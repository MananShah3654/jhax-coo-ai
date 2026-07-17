"""
JhaPay AI COO™ - Backend API.

Endpoints (all under /api):
  GET  /                          - health
  POST /auth/pin                  - PIN login
  GET  /dashboard                 - today KPIs + health + briefing
  GET  /briefing                  - daily CEO briefing
  GET  /branches                  - branch performance
  GET  /menu                      - menu performance
  GET  /customers                 - customer intelligence
  GET  /revenue                   - revenue breakdown
  GET  /forecast                  - forecast next 30 days
  GET  /operations                - peak hours, wait times
  POST /ai/chat                   - streaming AI COO chat (SSE)
  POST /ai/transcribe             - audio -> text (Whisper)
  POST /ai/tts                    - text -> audio (OpenAI TTS)
  POST /campaigns/generate        - AI-drafted campaign
  POST /campaigns/image           - AI promotional banner (free text-to-image)
  POST /combos/generate           - AI product combo (data-grounded, sales-optimized)
  POST /actions/execute           - execute one-click actions (mocked: SMS/Email/...)
  GET  /reports/{type}            - generate text report (markdown)
"""
from __future__ import annotations

import asyncio
import io
import json
import logging
import os
import uuid
from pathlib import Path
import hashlib
from datetime import date, datetime, timezone

from dotenv import load_dotenv
from fastapi import APIRouter, Depends, FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import StreamingResponse, Response
from pydantic import BaseModel
from starlette.middleware.cors import CORSMiddleware

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / ".env")

# Local imports (after env loaded so LLM_API_KEY is available)
from mock_data import DATASET  # noqa: E402  (kept for backwards compat)
from data_source import get_source  # noqa: E402
from analytics import (  # noqa: E402
    today_kpis, daily_briefing, branch_performance, menu_performance,
    customer_intelligence, revenue_breakdown, forecast, operations_snapshot,
    health_score,
)
from ai_service import (  # noqa: E402
    stream_coo_reply, transcribe_audio, synthesize_speech, generate_campaign,
    build_campaign_image, generate_combo, parse_coo_json,
)
from pdf_report import build_report_pdf  # noqa: E402
from database import (  # noqa: E402
    User, get_db, init_db, set_user_pin, verify_user_pin,
)
from auth import get_current_user  # noqa: E402
from twilio_auth import router as twilio_auth_router  # noqa: E402
from sqlalchemy.orm import Session  # noqa: E402

DS = get_source()

OWNER_PIN = os.environ.get("OWNER_PIN", "1234")
OWNER_NAME = os.environ.get("OWNER_NAME", "Manan")

app = FastAPI(title="JhaPay AI COO API")
api = APIRouter(prefix="/api")

logging.basicConfig(level=logging.INFO,
                    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger("jhapay")


# -------------------- Schemas --------------------
class PinLogin(BaseModel):
    pin: str


class ChatRequest(BaseModel):
    session_id: str | None = None
    message: str


class CampaignRequest(BaseModel):
    audience: str
    channel: str
    goal: str


class CampaignImageRequest(BaseModel):
    description: str
    style: str | None = "photorealistic"
    seed: int | None = None


class SquarePromoRequest(BaseModel):
    name: str
    discount: float                 # percent off, 0 < d < 100
    items: list[str] | None = None  # recorded for context; Square gets the discount


class ComboRequest(BaseModel):
    # Optional hint (e.g. the current campaign goal). Combos are generated from
    # live sales trends + best-sellers even when this is empty.
    focus: str | None = None


class TTSRequest(BaseModel):
    text: str
    voice: str = "nova"


class ActionRequest(BaseModel):
    id: str
    kind: str
    label: str | None = None
    target: str | None = None
    payload: dict | None = None


class ProfileUpdate(BaseModel):
    """Onboarding / profile fields the Firebase token doesn't carry.

    A phone-login token has no email/name; an email-login token has no phone.
    The client fills the gaps here after first sign-in. All fields optional so
    the same endpoint supports partial edits later.
    """
    name: str | None = None
    restaurant_name: str | None = None
    email: str | None = None
    phone_number: str | None = None


class PinBody(BaseModel):
    pin: str


def _validate_pin(pin: str) -> str:
    pin = (pin or "").strip()
    if not (pin.isdigit() and len(pin) == 4):
        raise HTTPException(400, "PIN must be exactly 4 digits.")
    return pin


# -------------------- Health / Auth --------------------
@api.get("/")
async def root():
    return {"service": "JhaPay AI COO", "version": "1.0", "ok": True}


@api.post("/auth/pin")
async def auth_pin(req: PinLogin):
    if req.pin != OWNER_PIN:
        raise HTTPException(status_code=401, detail="Invalid PIN")
    token = uuid.uuid4().hex
    return {
        "token": token,
        "owner": {"name": OWNER_NAME, "restaurant": DS.owner()["restaurant"]},
    }


@api.get("/me")
async def me(user: User = Depends(get_current_user)):
    """Return the current Firebase-authenticated user (created on first call).

    Send `Authorization: Bearer <firebase_id_token>`. The token is verified with
    the Firebase Admin SDK and the user is looked up / created in Postgres.
    Works for both email and phone sign-in — the backend just verifies the token.
    """
    return user.as_dict()


@api.patch("/me")
async def update_me(
    req: ProfileUpdate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Fill in / edit profile fields the Firebase token doesn't provide.

    Used during onboarding: e.g. a phone-login user supplies name, email and
    restaurant_name here. Only fields sent in the body are changed.
    """
    for field, value in req.model_dump(exclude_unset=True).items():
        setattr(user, field, value)
    db.commit()
    db.refresh(user)
    return user.as_dict()


@api.post("/me/pin")
async def set_pin(
    req: PinBody,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Create or replace the current user's quick-unlock PIN (hashed)."""
    pin = _validate_pin(req.pin)
    set_user_pin(db, user, pin)
    return {"ok": True, "has_pin": True}


@api.post("/me/pin/verify")
async def verify_pin(
    req: PinBody,
    user: User = Depends(get_current_user),
):
    """Verify a PIN for quick unlock.

    Requires a valid Firebase token (get_current_user) — so this only works
    while the device's session/refresh token is still valid. Status codes:
      401  token missing/expired (from get_current_user) → client does full login
      400  no PIN set for this user
      403  wrong PIN
    """
    if not user.pin_hash:
        raise HTTPException(400, "No PIN set for this account.")
    if not verify_user_pin(user, req.pin):
        raise HTTPException(403, "Incorrect PIN.")
    return {"ok": True}


# -------------------- Dashboard / Briefing --------------------
@api.get("/dashboard")
async def dashboard():
    return {
        "owner": {"name": OWNER_NAME, "restaurant": DS.owner()["restaurant"]},
        "today": today_kpis(),
        # Repeat Customer Rate is a cohort snapshot (not a daily window), so it
        # comes from customer_intelligence rather than today_kpis — surfaced here
        # so the dashboard can show all headline KPIs from one call.
        "repeat_rate_pct": customer_intelligence()["repeat_rate_pct"],
        "health": health_score(),
        "briefing": daily_briefing(),
        "branches_top3": branch_performance(7)[:3],
        # Last 14 days of daily revenue for the Total Revenue sparkline.
        "revenue_14d": revenue_breakdown(30)["by_day"][-14:],
        "data_source": DS.name,
    }


@api.get("/briefing")
async def briefing():
    return daily_briefing()


@api.get("/branches")
async def branches(days: int = 7):
    return {"days": days, "branches": branch_performance(days)}


@api.get("/menu")
async def menu(days: int = 30):
    perf = menu_performance(days)
    return {
        "days": days,
        "top": perf[:5],
        "bottom": perf[-5:],
        "all": perf,
    }


@api.get("/menu/catalog")
async def menu_catalog():
    """Raw integrated menu catalog (live Knowlwood API when DATA_SOURCE=knowlwood).

    Returns the mapped menu items grouped by category so the UI can browse the
    real catalog, not just performance analytics.
    """
    items = DS.menu()
    by_cat: dict[str, list] = {}
    for it in items:
        by_cat.setdefault(it.get("category", "Uncategorized"), []).append(it)
    categories = getattr(DS, "categories", lambda: [])()
    return {
        "data_source": DS.name,
        "restaurant": DS.owner()["restaurant"],
        "item_count": len(items),
        "categories": categories,
        "items_by_category": [
            {"category": cat, "items": sorted(its, key=lambda x: x["name"])}
            for cat, its in sorted(by_cat.items())
        ],
        "items": items,
    }


@api.get("/customers")
async def customers():
    return customer_intelligence()


@api.get("/revenue")
async def revenue(days: int = 30):
    return {"days": days, **revenue_breakdown(days)}


@api.get("/forecast")
async def get_forecast(days: int = 30):
    return forecast(days)


@api.get("/operations")
async def operations():
    return operations_snapshot()


# -------------------- AI Chat (streaming SSE) --------------------
@api.post("/ai/chat")
async def ai_chat(req: ChatRequest):
    session_id = req.session_id or uuid.uuid4().hex

    async def event_gen():
        # Emit session id first
        yield f"event: session\ndata: {json.dumps({'session_id': session_id})}\n\n"
        try:
            async for chunk in stream_coo_reply(session_id, req.message):
                if chunk:
                    yield f"event: delta\ndata: {json.dumps({'text': chunk})}\n\n"
            yield "event: done\ndata: {}\n\n"
        except Exception as exc:  # surface error to client
            logger.exception("AI chat error")
            yield f"event: error\ndata: {json.dumps({'message': str(exc)})}\n\n"

    return StreamingResponse(
        event_gen(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no",
                 "Connection": "keep-alive"},
    )


# Non-stream fallback for tests / quick replies
@api.post("/ai/chat_once")
async def ai_chat_once(req: ChatRequest):
    session_id = req.session_id or uuid.uuid4().hex
    buf = ""
    async for chunk in stream_coo_reply(session_id, req.message):
        buf += chunk
    parsed = parse_coo_json(buf)
    return {"session_id": session_id, "reply": parsed, "raw": buf}


# -------------------- Voice --------------------
@api.post("/ai/transcribe")
async def ai_transcribe(file: UploadFile = File(...)):
    data = await file.read()
    if not data:
        raise HTTPException(400, "Empty audio")
    # Whisper accepts a file-like; give it a name so the SDK picks the right MIME
    name = file.filename or "audio.webm"
    bio = io.BytesIO(data)
    bio.name = name
    try:
        text = await transcribe_audio(bio)
    except Exception as e:
        logger.exception("STT error")
        raise HTTPException(500, f"Transcription failed: {e}")
    return {"text": text}


@api.post("/ai/tts")
async def ai_tts(req: TTSRequest):
    try:
        audio = await synthesize_speech(req.text, voice=req.voice)
    except Exception as e:
        logger.exception("TTS error")
        raise HTTPException(500, f"TTS failed: {e}")
    return Response(content=audio, media_type="audio/mpeg")


# -------------------- Campaigns / Actions / Reports --------------------
@api.post("/campaigns/generate")
async def campaigns_generate(req: CampaignRequest):
    draft = await generate_campaign(req.audience, req.channel, req.goal)
    return {"audience": req.audience, "channel": req.channel, "goal": req.goal, "draft": draft}


@api.post("/campaigns/image")
async def campaigns_image(req: CampaignImageRequest):
    """Generate a promotional banner from a text description (free Pollinations)."""
    if not req.description or not req.description.strip():
        raise HTTPException(400, "Describe the banner you'd like.")
    try:
        return await build_campaign_image(
            req.description, req.style or "photorealistic", seed=req.seed
        )
    except Exception as e:
        logger.exception("Banner generation error")
        raise HTTPException(500, f"Banner generation failed: {e}")


@api.post("/combos/generate")
async def combos_generate(req: ComboRequest):
    """AI product combo optimized from current sales trends + best-sellers."""
    try:
        return await generate_combo(req.focus)
    except Exception as e:
        logger.exception("Combo generation error")
        raise HTTPException(500, f"Combo generation failed: {e}")


@api.post("/promotions/square-push")
async def promotions_square_push(req: SquarePromoRequest):
    """Create the promotion as a real DISCOUNT catalog object in Square.

    Reports exactly what Square returned. Unlike the mocked /actions/execute
    below, this touches a live POS catalog, so a failure must surface as a
    failure — the UI shows Square's own error text rather than a success toast.
    """
    name = (req.name or "").strip()
    if not name:
        raise HTTPException(400, "Promotion needs a name.")
    if not (0 < req.discount < 100):
        raise HTTPException(400, "Discount must be between 0 and 100 percent.")
    pusher = getattr(DS, "push_discount", None)
    if not callable(pusher):
        # Only SquareDataSource can push. Say so rather than pretend.
        raise HTTPException(
            400,
            f"Active data source is '{DS.name}', which has no Square catalog. "
            "Set DATA_SOURCE=square to push promotions to the POS.",
        )
    # Same name + same discount => same key => Square returns the existing
    # object instead of creating a duplicate on a double-click.
    key = hashlib.sha256(
        f"{name}|{req.discount}|{date.today().isoformat()}".encode("utf-8")
    ).hexdigest()[:40]
    result = pusher(name=name, percentage=req.discount, idempotency_key=key)
    obj = ((result.get("response") or {}).get("catalog_object") or {}) if result.get("ok") else {}
    return {
        "ok": result["ok"],
        "error": result["error"],
        "square_status": result["status"],
        "catalog_object_id": obj.get("id"),
        "version": obj.get("version"),
        # Square's verbatim body, so the UI/logs can show the real response.
        "square_response": result["response"],
        "pushed_at": datetime.now(timezone.utc).isoformat(),
        "items": req.items or [],
    }


@api.post("/actions/execute")
async def execute_action(req: ActionRequest):
    # All side-effect actions are mocked - in production they'd hit JhaPay SMS/Email/Push.
    now = datetime.now(timezone.utc).isoformat()
    kind = req.kind
    msg_map = {
        "campaign":  f"Campaign '{req.label or req.id}' scheduled. Owner can review in Marketing AI.",
        "share":     f"Report '{req.label or req.id}' shared via WhatsApp & Email.",
        "notify":    f"Manager notified about: {req.label or req.id}.",
        "promotion": f"Promotion '{req.label or req.id}' scheduled.",
        "report":    f"Report '{req.label or req.id}' generated.",
        "navigate":  f"Navigate -> {req.target or '/home'}",
    }
    detail = msg_map.get(kind, f"Action '{kind}' executed.")
    return {
        "ok": True,
        "executed_at": now,
        "kind": kind,
        "id": req.id,
        "detail": detail,
        "mocked": True,
    }


@api.get("/reports/{report_type}")
async def report(report_type: str):
    valid = {"daily", "weekly", "monthly", "branch", "investor", "marketing"}
    if report_type not in valid:
        raise HTTPException(400, f"Unknown report type. Valid: {valid}")
    today_k = today_kpis()
    health = health_score()
    branches = branch_performance(7)
    menu = menu_performance(30)
    ci = customer_intelligence()
    fc = forecast(30)
    body = (
        f"# {report_type.title()} Report — {DS.owner()['restaurant']}\n"
        f"_Generated {datetime.now(timezone.utc).strftime('%b %d, %Y %H:%M UTC')}_\n\n"
        f"## Today\n"
        f"- Revenue: ${today_k['revenue']:,.2f} ({today_k['vs_yesterday_pct']:+}% vs yesterday)\n"
        f"- Orders: {today_k['orders']}\n"
        f"- Avg Order: ${today_k['avg_order_value']:.2f}\n"
        f"- Tips: ${today_k['tips']:,.2f}\n"
        f"- Health Score: {health['score']}/100 ({health['state']})\n\n"
        f"## Branches (7d)\n"
        + "\n".join(f"- **{b['name']}** — ${b['revenue']:,.0f} ({b['growth_pct']:+}%)" for b in branches)
        + "\n\n## Top Menu Items (30d)\n"
        + "\n".join(f"- {m['name']} — ${m['revenue']:,.0f} ({m['units_sold']} units)" for m in menu[:5])
        + "\n\n## Customers\n"
        + f"- Total: {ci['total_customers']}\n"
        + f"- VIP: {ci['vip_count']}\n"
        + f"- At-Risk: {ci['at_risk_count']}\n"
        + f"- Repeat rate: {ci['repeat_rate_pct']}%\n\n"
        + f"## Next 30 Days Forecast\n- Projected Revenue: ${fc['projected_revenue']:,.0f}\n"
        + f"- Confidence: {fc['confidence']}%\n"
    )
    return {"type": report_type, "markdown": body}


@api.get("/reports/{report_type}/pdf")
async def report_pdf(report_type: str):
    valid = {"daily", "weekly", "monthly", "branch", "investor", "marketing"}
    if report_type not in valid:
        raise HTTPException(400, f"Unknown report type. Valid: {valid}")
    pdf = build_report_pdf(
        report_type=report_type,
        owner={"name": OWNER_NAME, "restaurant": DS.owner()["restaurant"]},
        today=today_kpis(),
        health=health_score(),
        branches=branch_performance(7),
        menu=menu_performance(30),
        customers_summary=customer_intelligence(),
        forecast_data=forecast(30),
        briefing=daily_briefing(),
    )
    filename = f"jhapay_{report_type}_report.pdf"
    return Response(
        content=pdf,
        media_type="application/pdf",
        headers={"Content-Disposition": f'inline; filename="{filename}"'},
    )


# -------------------- Wire up --------------------
@app.on_event("startup")
async def _on_startup():
    """Create Postgres tables (idempotent) on boot."""
    try:
        init_db()
        logger.info("Database initialized (tables ensured).")
    except Exception:
        # Don't crash the whole API if Postgres is momentarily unavailable;
        # DB-backed routes will surface the error per-request instead.
        logger.exception("Database init failed at startup")


app.include_router(api)
app.include_router(twilio_auth_router)  # /api/auth/send-otp, /api/auth/verify-otp
app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=os.environ.get("CORS_ORIGINS", "*").split(","),
    allow_methods=["*"],
    allow_headers=["*"],
)

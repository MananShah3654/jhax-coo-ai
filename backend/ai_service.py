"""
JhaPay AI COO - LLM-powered AI brain (Google Gemini for chat, Groq for voice).

Architecture (MCP-style, LLM never touches the DB):
  Frontend → AI Gateway → restaurant_context (via analytics.py) → Prompt
  Builder → LLM (streaming) → Response Formatter → UI.

The LLM is given a strict system prompt + the structured snapshot for
the current restaurant. It MUST reply in the executive "Decision Card"
format: STATUS / REASON / OPPORTUNITY / ACTION / EXPECTED IMPACT.

Providers:
  - Chat / text brain → Google Gemini (OpenAI-compatible; has a free tier). Config:
      GEMINI_API_KEY  (required for AI features)
      GEMINI_MODEL    (default: gemini-3.5-flash)
      GEMINI_API_BASE (default: Google's OpenAI-compatible endpoint)
  - Voice (STT / TTS) → Groq, OpenAI-compatible. Config:
      LLM_API_KEY   — free key from https://console.groq.com/keys
      LLM_API_BASE  (default: https://api.groq.com/openai/v1)
      STT_MODEL     (default: whisper-large-v3-turbo)
      TTS_MODEL     (default: playai-tts)
      TTS_VOICE     (default: Fritz-PlayAI)
"""
from __future__ import annotations

import hashlib
import json
import os
import re
from typing import AsyncGenerator
from urllib.parse import quote

from openai import AsyncOpenAI

from analytics import restaurant_context, menu_performance, today_kpis

# --- Chat brain: Google Gemini via its OpenAI-compatible endpoint. Has a FREE
# tier (no billing required), so it slots into the same AsyncOpenAI client. ---
GEMINI_API_KEY  = os.environ.get("GEMINI_API_KEY", "")
GEMINI_API_BASE = os.environ.get(
    "GEMINI_API_BASE", "https://generativelanguage.googleapis.com/v1beta/openai/")
GEMINI_MODEL    = os.environ.get("GEMINI_MODEL", "gemini-3.5-flash")

# --- Voice: Groq (Whisper STT + PlayAI TTS). Kept on its own OpenAI-compatible
# client for transcribe/synthesize only. ---
LLM_API_KEY  = os.environ.get("LLM_API_KEY", "")
LLM_API_BASE = os.environ.get("LLM_API_BASE", "https://api.groq.com/openai/v1")
LLM_MODEL    = os.environ.get("LLM_MODEL", "llama-3.3-70b-versatile")  # kept for compat; chat is Gemini now
STT_MODEL    = os.environ.get("STT_MODEL", "whisper-large-v3-turbo")
TTS_MODEL    = os.environ.get("TTS_MODEL", "playai-tts")
TTS_VOICE    = os.environ.get("TTS_VOICE", "Fritz-PlayAI")

# Chat client → Gemini (OpenAI-compatible). Audio client → Groq.
_chat   = AsyncOpenAI(api_key=GEMINI_API_KEY or "missing", base_url=GEMINI_API_BASE)
_client = AsyncOpenAI(api_key=LLM_API_KEY, base_url=LLM_API_BASE)


def _require_chat_key() -> None:
    if not GEMINI_API_KEY:
        raise RuntimeError(
            "GEMINI_API_KEY is not set. Add it to backend/.env (or the server "
            "environment) and restart the backend — the key is read once at startup."
        )


async def _chat_text(system: str, user: str, max_tokens: int = 1024,
                     temperature: float = 0.7) -> str:
    """One-shot chat completion → plain text (Gemini via OpenAI-compatible API)."""
    _require_chat_key()
    resp = await _chat.chat.completions.create(
        model=GEMINI_MODEL,
        messages=[{"role": "system", "content": system},
                  {"role": "user", "content": user}],
        temperature=temperature,
        max_tokens=max_tokens,
    )
    return resp.choices[0].message.content or ""

SYSTEM_PROMPT = """You are JhaPay AI COO™ — a digital Chief Operating Officer for a restaurant owner.
You are NOT ChatGPT. You are NOT a general assistant.

DOMAIN (allowed topics ONLY): sales, revenue, orders, customers, marketing, loyalty,
payments, tips, branches, staff, inventory, forecasting, promotions, restaurant
operations and growth.

If the user asks anything outside that domain, reply with EXACTLY this JSON and nothing else:
{"status":"Out of scope","reason":"I'm JhaPay AI COO and can assist only with restaurant operations, revenue, customers, marketing, loyalty, payments, performance, and growth.","opportunity":"","action":"","expected_impact":"","metrics":[],"actions":[]}

CLARIFICATION GATE (CRITICAL):
If the user message is too short, vague, ambiguous, or not actually a question
(e.g. "you", "ok", "hi", "what?", "hello", a single noun like "revenue", random
characters), DO NOT guess and DO NOT dump metrics. Instead reply with this exact
schema (clarify is filled, all other fields empty strings or empty arrays):
{
  "status": "I need a bit more to help",
  "clarify": "<a short question back, max 12 words>",
  "suggestions": ["<chip 1 max 6 words>", "<chip 2>", "<chip 3>"],
  "reason":"","opportunity":"","action":"","expected_impact":"","metrics":[],"actions":[]
}

ANSWER FORMAT — when the question IS clear, return STRICT JSON ONLY (no prose,
no markdown fences). BE EXTREMELY CONCISE. Glanceable, executive, decisive.

{
  "status":          "<headline, MAX 8 words, must include a number where relevant>",
  "reason":          "<MAX 14 words, plain English, grounded in data>",
  "opportunity":     "<MAX 14 words, optional - leave empty string if not applicable>",
  "action":          "<imperative, MAX 8 words>",
  "expected_impact": "<concrete: '+$1,800/wk' or '+12% repeats' - MAX 5 words>",
  "metrics":         [{"label":"<2-3 words>","value":"<formatted>"}],   // 0-3 items
  "actions": [    // 0-3 one-click buttons rendered as chips - NO MORE
     {"id":"launch_campaign","label":"Launch Campaign","kind":"campaign","target":"/marketing","prefill":{"audience":"at_risk","channel":"sms","goal":"Reactivate inactive customers"}},
     {"id":"share_report","label":"Share Report","kind":"share","target":"daily"},
     {"id":"view_branches","label":"View Branches","kind":"navigate","target":"/branches"}
  ]
}

Action.kind ∈ {"campaign","share","navigate","notify","promotion","report"}.
For "navigate", target is a route: /home, /chat, /branches, /customers, /menu, /marketing, /promotions, /forecast, /manager.
For "share"/"report", target is one of: daily, weekly, monthly, branch, investor, marketing.
For "campaign", include `prefill` {audience, channel, goal} so Marketing opens prefilled.
For "promotion" (e.g. "Create Combo", "Bundle Deal", "Happy Hour"), include `prefill`
{name, items:[menu_item_names], discount:number, audience} so the Combo Builder opens prefilled.
For "notify" (e.g. "Notify Downtown Manager"), include `prefill` {branch, message} so
Manager Mode opens with the task ready to send.

Prefer "promotion" over "campaign" when the action is about menu items / bundles /
combos / discounts. Use "campaign" when it's about outbound messaging to a customer
segment (SMS / email / push).

SALES & ORDERS PLAYBOOK (these are the two most common questions — answer them well):

Sales / revenue ("how are sales", "revenue this week", "why is revenue down"):
- Headline the number from today.revenue; read the trend from today.vs_yesterday_pct
  and today.vs_last_week_pct.
- ALWAYS decompose a revenue move into its two drivers: revenue = orders x average order
  value. Use today.orders_vs_last_week_pct and today.aov_vs_last_week_pct to say WHICH
  driver moved. "Revenue -8%: orders fell 11%, AOV held" is a real answer; "sales are
  down" is not. Put the driver in `reason`.
- For "WHY is revenue/sales DOWN" specifically, use revenue_diagnosis (baseline = same
  weekday, last 4 weeks, same hour — far more reliable than vs-yesterday):
    * revenue_diagnosis.anomaly.flagged + .delta_pct confirm the drop is real vs baseline.
    * revenue_diagnosis.ranked_causes is pre-scored and sorted. Lead `reason` with the
      #1 cause and cite its delta% (e.g. "Traffic down 30% vs 4-week baseline").
    * traffic, repeat_customer and discount_overuse in ranked_causes are
      data-backed — use them. ONLY for signals actually listed in
      revenue_diagnosis.unavailable_signals say data isn't tracked yet — NEVER
      invent a number for those.
- "This week"/trend -> sales_30d.by_day_14d. "Where do sales come from" ->
  sales_30d.by_channel. "When are we busy" -> sales_30d.by_hour + operations.peak_hours.

Orders ("how many orders", "orders dropped", "order volume"):
- Count from today.orders; trend from today.orders_vs_yesterday_pct /
  orders_vs_last_week_pct.
- Explain a drop using operations.slow_hours and sales_30d.by_channel (which daypart or
  channel is weak), and make `action` a demand lever (promo in a slow hour, channel push)
  — never just restate the count.

Operating KPIs (answer straight from today.*, always grounded — this is the
headline metric set the dashboard shows):
- Total Revenue -> today.revenue.  Order Count -> today.orders.
- Covers (guests served) -> today.covers, trend today.covers_vs_yesterday_pct.
- Average Order Value -> today.avg_order_value.
- Average Discount % -> today.avg_discount_pct (share of subtotal discounted).
- Cart Abandonment % -> today.cart_abandonment_pct (online checkouts abandoned).
- Repeat Customer Rate -> customers.repeat_rate_pct.
- Table Turnover -> today.table_turnover (dine-in turns per table per day).
- RevPASH -> today.revpash (revenue per available seat-hour, dine-in).
IMPORTANT: any KPI whose value is null in the context is NOT measurable on the
active data source (e.g. Square exposes no seat capacity or cart funnel). Say
"not tracked on this source" for it — NEVER fabricate a value.

Menu / best-seller: use top_menu_30d (units_sold, revenue, margin_pct) and
bottom_menu_30d. Push a "promotion" action for menu/combo/discount levers.

PAYMENT MIX ("what % of payments are card vs cash", "how do people pay"):
- Pick the window that matches the question, never a wider one: "yesterday" ->
  payments_yesterday. "today" -> payments_today. "this week" -> payments_this_week.
  No window named / "lately" / "usually" -> payments_30d. State which window you used.
- REVENUE BASIS IS MANDATORY. Every payment-mix answer must cite BOTH the dollar
  amount and the percent from by_method[].revenue and by_method[].revenue_pct —
  e.g. "Card $1,240 (62%), cash $610 (31%), other $140 (7%)". A bare percentage
  is not an acceptable answer.
- NEVER mix bases in one answer. by_method[].revenue / .revenue_pct are revenue
  (dollars); by_method[].orders is a COUNT of orders. Do not present an
  orders-basis number as a share of payments, and never blend the two — quoting
  "62% of payments" from revenue_pct alongside an order count as if they measure
  the same thing is wrong. Default to revenue basis; mention order counts only
  when explicitly asked, and label them "orders" when you do.
- If tracked_orders is 0, say exactly "no payment method recorded on this source"
  and give NO split — no percentages, no dollars, no estimate. The `note` field
  says the same thing. NEVER fabricate or infer a card/cash split.
- untracked_orders > 0 means some orders in the window carry no tender yet
  (unpaid/OPEN). The split covers tracked_revenue only — say so if it's material.
- Per-item mix ("how do people pay for the BLT") uses payment_breakdown's item
  scope: that item's line revenue attributed to each order's payment method.

PROFIT / P&L ("what's our profit this month", "are we making money", "margin"):
- Use profit_mtd. Headline profit_mtd.gross_profit_estimated with the dollar
  amount and gross_margin_pct, and name the window (month-to-date, not a full month).
- ALWAYS say it is an ESTIMATE in the same breath as the number — profit_mtd
  .is_estimate is true. Two things make it one: cost of goods is modelled as a
  flat share of menu price (profit_mtd.cogs_method), not real supplier invoices;
  and it is GROSS profit only — everything in profit_mtd.excludes (labour, rent,
  utilities, overhead) is missing, so true net profit is LOWER. Never present it
  as bookkeeping, and never call it "net profit" or "the bottom line".
- Put the caveat where the owner will read it, not buried: `reason` should carry
  "estimate — excludes labour/rent" or equivalent.
- If profit_mtd.discounts_tracked is false, the $0 discount line means the source
  records no discounts — say "discounts not tracked on this source", NOT
  "no discounts were given".
- Never invent labour cost, rent, or any overhead figure to "complete" the P&L.

RULES:
- Be decisive. No hedging, no "it depends".
- Ground every number in the RESTAURANT_CONTEXT provided in the user turn.
- Never invent metrics.
- Currency: USD with $ and thousands separator ($12,480 or $1.2k).
- Tone: humble, professional, executive, action-oriented.
- NEVER output anything outside the single JSON object.
"""


# The heavy context sections — the same-weekday revenue diagnosis, the 30-day
# menu leaderboards, and the sales-by-channel/hour/day history — are only injected
# when the question actually calls for them. A plain KPI question ("how many covers
# today?") no longer ships the full ~1.7k-token snapshot on every turn, which
# roughly halves per-call input tokens — important on metered / free LLM tiers
# (e.g. Groq's 100k tokens/day free cap). The compact `today`/health/customers/
# operations/branches core is always sent so KPI answers stay fully grounded.
_CTX_TRIGGERS = {
    "revenue_diagnosis": ("why", "down", "drop", "fell", "fall", "declin", "lower",
                          "slow", "lost", "losing", "worse", "tank", "sink",
                          "sluggish", "underperform", "diagnos", "cause", "reason"),
    "menu": ("menu", "item", "seller", "sell", "dish", "food", "plate", "combo",
             "bundle", "product", "margin", "profit", "popular"),
    "sales_30d": ("channel", "hour", "daypart", "busy", "peak", "when", "where",
                  "breakdown", "trend", "week", "daily", "delivery", "takeout",
                  "to-go", "togo", "dine", "online", "source", "month"),
    "payments": ("payment", "pay", "paid", "card", "cash", "tender", "swipe",
                 "wallet", "credit", "debit"),
    "profit_mtd": ("profit", "p&l", "pnl", "margin", "bottom line", "making money",
                   "earnings", "net", "cogs", "cost of goods", "loss"),
}
_MENU_KEYS = ("top_menu_30d", "bottom_menu_30d")
# All four windows ship together on a payment question so the model can pick the
# one the question actually names instead of forcing a 30-day answer.
_PAYMENT_KEYS = ("payments_30d", "payments_today", "payments_yesterday",
                 "payments_this_week")
_HEAVY_KEYS = ("revenue_diagnosis", "sales_30d", *_MENU_KEYS, *_PAYMENT_KEYS,
               "profit_mtd")


def _select_context(question: str, src) -> dict:
    """Full context minus heavy sections the question doesn't need."""
    ctx = restaurant_context(src)
    q = (question or "").lower()
    lean = {k: v for k, v in ctx.items() if k not in _HEAVY_KEYS}
    if any(kw in q for kw in _CTX_TRIGGERS["revenue_diagnosis"]):
        lean["revenue_diagnosis"] = ctx.get("revenue_diagnosis")
    if any(kw in q for kw in _CTX_TRIGGERS["sales_30d"]):
        lean["sales_30d"] = ctx.get("sales_30d")
    if any(kw in q for kw in _CTX_TRIGGERS["menu"]):
        for k in _MENU_KEYS:
            if k in ctx:
                lean[k] = ctx[k]
    if any(kw in q for kw in _CTX_TRIGGERS["payments"]):
        for k in _PAYMENT_KEYS:
            if k in ctx:
                lean[k] = ctx[k]
    if any(kw in q for kw in _CTX_TRIGGERS["profit_mtd"]):
        lean["profit_mtd"] = ctx.get("profit_mtd")
    return lean


def _wrap_user(text: str, src) -> str:
    ctx = restaurant_context(src)
    return (
        "RESTAURANT_CONTEXT (live data, ground every answer in this):\n"
        + json.dumps(ctx, default=str)
        + "\n\nOWNER QUESTION: "
        + text
    )


_FENCE_RE = re.compile(r"^```(?:json)?\s*|\s*```$", re.IGNORECASE | re.MULTILINE)


def parse_coo_json(text: str) -> dict:
    """Robustly parse the Decision Card JSON from a model reply.
    Handles bare JSON, markdown ```json fences, and trailing prose."""
    s = (text or "").strip()
    s = _FENCE_RE.sub("", s).strip()
    # Try direct
    try:
        return json.loads(s)
    except Exception:
        pass
    # Fallback: grab the first balanced {...} block
    start = s.find("{")
    if start >= 0:
        depth = 0
        for i in range(start, len(s)):
            if s[i] == "{":
                depth += 1
            elif s[i] == "}":
                depth -= 1
                if depth == 0:
                    try:
                        return json.loads(s[start:i + 1])
                    except Exception:
                        break
    return {
        "status": "Response", "reason": s, "opportunity": "",
        "action": "", "expected_impact": "", "metrics": [], "actions": [],
    }


async def _raise_for_stream(resp: httpx.Response) -> None:
    """Read + raise a helpful error when a streaming call returns non-2xx."""
    if resp.status_code >= 400:
        body = (await resp.aread()).decode("utf-8", "ignore")
        raise RuntimeError(f"LLM error {resp.status_code}: {body[:400]}")


async def stream_coo_reply(session_id: str, user_text: str, src) -> AsyncGenerator[str, None]:
    """Yield raw token strings as the model generates them (SSE-friendly)."""
    _require_chat_key()
    stream = await _chat.chat.completions.create(
        model=GEMINI_MODEL,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": _wrap_user(user_text, src)},
        ],
        stream=True,
        temperature=0.3,
    )
    async for chunk in stream:
        if chunk.choices:
            delta = chunk.choices[0].delta.content
            if delta:
                yield delta


LABOR_SYSTEM_PROMPT = """You are the Workforce Analyst inside a restaurant operations dashboard.

You are given WORKFORCE_DATA: precomputed, ACCURATE labor metrics for a selected
time period (hours, wages, overtime, tips, attendance, per-day rush vs staffing,
per-employee costs). Every number in it is already calculated correctly — treat
it as ground truth.

Your job: answer the owner's question in plain, concise, conversational English,
like a sharp operations manager. Explain what the numbers mean and give one
practical, actionable takeaway when relevant.

RULES:
- Use ONLY numbers present in WORKFORCE_DATA. NEVER invent, estimate, or round to
  numbers that aren't there. If it's not in the data, say you don't have it.
- Format money as $ (e.g. $1,585), hours with h (e.g. 8.5h), shares as %.
- Wrap the KEY figures and names in **double asterisks** so they render bold —
  the standout number, the employee/shift name, the % that matters. Bold
  sparingly (a few per answer), never a whole sentence.
- The headline numbers ALSO appear as metric cards beside your answer, so don't
  just re-list them. Lead with the insight or story ("Maria's Friday close ran
  long"), reference the figures naturally, and end with one actionable takeaway.
- Keep it tight and catchy: 2–4 sentences or a few short bullets. No preamble.
- If a detailed table is shown separately in the UI, summarize the highlights —
  don't re-list every row.
- Plain text only. Do NOT output JSON or markdown code fences."""


async def stream_labor_reply(question: str, context_json: str) -> AsyncGenerator[str, None]:
    """Stream a grounded natural-language answer over precomputed labor data."""
    _require_chat_key()
    stream = await _chat.chat.completions.create(
        model=GEMINI_MODEL,
        messages=[
            {"role": "system", "content": LABOR_SYSTEM_PROMPT},
            {"role": "user", "content":
                f"WORKFORCE_DATA (the only numbers you may use):\n{context_json}\n\n"
                f"OWNER QUESTION: {question}"},
        ],
        stream=True,
        temperature=0.2,
    )
    async for chunk in stream:
        if chunk.choices:
            delta = chunk.choices[0].delta.content
            if delta:
                yield delta


async def generate_campaign(audience: str, channel: str, goal: str) -> dict:
    """Draft a marketing campaign (subject + body + CTA)."""
    prompt = (
        f"Draft a {channel} campaign for the audience '{audience}'. "
        f"The goal is: {goal}. Keep it punchy and action-oriented."
    )
    buf = await _chat_text(
        system=(
            "You are a restaurant marketing copywriter. Return STRICT JSON ONLY with "
            "keys: subject (string, <=80 chars), body (string, <=400 chars, friendly "
            "and on-brand for a casual upscale bistro called 'Jha Bistro'), cta "
            "(string, <=20 chars), estimated_reach (integer), estimated_revenue (integer)."
        ),
        user=prompt,
        max_tokens=512,
        temperature=0.7,
    )
    parsed = parse_coo_json(buf)
    if "subject" not in parsed:
        parsed = {"subject": "Your Jha Bistro Update", "body": buf[:400], "cta": "Order Now",
                  "estimated_reach": 0, "estimated_revenue": 0}
    return parsed


# -------- AI-generated health-step actions (replaces the static templates) --------

_HEALTH_METRIC_LABELS = {
    "revenue_growth": "Revenue growth (last 7 days vs prior 7)",
    "repeat_customers": "Repeat-customer rate",
    "reviews": "Review / rating score",
    "wait_times": "Order wait times",
    "tips": "Tip rate",
    "staff_efficiency": "Staff efficiency",
}

# Small cache so we don't call the LLM on every dashboard load — keyed by the
# weak metrics + their (rounded) scores, which only change as the data moves.
_HEALTH_ACTION_CACHE: dict[str, dict] = {}


async def generate_health_actions(steps: list[dict], context: dict | None = None) -> dict:
    """Turn the weak health metrics into specific, data-grounded one-line actions
    via the LLM. Returns {metric_key: action_string}. Best-effort: returns {} on
    no key / no steps / any error, so the caller keeps the built-in templates."""
    if not GEMINI_API_KEY or not steps:
        return {}
    cache_key = json.dumps(
        [(s.get("metric"), s.get("score")) for s in steps], sort_keys=True)
    if cache_key in _HEALTH_ACTION_CACHE:
        return _HEALTH_ACTION_CACHE[cache_key]

    weak = [{"metric": s["metric"],
             "label": _HEALTH_METRIC_LABELS.get(s["metric"], s["metric"]),
             "score": s["score"]} for s in steps]
    system = (
        "You are a restaurant COO advising the owner. For EACH weak metric below, "
        "write ONE specific, imperative next action (max 12 words) to improve it, "
        "grounded in the provided numbers. Return STRICT JSON ONLY: an object that "
        "maps each metric key to its action string. No prose, no markdown fences."
    )
    user = (
        "Weak metrics (score 0-100, lower is worse):\n" + json.dumps(weak)
        + "\n\nLive context:\n" + json.dumps(context or {}, default=str)
    )
    try:
        buf = await _chat_text(system=system, user=user, max_tokens=800, temperature=0.5)
        data = json.loads(_FENCE_RE.sub("", buf).strip())
        actions = {k: v.strip() for k, v in data.items()
                   if isinstance(v, str) and v.strip()}
    except Exception:
        return {}
    if len(_HEALTH_ACTION_CACHE) > 100:  # cheap unbounded-growth guard
        _HEALTH_ACTION_CACHE.clear()
    _HEALTH_ACTION_CACHE[cache_key] = actions
    return actions


# -------- AI Combo builder (data-grounded, sales-optimized) --------

def _charm_price(x: float) -> float:
    """Round a price to a psychological charm price (…​.99 / …​.49)."""
    base = int(x)  # floor for positive values
    if base < 1:
        return round(x, 2)
    return round(base - 0.01 if (x - base) < 0.5 else base + 0.49, 2)


def _assemble_combo(*, name: str, tagline: str, items: list[dict],
                    combo_price, daypart: str, rationale: str,
                    uplift_pct, today_revenue: float = 0.0) -> dict:
    """Build the final combo dict with prices/savings recomputed from REAL menu
    prices, so the offer math is always correct regardless of the LLM output."""
    line_items = [{"name": m["name"], "category": m.get("category", ""),
                   "price": round(float(m["price"]), 2)} for m in items]
    regular_total = round(sum(li["price"] for li in line_items), 2)
    # Keep the discount in a sensible 5%–25%-off band.
    lo, hi = round(regular_total * 0.75, 2), round(regular_total * 0.95, 2)
    try:
        cp = float(combo_price)
    except (TypeError, ValueError):
        cp = 0.0
    cp = round(regular_total * 0.85, 2) if cp <= 0 else min(max(cp, lo), hi)
    cp = _charm_price(cp)
    savings = round(regular_total - cp, 2)
    savings_pct = round(savings / regular_total * 100, 1) if regular_total else 0.0
    try:
        uplift = int(uplift_pct)
    except (TypeError, ValueError):
        uplift = 8
    uplift = min(max(uplift, 3), 20)
    return {
        "name": (name or "Best-Sellers Bundle")[:40],
        "tagline": (tagline or "Your favourites, together for less.")[:90],
        "items": line_items,
        "regular_total": regular_total,
        "combo_price": cp,
        "savings": savings,
        "savings_pct": savings_pct,
        "target_daypart": daypart or "All day",
        "rationale": (rationale or "")[:220],
        "expected_uplift_pct": uplift,
        "expected_daily_revenue": int(round(today_revenue * uplift / 100)),
    }


def _fallback_combo(top: list[dict], today_revenue: float = 0.0) -> dict:
    """Deterministic combo used when the LLM is unavailable or returns junk:
    the top revenue items across distinct categories, so it's always relevant."""
    picked, seen = [], set()
    for m in top:
        if m.get("category") in seen:
            continue
        seen.add(m.get("category"))
        picked.append(m)
        if len(picked) == 3:
            break
    if len(picked) < 2:
        picked = top[:2]
    return _assemble_combo(
        name="Best-Sellers Bundle",
        tagline="Pair your top picks and save.",
        items=picked,
        combo_price=None,
        daypart="All day",
        rationale="Bundles your highest-revenue items across courses to lift "
                  "average order value with proven crowd-pleasers.",
        uplift_pct=8,
        today_revenue=today_revenue,
    )


async def generate_combo(focus: str | None = None) -> dict:
    """Auto-generate an optimized product combo from current sales trends and the
    best-selling products. The LLM chooses complementary items and writes the
    offer; pricing/savings are recomputed from real menu prices for accuracy."""
    ranked = menu_performance(30)
    if not ranked:
        return _assemble_combo(name="Combo", tagline="", items=[], combo_price=None,
                               daypart="All day", rationale="", uplift_pct=8)
    top = ranked[:8]
    by_name = {m["name"].strip().lower(): m for m in ranked}
    kpis = today_kpis()
    today_revenue = float(kpis.get("revenue", 0) or 0)

    fallback = _fallback_combo(top, today_revenue)
    if not GEMINI_API_KEY:
        return fallback

    catalog = [
        {"name": m["name"], "category": m["category"], "price": round(m["price"], 2),
         "units_sold_30d": m["units_sold"], "margin_pct": m["margin_pct"]}
        for m in top
    ]
    trend_wk = kpis.get("vs_last_week_pct", 0)
    trend_dir = "up" if trend_wk > 0 else "down" if trend_wk < 0 else "flat"
    focus_line = f" The owner wants to focus on: {focus.strip()}." if focus else ""

    system = (
        "You are a restaurant menu-strategy expert for a casual upscale bistro "
        "called 'Jha Bistro'. Design ONE bundled combo offer that increases sales "
        "and average order value. Pick 2-4 COMPLEMENTARY items (e.g. a main + a "
        "side + a drink or dessert) ONLY from the provided best-seller catalog. "
        "Prefer high-margin items and pairings that suit the current sales trend. "
        "Return STRICT JSON ONLY with keys: name (string, <=40 chars, catchy), "
        "tagline (string, <=90 chars), item_names (array of 2-4 strings copied "
        "EXACTLY from the catalog names), combo_price (number, LESS than the sum "
        "of the chosen item prices), target_daypart (one of: Breakfast, Lunch, "
        "Dinner, All day), rationale (string, <=200 chars, why this bundle sells "
        "given the trend), expected_uplift_pct (integer 3-20). No prose outside JSON."
    )
    user = (
        f"Best-seller catalog (last 30 days):\n{json.dumps(catalog)}\n\n"
        f"Sales trend vs last week: {trend_wk}% ({trend_dir}). "
        f"Today revenue ${today_revenue:.0f}, "
        f"avg order ${kpis.get('avg_order_value', 0):.2f}.{focus_line}"
    )
    try:
        buf = await _chat_text(system=system, user=user, max_tokens=800, temperature=0.8)
        parsed = parse_coo_json(buf)
    except Exception:
        return fallback

    # Map the model's picks back to real menu items; drop anything unrecognised.
    items, seen_ids = [], set()
    for n in (parsed.get("item_names") or []):
        if not isinstance(n, str):
            continue
        m = by_name.get(n.strip().lower())
        if m and m["id"] not in seen_ids:
            seen_ids.add(m["id"])
            items.append(m)
    if len(items) < 2:
        return fallback

    return _assemble_combo(
        name=parsed.get("name") or fallback["name"],
        tagline=parsed.get("tagline") or fallback["tagline"],
        items=items[:4],
        combo_price=parsed.get("combo_price"),
        daypart=parsed.get("target_daypart") or "All day",
        rationale=parsed.get("rationale") or fallback["rationale"],
        uplift_pct=parsed.get("expected_uplift_pct"),
        today_revenue=today_revenue,
    )


# -------- Promotional banner (free text-to-image) --------

# Pollinations.ai serves text-to-image over a plain GET URL — no key, no cost.
# We return the URL and let the browser <img> load it directly (no proxying).
IMG_BASE = os.environ.get("IMG_API_BASE", "https://image.pollinations.ai/prompt").rstrip("/")
IMG_MODEL = os.environ.get("IMG_MODEL", "flux")


async def _enhance_image_prompt(description: str, style: str) -> str:
    """Turn the owner's short description into a vivid banner prompt.

    Best-effort: uses the LLM when a key is present, otherwise falls back to a
    solid template so banner generation never hard-fails on the copy step.
    """
    base = (
        f"Professional food-marketing banner for 'Jha Bistro', a casual upscale "
        f"bistro. {description.strip()}. {style}, appetizing, vibrant, warm "
        f"lighting, shallow depth of field, high detail, clean composition with "
        f"empty space for a headline, no text, no watermark, no logo."
    )
    if not GEMINI_API_KEY:
        return base
    try:
        txt = (await _chat_text(
            system=(
                "You write concise text-to-image prompts for restaurant "
                "promotional banners. Reply with ONE prompt, max 55 words, "
                "vivid and photographic. Always end with: 'clean composition "
                "with empty space for a headline, no text, no watermark'. "
                "No preamble, no quotes."
            ),
            user=(
                f"Banner for 'Jha Bistro'. Owner's idea: {description.strip()}. "
                f"Preferred style: {style}."
            ),
            max_tokens=200,
            temperature=0.8,
        )).strip()
        return txt or base
    except Exception:
        return base


async def build_campaign_image(
    description: str,
    style: str = "photorealistic",
    width: int = 1200,
    height: int = 628,
    seed: int | None = None,
) -> dict:
    """Build a promotional banner image URL from a text description.

    Returns {url, prompt, seed}. Default size is a social-banner ratio (1200×628).
    `seed` makes results reproducible; pass a new seed to regenerate a variant.
    """
    prompt = await _enhance_image_prompt(description, style)
    if seed is None:
        seed = int(hashlib.sha256(prompt.encode("utf-8")).hexdigest(), 16) % 1_000_000
    encoded = quote(prompt, safe="")
    url = (
        f"{IMG_BASE}/{encoded}"
        f"?width={width}&height={height}&nologo=true&model={IMG_MODEL}&seed={seed}"
    )
    return {"url": url, "prompt": prompt, "seed": seed}


# -------- Voice (Groq Whisper STT + TTS) --------

async def transcribe_audio(file_obj) -> str:
    resp = await _client.audio.transcriptions.create(
        model=STT_MODEL, file=file_obj, response_format="json", language="en"
    )
    return resp.text


async def synthesize_speech(text: str, voice: str | None = None) -> bytes:
    # Groq TTS uses its own voices (e.g. Fritz-PlayAI); OpenAI voice names aren't valid,
    # so we always use TTS_VOICE from env and ignore the incoming `voice`.
    resp = await _client.audio.speech.create(
        model=TTS_MODEL,
        voice=TTS_VOICE,
        input=text[:4000],
        response_format="mp3",
    )
    return resp.read()

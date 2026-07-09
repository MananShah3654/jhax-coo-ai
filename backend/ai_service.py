"""
JhaPay AI COO - free-LLM powered AI brain (OpenAI-compatible API).

Architecture (MCP-style, LLM never touches the DB):
  Frontend → AI Gateway → restaurant_context (via analytics.py) → Prompt
  Builder → LLM (streaming) → Response Formatter → UI.

The LLM is given a strict system prompt + the structured snapshot for
the current restaurant. It MUST reply in the executive "Decision Card"
format: STATUS / REASON / OPPORTUNITY / ACTION / EXPECTED IMPACT.

Provider: any OpenAI-compatible endpoint. Defaults to Groq's FREE tier
(Llama 3.3 70B + Whisper). Configure via env in backend/.env:
  LLM_API_KEY   (required)  — free key from https://console.groq.com/keys
  LLM_API_BASE  (default: https://api.groq.com/openai/v1)
  LLM_MODEL     (default: llama-3.3-70b-versatile)
  STT_MODEL     (default: whisper-large-v3-turbo)
  TTS_MODEL     (default: playai-tts)
  TTS_VOICE     (default: Fritz-PlayAI)
"""
from __future__ import annotations

import json
import os
import re
import uuid
from typing import AsyncGenerator

import httpx

from analytics import restaurant_context

# ---- Provider config (OpenAI-compatible; default = Groq free tier) ----
LLM_API_BASE = os.environ.get("LLM_API_BASE", "https://api.groq.com/openai/v1").rstrip("/")
# Accept a few common env names so any free provider key just works.
LLM_API_KEY = (
    os.environ.get("LLM_API_KEY")
    or os.environ.get("GROQ_API_KEY")
    or os.environ.get("OPENAI_API_KEY")
    or ""
)
LLM_MODEL = os.environ.get("LLM_MODEL", "llama-3.3-70b-versatile")
STT_MODEL = os.environ.get("STT_MODEL", "whisper-large-v3-turbo")
TTS_MODEL = os.environ.get("TTS_MODEL", "playai-tts")
TTS_VOICE = os.environ.get("TTS_VOICE", "Fritz-PlayAI")

_TIMEOUT = httpx.Timeout(90.0, connect=10.0)


def _require_key() -> None:
    if not LLM_API_KEY:
        raise RuntimeError(
            "LLM_API_KEY is not set — add a FREE key to backend/.env. "
            "Get one at https://console.groq.com/keys (no credit card)."
        )


def _headers() -> dict:
    return {"Authorization": f"Bearer {LLM_API_KEY}", "Content-Type": "application/json"}


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

RULES:
- Be decisive. No hedging, no "it depends".
- Ground every number in the RESTAURANT_CONTEXT provided in the user turn.
- Never invent metrics.
- Currency: USD with $ and thousands separator ($12,480 or $1.2k).
- Tone: humble, professional, executive, action-oriented.
- NEVER output anything outside the single JSON object.
"""


def _wrap_user(text: str) -> str:
    ctx = restaurant_context()
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


async def stream_coo_reply(session_id: str, user_text: str) -> AsyncGenerator[str, None]:
    """Yield raw token strings as the model generates them (SSE-friendly).

    Note: each call is stateless (full context is injected every turn), so
    there is no server-side conversation memory — `session_id` is unused.
    """
    _require_key()
    payload = {
        "model": LLM_MODEL,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": _wrap_user(user_text)},
        ],
        "temperature": 0.4,
        "stream": True,
        "response_format": {"type": "json_object"},
    }
    async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
        async with client.stream(
            "POST", f"{LLM_API_BASE}/chat/completions",
            headers=_headers(), json=payload,
        ) as resp:
            await _raise_for_stream(resp)
            async for line in resp.aiter_lines():
                if not line or not line.startswith("data:"):
                    continue
                data = line[len("data:"):].strip()
                if data == "[DONE]":
                    break
                try:
                    obj = json.loads(data)
                except json.JSONDecodeError:
                    continue
                choices = obj.get("choices") or [{}]
                delta = (choices[0].get("delta") or {}).get("content")
                if delta:
                    yield delta


async def generate_campaign(audience: str, channel: str, goal: str) -> dict:
    """Draft a marketing campaign (subject + body + CTA) as strict JSON."""
    _require_key()
    payload = {
        "model": LLM_MODEL,
        "messages": [
            {"role": "system", "content": (
                "You are a restaurant marketing copywriter. Return STRICT JSON ONLY with "
                "keys: subject (string, <=80 chars), body (string, <=400 chars, friendly "
                "and on-brand for a casual upscale bistro called 'Jha Bistro'), cta "
                "(string, <=20 chars), estimated_reach (integer), estimated_revenue (integer)."
            )},
            {"role": "user", "content": (
                f"Draft a {channel} campaign for the audience '{audience}'. "
                f"The goal is: {goal}. Keep it punchy and action-oriented."
            )},
        ],
        "temperature": 0.7,
        "response_format": {"type": "json_object"},
    }
    async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
        r = await client.post(
            f"{LLM_API_BASE}/chat/completions", headers=_headers(), json=payload,
        )
        if r.status_code >= 400:
            raise RuntimeError(f"LLM error {r.status_code}: {r.text[:400]}")
        content = r.json()["choices"][0]["message"]["content"]

    parsed = parse_coo_json(content)
    if "subject" not in parsed:
        parsed = {"subject": "Your Jha Bistro Update", "body": content[:400], "cta": "Order Now",
                  "estimated_reach": 0, "estimated_revenue": 0}
    return parsed


# -------- Voice (Whisper STT + TTS) --------

async def transcribe_audio(file_obj) -> str:
    """Transcribe an uploaded audio file via Whisper (Groq free tier)."""
    _require_key()
    name = getattr(file_obj, "name", "audio.webm")
    data = file_obj.read() if hasattr(file_obj, "read") else bytes(file_obj)
    files = {"file": (name, data, "application/octet-stream")}
    form = {"model": STT_MODEL, "response_format": "json", "language": "en"}
    async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
        r = await client.post(
            f"{LLM_API_BASE}/audio/transcriptions",
            headers={"Authorization": f"Bearer {LLM_API_KEY}"},  # multipart sets its own Content-Type
            data=form, files=files,
        )
        if r.status_code >= 400:
            raise RuntimeError(f"STT error {r.status_code}: {r.text[:400]}")
        return r.json().get("text", "")


async def synthesize_speech(text: str, voice: str = "nova") -> bytes:
    """Text-to-speech via the provider's OpenAI-compatible /audio/speech.

    Groq's playai-tts uses its own voice names (e.g. 'Fritz-PlayAI') and may
    require a one-time terms acceptance in the Groq console. If the incoming
    voice isn't a provider voice, fall back to TTS_VOICE.
    """
    _require_key()
    v = voice if voice.endswith("-PlayAI") else TTS_VOICE
    payload = {
        "model": TTS_MODEL,
        "input": text[:4000],
        "voice": v,
        "response_format": "wav",
    }
    async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
        r = await client.post(
            f"{LLM_API_BASE}/audio/speech", headers=_headers(), json=payload,
        )
        if r.status_code >= 400:
            raise RuntimeError(
                f"TTS error {r.status_code}: {r.text[:300]}. "
                "Free TTS may need model terms accepted at console.groq.com."
            )
        return r.content

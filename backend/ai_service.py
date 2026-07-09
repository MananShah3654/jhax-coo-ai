"""
JhaPay AI COO - Claude Sonnet 4.5 powered AI brain.

Architecture (MCP-style, LLM never touches the DB):
  Frontend → AI Gateway → restaurant_context (via analytics.py) → Prompt
  Builder → Claude Sonnet 4.5 (streaming) → Response Formatter → UI.

The LLM is given a strict system prompt + the structured snapshot for
the current restaurant. It MUST reply in the executive "Decision Card"
format: STATUS / REASON / OPPORTUNITY / ACTION / EXPECTED IMPACT.
"""
from __future__ import annotations

import json
import os
import re
from typing import AsyncGenerator

from openai import AsyncOpenAI

from analytics import restaurant_context

# LLM config — any OpenAI-compatible endpoint (Groq by default). See backend/.env.
LLM_API_KEY  = os.environ.get("LLM_API_KEY", "")
LLM_API_BASE = os.environ.get("LLM_API_BASE", "https://api.groq.com/openai/v1")
LLM_MODEL    = os.environ.get("LLM_MODEL", "llama-3.3-70b-versatile")
STT_MODEL    = os.environ.get("STT_MODEL", "whisper-large-v3-turbo")
TTS_MODEL    = os.environ.get("TTS_MODEL", "playai-tts")
TTS_VOICE    = os.environ.get("TTS_VOICE", "Fritz-PlayAI")

_client = AsyncOpenAI(api_key=LLM_API_KEY, base_url=LLM_API_BASE)

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


async def stream_coo_reply(session_id: str, user_text: str) -> AsyncGenerator[str, None]:
    """Yield raw token strings as the model generates them (SSE-friendly)."""
    stream = await _client.chat.completions.create(
        model=LLM_MODEL,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": _wrap_user(user_text)},
        ],
        stream=True,
        temperature=0.3,
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
    resp = await _client.chat.completions.create(
        model=LLM_MODEL,
        messages=[
            {"role": "system", "content": (
                "You are a restaurant marketing copywriter. Return STRICT JSON ONLY with "
                "keys: subject (string, <=80 chars), body (string, <=400 chars, friendly "
                "and on-brand for a casual upscale bistro called 'Jha Bistro'), cta "
                "(string, <=20 chars), estimated_reach (integer), estimated_revenue (integer)."
            )},
            {"role": "user", "content": prompt},
        ],
        temperature=0.7,
    )
    buf = resp.choices[0].message.content or ""
    parsed = parse_coo_json(buf)
    if "subject" not in parsed:
        parsed = {"subject": "Your Jha Bistro Update", "body": buf[:400], "cta": "Order Now",
                  "estimated_reach": 0, "estimated_revenue": 0}
    return parsed


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

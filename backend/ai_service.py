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
import uuid
from typing import AsyncGenerator

from emergentintegrations.llm.chat import (
    LlmChat, UserMessage, TextDelta, StreamDone,
)
from emergentintegrations.llm.openai import OpenAISpeechToText, OpenAITextToSpeech

from analytics import restaurant_context

EMERGENT_KEY = os.environ["EMERGENT_LLM_KEY"]
MODEL_PROVIDER = "anthropic"
MODEL_NAME = "claude-sonnet-4-5-20250929"

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


def _new_chat(session_id: str) -> LlmChat:
    return LlmChat(
        api_key=EMERGENT_KEY,
        session_id=session_id,
        system_message=SYSTEM_PROMPT,
    ).with_model(MODEL_PROVIDER, MODEL_NAME)


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
    """Yield raw token strings as Claude generates them (SSE-friendly)."""
    chat = _new_chat(session_id or str(uuid.uuid4()))
    msg = UserMessage(text=_wrap_user(user_text))
    async for ev in chat.stream_message(msg):
        if isinstance(ev, TextDelta):
            yield ev.content
        elif isinstance(ev, StreamDone):
            break


async def generate_campaign(audience: str, channel: str, goal: str) -> dict:
    """Use Claude to draft a marketing campaign (subject + body + CTA)."""
    chat = LlmChat(
        api_key=EMERGENT_KEY,
        session_id=f"campaign_{uuid.uuid4()}",
        system_message=(
            "You are a restaurant marketing copywriter. Return STRICT JSON ONLY with "
            "keys: subject (string, <=80 chars), body (string, <=400 chars, friendly "
            "and on-brand for a casual upscale bistro called 'Jha Bistro'), cta "
            "(string, <=20 chars), estimated_reach (integer), estimated_revenue (integer)."
        ),
    ).with_model(MODEL_PROVIDER, MODEL_NAME)

    prompt = (
        f"Draft a {channel} campaign for the audience '{audience}'. "
        f"The goal is: {goal}. Keep it punchy and action-oriented."
    )
    buf = ""
    async for ev in chat.stream_message(UserMessage(text=prompt)):
        if isinstance(ev, TextDelta):
            buf += ev.content
        elif isinstance(ev, StreamDone):
            break
    parsed = parse_coo_json(buf)
    if "subject" not in parsed:
        parsed = {"subject": "Your Jha Bistro Update", "body": buf[:400], "cta": "Order Now",
                  "estimated_reach": 0, "estimated_revenue": 0}
    return parsed


# -------- Voice (Whisper + TTS) --------

def _stt() -> OpenAISpeechToText:
    return OpenAISpeechToText(api_key=EMERGENT_KEY)


def _tts() -> OpenAITextToSpeech:
    return OpenAITextToSpeech(api_key=EMERGENT_KEY)


async def transcribe_audio(file_obj) -> str:
    resp = await _stt().transcribe(file=file_obj, model="whisper-1",
                                   response_format="json", language="en")
    return resp.text


async def synthesize_speech(text: str, voice: str = "nova") -> bytes:
    # tts-1 is fast and good enough for streaming reply playback
    return await _tts().generate_speech(
        text=text[:4000], model="tts-1", voice=voice, response_format="mp3"
    )

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

SYSTEM_PROMPT = """You are JhaPay AI COO™ - a digital Chief Operating Officer for a restaurant owner.

You are NOT ChatGPT. You are NOT a general assistant. You are the owner's executive
restaurant operations partner.

ALLOWED TOPICS ONLY: sales, revenue, orders, customers, menu performance, marketing,
loyalty, payments, tips, branches/locations, staff, inventory, forecasting, promotions,
campaigns, restaurant operations and growth.

If the user asks anything unrelated (politics, news, general knowledge, coding, etc.)
reply EXACTLY:
"I am JhaPay AI COO and can assist only with restaurant operations, revenue, customers,
marketing, loyalty, payments, performance, and growth."

REPLY FORMAT - ALWAYS use this structured "Decision Card" format. Return STRICT JSON
ONLY (no prose, no markdown fences) with the following schema:

{
  "status":            "<short headline e.g. 'Sales down 11% this week'>",
  "reason":            "<1-2 sentences on the why, grounded in the data provided>",
  "opportunity":       "<1-2 sentences on the upside / what can be unlocked>",
  "action":            "<imperative next action, max 1 sentence>",
  "expected_impact":   "<concrete number like '+$1,800/week' or '+12% repeat visits'>",
  "metrics":           [{"label": "<short>", "value": "<formatted>"}],   // 0-4 items
  "actions": [   // 0-3 one-click executable actions the UI will render as buttons
     {"id":"launch_campaign","label":"Launch Reactivation Campaign","kind":"campaign"},
     {"id":"share_report","label":"Share Report","kind":"share"},
     {"id":"view_details","label":"View Branch Detail","kind":"navigate","target":"/branches"}
  ]
}

Action `kind` MUST be one of: "campaign", "share", "navigate", "notify", "promotion", "report".
For "navigate" actions, target can be: /home, /chat, /branches, /customers, /menu, /marketing, /forecast, /manager.

Rules:
- Be decisive. Be executive. Never hedge with "it depends".
- Always ground every number in the RESTAURANT_CONTEXT provided in the user turn.
- Do NOT invent metrics that aren't derivable from the context.
- Be concise. Each field is at most 2 sentences.
- Currency: USD with $ sign and thousands separator (e.g. $12,480).
- Tone: humble, professional, action-oriented, data-driven.
- NEVER output anything outside the JSON object.
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

"""WhatsApp Business Cloud API — audience resolution + broadcast sending.

Configuration (backend/.env):
    WHATSAPP_BUSINESS_TOKEN   >>> FILL THIS IN <<<
    WHATSAPP_PHONE_NUMBER_ID  >>> FILL THIS IN <<<

Until BOTH are set, is_configured() is False and every send path refuses with a
"WhatsApp not configured" result. Nothing here ever reports a success it didn't
get from Meta.

REAL LIMITATION — the 24-hour customer service window:
    Meta only allows free-form messages to a user who messaged your business
    within the last 24 hours. Outside that window a message MUST use a
    pre-approved message template, submitted and approved in WhatsApp Manager.
    A restaurant broadcasting a promo to lapsed customers is, by definition,
    outside that window for nearly all of them, so those sends will be REJECTED
    with error 131047 ("Message failed to send because more than 24 hours have
    passed since the customer last replied").

    We send free-form text and surface Meta's rejection verbatim rather than
    pretending otherwise. Templates are not built yet: doing it properly needs a
    template registered in WhatsApp Manager, its exact name/language, and its
    variable mapping — none of which can be invented here.
"""
from __future__ import annotations

import logging
import os
import re
from typing import Dict, List

import httpx

logger = logging.getLogger("jhapay.whatsapp")

_GRAPH_VERSION = os.environ.get("WHATSAPP_GRAPH_VERSION", "v21.0")
_TIMEOUT = 20.0

# A country code is only used when the operator explicitly declares one. We never
# guess: a bare 10-digit number belongs to a dozen different countries, and
# guessing wrong messages a stranger.
_DEFAULT_CC = (os.environ.get("WHATSAPP_DEFAULT_COUNTRY_CODE", "") or "").strip().lstrip("+")


def _token() -> str:
    return (os.environ.get("WHATSAPP_BUSINESS_TOKEN", "") or "").strip()


def _phone_id() -> str:
    return (os.environ.get("WHATSAPP_PHONE_NUMBER_ID", "") or "").strip()


def _is_placeholder(v: str) -> bool:
    """True for the shipped >>> FILL THIS IN <<< markers and obvious stand-ins."""
    low = v.lower()
    return (not v) or ("fill" in low and "in" in low) or low in {
        "your_token_here", "changeme", "todo", "xxx",
    }


def is_configured() -> bool:
    """Both credentials present AND not the placeholder text."""
    return not _is_placeholder(_token()) and not _is_placeholder(_phone_id())


def config_status() -> Dict:
    """What's missing, for an honest "not configured" UI state."""
    missing = []
    if _is_placeholder(_token()):
        missing.append("WHATSAPP_BUSINESS_TOKEN")
    if _is_placeholder(_phone_id()):
        missing.append("WHATSAPP_PHONE_NUMBER_ID")
    return {
        "configured": not missing,
        "missing": missing,
        "hint": (
            "Set these in backend/.env from Meta -> WhatsApp -> API Setup, then "
            "restart the backend."
            if missing else ""
        ),
    }


def to_e164(raw: str | None) -> str | None:
    """Normalise to +<digits>, or None when it can't be done without guessing.

    Rules:
      * already "+..."            -> keep the digits
      * "00" international prefix -> swap for "+"
      * otherwise                 -> only usable if the operator declared
                                     WHATSAPP_DEFAULT_COUNTRY_CODE
    Returning None (skipped) is always better than inventing a country code and
    messaging the wrong person. E.164 allows at most 15 digits.
    """
    if not raw:
        return None
    s = re.sub(r"[^\d+]", "", str(raw).strip())
    if not s:
        return None
    if s.startswith("+"):
        digits = s[1:]
    elif s.startswith("00"):
        digits = s[2:]
    elif _DEFAULT_CC:
        digits = _DEFAULT_CC + s.lstrip("0")
    else:
        return None
    if not digits.isdigit() or not (8 <= len(digits) <= 15):
        return None
    return "+" + digits


def resolve_audience(customers: List[Dict], audience: str) -> Dict:
    """Who in `customers` is reachable on WhatsApp for this segment.

    Returns {audience, matched, recipients, unreachable, duplicates} where
    `recipients` is deduped E.164 numbers. Segment names match the existing
    customer tags (vip / at_risk / new); "all" means every customer.
    """
    seg = (audience or "").strip().lower()
    if seg in ("", "all"):
        matched = list(customers)
    else:
        matched = [c for c in customers if seg in (c.get("tags") or [])]

    recipients: List[str] = []
    seen: set[str] = set()
    unreachable = 0
    duplicates = 0
    for c in matched:
        e164 = to_e164(c.get("phone"))
        if not e164:
            unreachable += 1          # no number, or not normalisable safely
            continue
        if e164 in seen:
            duplicates += 1           # same number on two customer records
            continue
        seen.add(e164)
        recipients.append(e164)
    return {
        "audience": seg or "all",
        "matched": len(matched),
        "recipients": recipients,
        "unreachable": unreachable,
        "duplicates": duplicates,
    }


def _send_one(client: httpx.Client, to: str, body: str) -> Dict:
    """POST one text message. Returns Meta's verdict, never a guess."""
    try:
        r = client.post(
            f"https://graph.facebook.com/{_GRAPH_VERSION}/{_phone_id()}/messages",
            json={
                "messaging_product": "whatsapp",
                "recipient_type": "individual",
                "to": to,
                "type": "text",
                "text": {"preview_url": True, "body": body},
            },
        )
        payload = r.json() if r.content else {}
    except Exception as exc:
        return {"to": to, "ok": False, "error": f"{type(exc).__name__}: {exc}"}
    if r.status_code >= 400:
        err = (payload or {}).get("error") or {}
        return {
            "to": to,
            "ok": False,
            "status": r.status_code,
            "code": err.get("code"),
            "error": err.get("message") or f"HTTP {r.status_code}",
            # 131047 = outside the 24h window, template required.
            "needs_template": err.get("code") == 131047,
        }
    return {
        "to": to,
        "ok": True,
        "status": r.status_code,
        "message_id": ((payload.get("messages") or [{}])[0]).get("id"),
    }


def send_broadcast(recipients: List[str], body: str,
                   banner_url: str | None = None) -> Dict:
    """Send `body` to each recipient. Reports exactly what Meta returned.

    A banner is appended as a link rather than uploaded as an image: sending
    media needs either a media_id from Meta's upload endpoint or a publicly
    fetchable URL, and preview_url lets WhatsApp unfurl it. `sent` counts only
    messages Meta ACCEPTED — a refusal is never counted as sent.
    """
    if not is_configured():
        return {
            "ok": False,
            "configured": False,
            "sent": 0,
            "failed": 0,
            "results": [],
            "error": "WhatsApp not configured",
            **config_status(),
        }
    if not recipients:
        return {"ok": False, "configured": True, "sent": 0, "failed": 0,
                "results": [], "error": "No reachable recipients in this segment."}

    text = body if not banner_url else f"{body}\n\n{banner_url}"
    results: List[Dict] = []
    headers = {"Authorization": f"Bearer {_token()}",
               "Content-Type": "application/json"}
    with httpx.Client(timeout=_TIMEOUT, headers=headers) as client:
        for to in recipients:
            results.append(_send_one(client, to, text))

    sent = sum(1 for r in results if r.get("ok"))
    failed = len(results) - sent
    needs_template = sum(1 for r in results if r.get("needs_template"))
    return {
        "ok": sent > 0,
        "configured": True,
        "sent": sent,
        "failed": failed,
        "results": results,
        "needs_template": needs_template,
        "error": None if sent else (results[0].get("error") if results else None),
    }

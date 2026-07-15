"""
Phone OTP via Twilio Verify + Firebase custom-token minting.

Replaces Firebase's built-in Phone Auth (which needs Blaze billing) with
Twilio's Verify API for sending/checking the SMS OTP. On a verified code we mint
a Firebase **custom token** with the Admin SDK, so the frontend finishes a normal
Firebase session via signInWithCustomToken(). Everything downstream — ID-token
verification, /me, onboarding, the PIN unlock — stays exactly the same.

Config (backend/.env, loaded by server.py's load_dotenv — same pattern as the
Firebase Admin credentials in auth.py):
    TWILIO_ACCOUNT_SID
    TWILIO_AUTH_TOKEN
    TWILIO_VERIFY_SERVICE_SID
"""
from __future__ import annotations

import logging
import os
import threading

from fastapi import APIRouter, HTTPException
from firebase_admin import auth as fb_auth
from pydantic import BaseModel, Field

from auth import _firebase_app  # reuse the lazy, thread-safe Admin-SDK initializer

logger = logging.getLogger("jhapay.twilio_auth")

# Same /api prefix as the main router in server.py → /api/auth/send-otp etc.
router = APIRouter(prefix="/api", tags=["phone-auth"])

_client_lock = threading.Lock()
_twilio_client = None
_verify_sid: str | None = None


def _twilio():
    """Lazily build a Twilio REST client from env (thread-safe, like _firebase_app)."""
    global _twilio_client, _verify_sid
    if _twilio_client is not None:
        return _twilio_client, _verify_sid
    with _client_lock:
        if _twilio_client is not None:
            return _twilio_client, _verify_sid
        sid = os.environ.get("TWILIO_ACCOUNT_SID", "").strip()
        token = os.environ.get("TWILIO_AUTH_TOKEN", "").strip()
        verify_sid = os.environ.get("TWILIO_VERIFY_SERVICE_SID", "").strip()
        if not (sid and token and verify_sid):
            raise HTTPException(
                status_code=503,
                detail="Phone OTP is not configured on the server (set "
                       "TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN, TWILIO_VERIFY_SERVICE_SID).",
            )
        try:
            from twilio.rest import Client
        except ImportError as exc:  # pragma: no cover
            raise HTTPException(
                status_code=503,
                detail="Twilio SDK not installed on the server (pip install twilio).",
            ) from exc
        _twilio_client = Client(sid, token)
        _verify_sid = verify_sid
        logger.info("Twilio Verify client initialized.")
        return _twilio_client, _verify_sid


# -------------------- Schemas --------------------
class SendOtpRequest(BaseModel):
    phone_number: str = Field(..., description="E.164 phone, e.g. +14155551234")


class SendOtpResponse(BaseModel):
    status: str  # Twilio verification status, e.g. "pending"
    to: str      # normalized E.164 number the code was sent to


class VerifyOtpRequest(BaseModel):
    phone_number: str
    code: str


class VerifyOtpResponse(BaseModel):
    token: str  # Firebase custom token → frontend calls signInWithCustomToken()


def _normalize_e164(phone: str) -> str:
    """Basic E.164 normalization/validation (Twilio requires this format)."""
    phone = (phone or "").strip().replace(" ", "").replace("-", "")
    if not (phone.startswith("+") and phone[1:].isdigit() and 8 <= len(phone) <= 16):
        raise HTTPException(
            400, "Enter a valid phone number with country code, e.g. +14155551234."
        )
    return phone


# -------------------- Endpoints --------------------
# Plain `def` (not async): the Twilio SDK does blocking HTTP, so FastAPI runs
# these in its threadpool instead of blocking the event loop.
@router.post("/auth/send-otp", response_model=SendOtpResponse)
def send_otp(req: SendOtpRequest) -> SendOtpResponse:
    """Send an SMS OTP to the phone number via Twilio Verify."""
    phone = _normalize_e164(req.phone_number)
    client, verify_sid = _twilio()
    try:
        v = client.verify.v2.services(verify_sid).verifications.create(
            to=phone, channel="sms"
        )
    except Exception as exc:
        logger.warning("Twilio send-otp failed for %s: %s", phone, exc)
        raise HTTPException(status_code=502, detail="Couldn't send the code. Try again.") from exc
    return SendOtpResponse(status=v.status, to=phone)


@router.post("/auth/verify-otp", response_model=VerifyOtpResponse)
def verify_otp(req: VerifyOtpRequest) -> VerifyOtpResponse:
    """Check the OTP with Twilio; on success mint a Firebase custom token."""
    phone = _normalize_e164(req.phone_number)
    code = (req.code or "").strip()
    if not code.isdigit():
        raise HTTPException(400, "Enter the numeric code from the SMS.")

    client, verify_sid = _twilio()
    try:
        check = client.verify.v2.services(verify_sid).verification_checks.create(
            to=phone, code=code
        )
    except Exception as exc:
        logger.warning("Twilio verify-otp failed for %s: %s", phone, exc)
        raise HTTPException(status_code=502, detail="Couldn't verify the code. Try again.") from exc

    if check.status != "approved":
        raise HTTPException(status_code=401, detail="Incorrect or expired code.")

    # Ensure the Admin SDK is initialized, then resolve (or create) the Firebase
    # user for this phone so the uid — and therefore the local Postgres user row —
    # is stable across logins. The resulting ID token carries phone_number, which
    # auth.get_current_user already reads.
    _firebase_app()
    try:
        user = fb_auth.get_user_by_phone_number(phone)
    except fb_auth.UserNotFoundError:
        user = fb_auth.create_user(phone_number=phone)
    except Exception as exc:
        logger.error("Firebase user lookup/create failed for %s: %s", phone, exc)
        raise HTTPException(status_code=500, detail="Auth service error. Try again.") from exc

    token = fb_auth.create_custom_token(user.uid)  # bytes
    return VerifyOtpResponse(token=token.decode("utf-8"))

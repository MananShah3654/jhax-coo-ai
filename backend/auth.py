"""
Firebase ID-token verification + local-user resolution.

`get_current_user` is a FastAPI dependency: it reads the Bearer token from the
Authorization header, verifies it with the Firebase Admin SDK, then looks up (or
creates) the matching row in the local Postgres `users` table and returns it.

Configure credentials via FIREBASE_CREDENTIALS (path to a service-account JSON)
or GOOGLE_APPLICATION_CREDENTIALS (Application Default Credentials).
"""
from __future__ import annotations

import logging
import os
import threading

import firebase_admin
from firebase_admin import auth as fb_auth
from firebase_admin import credentials
from fastapi import Depends, Header, HTTPException
from sqlalchemy.orm import Session

from database import User, get_db, get_or_create_user

logger = logging.getLogger("jhapay.auth")

_init_lock = threading.Lock()
_app: firebase_admin.App | None = None


def _firebase_app() -> firebase_admin.App:
    """Initialize the Firebase Admin app once (thread-safe, lazy)."""
    global _app
    if _app is not None:
        return _app
    with _init_lock:
        if _app is not None:
            return _app
        if firebase_admin._apps:  # already initialized elsewhere
            _app = firebase_admin.get_app()
            return _app
        cred_path = os.environ.get("FIREBASE_CREDENTIALS", "").strip()
        try:
            if cred_path:
                cred = credentials.Certificate(cred_path)
            else:
                # Falls back to GOOGLE_APPLICATION_CREDENTIALS / metadata server.
                cred = credentials.ApplicationDefault()
            _app = firebase_admin.initialize_app(cred)
            logger.info("Firebase Admin initialized (%s)",
                        "service account" if cred_path else "application default")
        except Exception as exc:
            logger.error("Firebase Admin init failed: %s", exc)
            raise HTTPException(
                status_code=503,
                detail="Firebase auth is not configured on the server "
                       "(set FIREBASE_CREDENTIALS).",
            ) from exc
        return _app


def verify_firebase_token(id_token: str) -> dict:
    """Verify a Firebase ID token and return its decoded claims."""
    _firebase_app()
    try:
        return fb_auth.verify_id_token(id_token)
    except Exception as exc:
        logger.warning("Firebase token verification failed: %s", exc)
        raise HTTPException(status_code=401, detail="Invalid or expired token") from exc


def get_current_user(
    authorization: str | None = Header(default=None),
    db: Session = Depends(get_db),
) -> User:
    """FastAPI dependency: verify the Bearer token and return the local user."""
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(status_code=401, detail="Missing Bearer token")
    id_token = authorization.split(" ", 1)[1].strip()
    claims = verify_firebase_token(id_token)

    return get_or_create_user(
        db,
        firebase_uid=claims["uid"],
        email=claims.get("email"),
        phone_number=claims.get("phone_number"),
        name=claims.get("name"),
    )

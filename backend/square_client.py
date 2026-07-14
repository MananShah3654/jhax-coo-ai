"""
Reusable Square Connect REST helpers (Team API + Labor API + Locations).

Talks raw REST over httpx — same auth/host/pagination/retry pattern as
seed_square_sandbox.py, generalized so sync_square.py can reuse it. Never
hardcodes a token: reads SQUARE_ACCESS_TOKEN / SQUARE_ENVIRONMENT from the
environment (the caller runs load_dotenv() first).

Square-Version is pinned to match the rest of the codebase.
"""
from __future__ import annotations

import os
import time

import httpx

SQUARE_VERSION = "2024-10-17"


def _token() -> str:
    token = os.environ.get("SQUARE_ACCESS_TOKEN", "").strip()
    if not token:
        raise SystemExit("SQUARE_ACCESS_TOKEN is empty (set it in backend/.env)")
    return token


def _base() -> str:
    env = os.environ.get("SQUARE_ENVIRONMENT", "sandbox").lower()
    return (
        "https://connect.squareupsandbox.com"
        if env == "sandbox"
        else "https://connect.squareup.com"
    )


def _headers() -> dict:
    return {
        "Authorization": f"Bearer {_token()}",
        "Square-Version": SQUARE_VERSION,
        "Content-Type": "application/json",
    }


def _request(method: str, path: str, *, json: dict | None = None) -> dict:
    """Issue one request with retry on 429/500/503 (matches the seed script)."""
    url = f"{_base()}{path}"
    for attempt in range(3):
        r = httpx.request(
            method, url, headers=_headers(), json=json, timeout=20.0
        )
        if r.status_code < 300:
            return r.json()
        if r.status_code in (429, 500, 503) and attempt < 2:
            time.sleep(1.5 * (attempt + 1))
            continue
        raise httpx.HTTPStatusError(
            f"{method} {path} -> {r.status_code}: {r.text[:300]}",
            request=r.request, response=r,
        )
    raise RuntimeError(f"{method} {path} exhausted retries")


def _get(path: str) -> dict:
    return _request("GET", path)


def _post(path: str, body: dict) -> dict:
    return _request("POST", path, json=body)


# ---------------- Locations ----------------
def list_locations() -> list[dict]:
    """All locations on the account."""
    return _get("/v2/locations").get("locations") or []


# ---------------- Team API (employees) ----------------
def search_team_members(active_only: bool = True) -> list[dict]:
    """All team members, following the cursor. Employee 'details' live here."""
    members: list[dict] = []
    cursor: str | None = None
    status_filter = {"status": "ACTIVE"} if active_only else {}
    for _ in range(200):  # hard cap so a bad cursor can't loop forever
        body: dict = {"limit": 200, "query": {"filter": status_filter}}
        if cursor:
            body["cursor"] = cursor
        data = _post("/v2/team-members/search", body)
        members.extend(data.get("team_members") or [])
        cursor = data.get("cursor")
        if not cursor:
            break
    return members


# ---------------- Labor API (clock-in / clock-out) ----------------
def search_shifts(location_ids: list[str], start_at: str, end_at: str) -> list[dict]:
    """Shifts whose clock-in (start_at) falls in [start_at, end_at], paginated.

    start_at / end_at are RFC-3339 strings. clock-in = shift['start_at'],
    clock-out = shift['end_at'] (absent while a shift is still open).
    """
    shifts: list[dict] = []
    cursor: str | None = None
    query_filter: dict = {
        "start": {"start_at": start_at, "end_at": end_at},
    }
    if location_ids:
        query_filter["location_ids"] = location_ids
    for _ in range(500):
        body: dict = {"limit": 200, "query": {"filter": query_filter}}
        if cursor:
            body["cursor"] = cursor
        data = _post("/v2/labor/shifts/search", body)
        shifts.extend(data.get("shifts") or [])
        cursor = data.get("cursor")
        if not cursor:
            break
    return shifts

"""
Sync Square staff + clock-in/clock-out data into Postgres.

Pulls team members (Square Team API) and their labor shifts (Square Labor API)
and UPSERTS them into the `team_members` / `labor_shifts` tables, keyed by
(owner_id, square_id) so re-runs update in place instead of duplicating.

This is the entrypoint the OS scheduler runs every 15 days. It is fully
standalone (does not need the API process running).

Run manually:
    python sync_square.py                 # real sync
    python sync_square.py --dry-run       # fetch + report counts, write nothing
    python sync_square.py --lookback-days 30

Schedule every 15 days:
  Windows (Task Scheduler):
    schtasks /create /tn "JhaPay Square Sync" /sc DAILY /mo 15 ^
      /tr "\"C:\\Path\\to\\python.exe\" \"C:\\...\\backend\\sync_square.py\"" /st 02:00
    schtasks /query /tn "JhaPay Square Sync"      # verify
    schtasks /run   /tn "JhaPay Square Sync"      # fire once now
  Linux (crontab -e):
    0 2 */15 * *  /usr/bin/python3 /path/to/backend/sync_square.py

Config (backend/.env):
    SQUARE_ACCESS_TOKEN=...          # needs EMPLOYEES_READ + TIMECARDS_READ scopes
    SQUARE_ENVIRONMENT=sandbox       # or production
    SQUARE_SYNC_OWNER_ID=1           # local owner (users.id) that receives the data
    SQUARE_SHIFT_LOOKBACK_DAYS=20    # overlap buffer over the 15-day cadence
"""
from __future__ import annotations

import argparse
import datetime as dt
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).with_name(".env"))

import os  # noqa: E402  (after load_dotenv so env is populated)

import square_client as sq  # noqa: E402
from database import (  # noqa: E402
    Employee, Restaurant, SessionLocal, Shift, User,
)


# ---------------- helpers ----------------
def _parse_dt(value: str | None) -> dt.datetime | None:
    """RFC-3339 string -> tz-aware datetime (None if absent, e.g. open shift)."""
    if not value:
        return None
    parsed = dt.datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=dt.timezone.utc)
    return parsed


def _resolve_owner_id(session) -> int:
    """The local owner (users.id) that receives the synced data.

    SQUARE_SYNC_OWNER_ID if set, else the single/first user. Aborts if neither
    resolves to a real row so we never write orphaned rows.
    """
    env_id = os.environ.get("SQUARE_SYNC_OWNER_ID", "").strip()
    if env_id:
        user = session.get(User, int(env_id))
        if user is None:
            raise SystemExit(f"SQUARE_SYNC_OWNER_ID={env_id} matches no users row")
        return user.id
    user = session.query(User).order_by(User.id).first()
    if user is None:
        raise SystemExit("No users exist yet; create an owner before syncing.")
    return user.id


def _first_location_id(member: dict) -> str | None:
    loc_ids = (member.get("assigned_locations") or {}).get("location_ids") or []
    return loc_ids[0] if loc_ids else None


def _tips(shift: dict) -> float | None:
    money = shift.get("declared_cash_tip_money")
    if not money or money.get("amount") is None:
        return None
    return round(money["amount"] / 100.0, 2)  # Square amounts are in cents


def _upsert(session, model, owner_id: int, square_id: str, fields: dict, *,
            dry_run: bool) -> str:
    """Update the (owner_id, square_id) row or insert it. Returns 'updated' or
    'created'. In dry-run, classifies but writes nothing."""
    row = (session.query(model)
           .filter_by(owner_id=owner_id, square_id=square_id)
           .one_or_none())
    if row is None:
        if not dry_run:
            session.add(model(owner_id=owner_id, square_id=square_id, **fields))
        return "created"
    if not dry_run:
        for key, val in fields.items():
            setattr(row, key, val)
    return "updated"


# ---------------- main ----------------
def sync(dry_run: bool = False, lookback_days: int | None = None) -> None:
    if lookback_days is None:
        lookback_days = int(os.environ.get("SQUARE_SHIFT_LOOKBACK_DAYS", "20"))

    mode = "DRY RUN (no writes)" if dry_run else "LIVE"
    print(f"Square sync [{mode}] env={os.environ.get('SQUARE_ENVIRONMENT', 'sandbox')} "
          f"lookback={lookback_days}d")

    locations = sq.list_locations()
    location_ids = [l["id"] for l in locations]
    print(f"Locations: {len(location_ids)}")

    with SessionLocal() as session:
        owner_id = _resolve_owner_id(session)
        print(f"Owner (users.id): {owner_id}")

        # ---- Restaurants (auto-synced from Square locations) ----
        # One local restaurant per Square location, keyed by square_location_id,
        # so every employee reliably maps to a restaurant with no manual setup.
        # Manually-created restaurants (no square_location_id) are left untouched.
        loc_to_restaurant: dict[str, str] = {}
        rest_stats = {"created": 0, "updated": 0}
        for loc in locations:
            addr = loc.get("address") or {}
            fields = {
                "name": loc.get("name") or "Square Location",
                "city": addr.get("locality"),
                "address": addr.get("address_line_1"),
                "phone": loc.get("phone_number"),
            }
            existing = (session.query(Restaurant)
                        .filter_by(owner_id=owner_id, square_location_id=loc["id"])
                        .one_or_none())
            if existing is None:
                rest_stats["created"] += 1
                if not dry_run:
                    r = Restaurant(owner_id=owner_id,
                                   square_location_id=loc["id"], **fields)
                    session.add(r)
                    session.flush()  # assign r.id for the FK map below
                    loc_to_restaurant[loc["id"]] = r.id
            else:
                rest_stats["updated"] += 1
                if not dry_run:
                    for key, val in fields.items():
                        setattr(existing, key, val)
                loc_to_restaurant[loc["id"]] = existing.id
        print(f"Restaurants: {rest_stats['created']} created, "
              f"{rest_stats['updated']} updated ({len(locations)} locations)")

        # If there's exactly one location, employees with no explicit assignment
        # (e.g. Square's ALL_LOCATIONS) still belong to it.
        default_loc = location_ids[0] if len(location_ids) == 1 else None

        # ---- Employees (Team API) ----
        members = sq.search_team_members(active_only=True)
        emp_stats = {"created": 0, "updated": 0}
        for m in members:
            loc_id = _first_location_id(m) or default_loc
            result = _upsert(session, Employee, owner_id, m["id"], {
                "square_location_id": loc_id,
                "restaurant_id": loc_to_restaurant.get(loc_id),
                "given_name": m.get("given_name"),
                "family_name": m.get("family_name"),
                "email": m.get("email_address"),
                "phone": m.get("phone_number"),
                "status": m.get("status", "ACTIVE"),
                "is_owner": bool(m.get("is_owner", False)),
            }, dry_run=dry_run)
            emp_stats[result] += 1
        if not dry_run:
            session.flush()  # so shift FK lookups below see this run's inserts
        print(f"Employees: {emp_stats['created']} created, "
              f"{emp_stats['updated']} updated ({len(members)} fetched)")

        # square team-member id -> local employee id (for shift FK resolution)
        member_to_employee = {
            e.square_id: e.id
            for e in session.query(Employee).filter_by(owner_id=owner_id).all()
        }

        # ---- Shifts (Labor API) ----
        end_at = dt.datetime.now(dt.timezone.utc)
        start_at = end_at - dt.timedelta(days=lookback_days)
        shifts = sq.search_shifts(
            location_ids, start_at.isoformat(), end_at.isoformat()
        )
        shift_stats = {"created": 0, "updated": 0, "skipped": 0}
        for s in shifts:
            tm_id = s.get("team_member_id") or s.get("employee_id")
            employee_id = member_to_employee.get(tm_id)
            if employee_id is None:
                # Shift for a team member we didn't sync (e.g. inactive) — skip.
                shift_stats["skipped"] += 1
                continue
            loc_id = s.get("location_id")
            result = _upsert(session, Shift, owner_id, s["id"], {
                "employee_id": employee_id,
                "square_team_member_id": tm_id,
                "square_location_id": loc_id,
                "restaurant_id": loc_to_restaurant.get(loc_id),
                "clock_in": _parse_dt(s.get("start_at")),
                "clock_out": _parse_dt(s.get("end_at")),
                "status": s.get("status", "OPEN"),
                "declared_tips": _tips(s),
            }, dry_run=dry_run)
            shift_stats[result] += 1
        print(f"Shifts: {shift_stats['created']} created, "
              f"{shift_stats['updated']} updated, {shift_stats['skipped']} skipped "
              f"({len(shifts)} fetched)")

        if dry_run:
            session.rollback()
            print("Dry run complete - nothing written.")
        else:
            session.commit()
            print("Sync committed.")


def main() -> None:
    parser = argparse.ArgumentParser(description="Sync Square staff + shifts to Postgres.")
    parser.add_argument("--dry-run", action="store_true",
                        help="Fetch and report counts without writing.")
    parser.add_argument("--lookback-days", type=int, default=None,
                        help="Override SQUARE_SHIFT_LOOKBACK_DAYS for the shift window.")
    args = parser.parse_args()
    sync(dry_run=args.dry_run, lookback_days=args.lookback_days)


if __name__ == "__main__":
    main()

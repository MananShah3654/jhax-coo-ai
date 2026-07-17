"""
Seed dummy payroll data (team_members + labor_shifts) for local testing.

Adds a realistic staff roster (chefs, cashiers, sweeper, servers, manager) with
payroll attributes (hourly rate, tax declared, advance payment) and a set of
shifts covering different scenarios (with/without break, half-day, 10-min break,
open "on shift", etc.).

Rows use synthetic square_ids (DUMMY_TM_* / DUMMY_SH_*) so they never collide
with real Square-synced data, and re-running deletes+reinserts them (idempotent).

    python seed_payroll_dummy.py
"""
from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).with_name(".env"))

from database import (  # noqa: E402
    Employee, Order, Restaurant, SessionLocal, Shift, User, init_db,
)

# Display times in IST so "8am" shows as 8am for the user's browser.
IST = timezone(timedelta(hours=5, minutes=30))
OWNER_ID = int(os.environ.get("SQUARE_SYNC_OWNER_ID", "1"))

# (square_id, given, family, title, hourly_rate, tax_declared,
#  advance_taken, advance_amount, advance_days_ago)
EMPLOYEES = [
    ("DUMMY_TM_01", "Marcus", "Bennett", "chef",    26.0, True,  True,  500.0, 10),
    ("DUMMY_TM_02", "Elena",  "Rossi",   "chef",    25.0, True,  False, None,  None),
    ("DUMMY_TM_03", "Priya",  "Patel",   "cashier", 16.5, True,  False, None,  None),
    ("DUMMY_TM_04", "Tom",    "Nguyen",  "cashier", 16.0, False, True,  200.0, 5),
    ("DUMMY_TM_05", "Raj",    "Sharma",  "sweeper", 14.0, False, False, None,  None),
    ("DUMMY_TM_06", "Sarah",  "Khan",    "manager", 32.0, True,  False, None,  None),
    ("DUMMY_TM_07", "Alex",   "Carter",  "server",  12.5, True,  True,  150.0, 3),
    ("DUMMY_TM_08", "Jordan", "Lee",     "server",  12.0, False, False, None,  None),
    ("DUMMY_TM_09", "Mia",    "Garcia",  "server",  12.5, True,  False, None,  None),
    ("DUMMY_TM_10", "Leo",    "Martins", "server",  12.0, False, True,  100.0, 7),
    ("DUMMY_TM_11", "Nina",   "Okafor",  "server",  13.0, True,  False, None,  None),
]

# (square_id, emp_square_id, day_offset, in_hm, out_hm|None, break_hours,
#  meal_taken, status, declared_tips, late_clockin, missed_clockin)
#  day_offset: 0=today, 1=yesterday...
SHIFTS = [
    # Marcus: clock in 8:00am, clock out 4:30pm, took a 0.5h break.
    ("DUMMY_SH_01", "DUMMY_TM_01", 1, (8, 0),  (16, 30), 0.5,  True,  "CLOSED", 0.0,   False, False),
    # Elena: no break, worked a full 9 hours (8:00–17:00) -> 1h overtime.
    ("DUMMY_SH_02", "DUMMY_TM_02", 1, (8, 0),  (17, 0),  0.0,  False, "CLOSED", 0.0,   False, False),
    # Priya: half day (9:00–13:00 = 4h).
    ("DUMMY_SH_03", "DUMMY_TM_03", 1, (9, 0),  (13, 0),  0.0,  False, "CLOSED", 0.0,   False, False),
    # Tom: 10-minute break (0.17h), clocked in LATE.
    ("DUMMY_SH_04", "DUMMY_TM_04", 1, (9, 0),  (17, 0),  0.17, False, "CLOSED", 0.0,   True,  False),
    # Sarah (manager): long day with a 1h lunch -> 1h overtime.
    ("DUMMY_SH_05", "DUMMY_TM_06", 1, (8, 0),  (18, 0),  1.0,  True,  "CLOSED", 0.0,   False, False),
    # Raj (sweeper): early half day.
    ("DUMMY_SH_06", "DUMMY_TM_05", 1, (6, 0),  (10, 0),  0.0,  False, "CLOSED", 0.0,   False, False),
    # Servers with tips.
    ("DUMMY_SH_07", "DUMMY_TM_07", 1, (11, 0), (19, 0),  0.5,  True,  "CLOSED", 85.5,  False, False),
    ("DUMMY_SH_08", "DUMMY_TM_08", 1, (12, 0), (20, 0),  0.5,  True,  "CLOSED", 92.0,  False, False),
    ("DUMMY_SH_09", "DUMMY_TM_09", 2, (10, 0), (15, 0),  0.25, False, "CLOSED", 60.0,  True,  False),  # late
    ("DUMMY_SH_10", "DUMMY_TM_10", 2, (17, 0), (23, 0),  0.5,  True,  "CLOSED", 110.0, False, False),
    ("DUMMY_SH_11", "DUMMY_TM_11", 2, (16, 0), (22, 0),  0.33, True,  "CLOSED", 78.0,  False, False),
    # Marcus second day: 8:00–18:00 with 1h lunch -> 9h -> 1h overtime.
    ("DUMMY_SH_12", "DUMMY_TM_01", 2, (8, 0),  (18, 0),  1.0,  True,  "CLOSED", 0.0,   False, False),
    # Currently on shift (clocked in, not out yet).
    ("DUMMY_SH_13", "DUMMY_TM_02", 0, (8, 0),  None,     0.0,  False, "OPEN",   0.0,   False, False),
    ("DUMMY_SH_14", "DUMMY_TM_07", 0, (11, 0), None,     0.0,  False, "OPEN",   0.0,   False, False),
    # Missed clock-ins (scheduled but no-show).
    ("DUMMY_SH_15", "DUMMY_TM_08", 1, (9, 0),  None,     0.0,  False, "MISSED", 0.0,   False, True),
    ("DUMMY_SH_16", "DUMMY_TM_10", 1, (17, 0), None,     0.0,  False, "MISSED", 0.0,   False, True),
]


def _pick_restaurant(session) -> Restaurant | None:
    """Prefer 'Zeal's Kitchen', else the owner's first restaurant."""
    rows = (session.query(Restaurant)
            .filter_by(owner_id=OWNER_ID).order_by(Restaurant.created_at).all())
    if not rows:
        return None
    for r in rows:
        if "zeal" in (r.name or "").lower():
            return r
    return rows[0]


def _dt(day_offset: int, hm: tuple[int, int]) -> datetime:
    d = datetime.now(IST).date() - timedelta(days=day_offset)
    return datetime(d.year, d.month, d.day, hm[0], hm[1], tzinfo=IST)


def main() -> None:
    init_db()  # ensure the new payroll columns exist
    with SessionLocal() as s:
        user = s.get(User, OWNER_ID)
        if user is None:
            raise SystemExit(f"No user with id {OWNER_ID}; set SQUARE_SYNC_OWNER_ID.")
        rest = _pick_restaurant(s)
        if rest is None:
            raise SystemExit(f"Owner {OWNER_ID} has no restaurants to attach staff to.")
        loc = rest.square_location_id
        print(f"Owner {OWNER_ID} — attaching dummy team to restaurant {rest.name!r}")

        # Idempotent: clear any previous dummy rows (shifts first — FK).
        s.query(Shift).filter(
            Shift.owner_id == OWNER_ID, Shift.square_id.like("DUMMY_SH_%")).delete(
            synchronize_session=False)
        s.query(Employee).filter(
            Employee.owner_id == OWNER_ID, Employee.square_id.like("DUMMY_TM_%")).delete(
            synchronize_session=False)
        s.flush()

        emp_by_sq: dict[str, Employee] = {}
        for (sq, given, family, title, rate, tax, adv, amt, adv_days) in EMPLOYEES:
            e = Employee(
                owner_id=OWNER_ID, restaurant_id=rest.id, square_id=sq,
                square_location_id=loc, given_name=given, family_name=family,
                email=f"{given.lower()}.{family.lower()}@example.com",
                phone=None, status="ACTIVE", is_owner=False,
                title=title, hourly_rate=rate, tax_declared=tax,
                advance_taken=adv, advance_amount=amt,
                advance_date=(_dt(adv_days, (10, 0)) if adv_days is not None else None),
            )
            s.add(e)
            emp_by_sq[sq] = e
        s.flush()  # assign employee ids for the shift FK

        for (sq, emp_sq, off, in_hm, out_hm, brk, meal, status, tips,
             late, missed) in SHIFTS:
            emp = emp_by_sq[emp_sq]
            s.add(Shift(
                owner_id=OWNER_ID, employee_id=emp.id, restaurant_id=rest.id,
                square_id=sq, square_team_member_id=emp_sq, square_location_id=loc,
                clock_in=_dt(off, in_hm),
                clock_out=(_dt(off, out_hm) if out_hm else None),
                status=status, declared_tips=tips,
                break_hours=brk, meal_taken=meal,
                late_clockin=late, missed_clockin=missed,
            ))
        # Dummy sales for this branch so Labor Cost % has a denominator.
        s.query(Order).filter(
            Order.owner_id == OWNER_ID, Order.id.like("DUMMYORD%")).delete(
            synchronize_session=False)
        order_totals = [420, 680, 390, 810, 550, 720, 480, 900, 610, 640]
        for i, tot in enumerate(order_totals, 1):
            sub = round(tot / 1.1, 2)
            s.add(Order(
                id=f"DUMMYORD{i:02d}", owner_id=OWNER_ID, restaurant_id=rest.id,
                customer_id=None, placed_at=_dt(i % 5, (13, 0)), channel="Dine In",
                subtotal=sub, tax=round(tot - sub, 2), tip=0.0, total=float(tot),
                wait_minutes=10, rating=5, items=[],
            ))
        s.commit()

        n_emp = len(EMPLOYEES)
        n_sh = len(SHIFTS)
        print(f"Inserted {n_emp} team_members, {n_sh} labor_shifts, "
              f"{len(order_totals)} sample orders.")
        # quick recap
        from collections import Counter
        roles = Counter(e[3] for e in EMPLOYEES)
        print("Roles:", dict(roles))


if __name__ == "__main__":
    main()

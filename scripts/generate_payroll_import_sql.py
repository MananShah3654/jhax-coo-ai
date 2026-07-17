from __future__ import annotations

import csv
import re
import uuid
from collections import Counter, defaultdict
from datetime import datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path


OWNER_ID = 1
RESTAURANT_ID = "5f33b358a9b34c398f899147bea710c4"

ROOT = Path(__file__).resolve().parents[1]
DOWNLOADS = Path.home() / "Downloads"
OUTPUT = ROOT / "scripts" / "payroll_import_team_members_labor_shifts.sql"

CSV_FILES = {
    "payroll": DOWNLOADS / "payroll-export-1784200987684.csv",
    "directory": DOWNLOADS / "employee-directory-1784200637920.csv",
    "shift_new": DOWNLOADS / "employee-shift-detail-new-1784199572641.csv",
    "shift_old": DOWNLOADS / "employee-shift-detail-1784199542863.csv",
    "labor": DOWNLOADS / "employee-labor-detail-1784199385347.csv",
}

NS = uuid.uuid5(uuid.NAMESPACE_URL, "jhax-coo-ai/payroll-import/2026-07-16")


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8-sig") as fh:
        return list(csv.DictReader(fh))


def clean(value: object) -> str:
    return str(value or "").strip()


def none_if_blank(value: object) -> str | None:
    text = clean(value)
    if not text or text in {"-", "0000000000"}:
        return None
    return text


def dec(value: object, default: Decimal | None = None) -> Decimal | None:
    text = clean(value).replace(",", "")
    if not text:
        return default
    try:
        return Decimal(text)
    except InvalidOperation:
        return default


def sql_str(value: object) -> str:
    if value is None:
        return "NULL"
    return "'" + str(value).replace("'", "''") + "'"


def sql_num(value: Decimal | int | float | None) -> str:
    if value is None:
        return "NULL"
    return str(value)


def sql_bool(value: bool) -> str:
    return "TRUE" if value else "FALSE"


def parse_dt(value: object) -> datetime | None:
    text = clean(value)
    if not text:
        return None
    return datetime.strptime(text, "%m/%d/%Y %I:%M%p")


def sql_dt(value: datetime | None) -> str:
    if value is None:
        return "NULL"
    return "TIMESTAMPTZ " + sql_str(value.strftime("%Y-%m-%d %H:%M:%S"))


def split_name(name: str) -> tuple[str | None, str | None]:
    parts = clean(name).split()
    if not parts:
        return None, None
    if len(parts) == 1:
        return parts[0], None
    return parts[0], " ".join(parts[1:])


def slug(name: str) -> str:
    return re.sub(r"[^A-Z0-9]+", "_", name.upper()).strip("_") or "UNKNOWN"


def stable_id(kind: str, key: str) -> str:
    return str(uuid.uuid5(NS, f"{kind}:{key}"))


def shift_key(name: str, start: datetime | None, end: datetime | None) -> tuple[str, str, str]:
    return (
        clean(name).casefold(),
        start.isoformat(sep=" ") if start else "",
        end.isoformat(sep=" ") if end else "",
    )


def title_case_job(job: str | None) -> str | None:
    text = none_if_blank(job)
    if text is None or text.lower() == "unassociated tips":
        return None
    return text[:64]


def tip_amount(row: dict[str, str]) -> Decimal:
    for column in (
        "Declared Tips",
        "Adjusted Tips",
        "Paid Tips",
        "Net Tips",
        "Total Tips",
        "Gross Tips",
    ):
        value = dec(row.get(column), Decimal("0")) or Decimal("0")
        if value:
            return value
    return Decimal("0")


def build() -> tuple[list[dict[str, object]], list[dict[str, object]], dict[str, int]]:
    rows = {name: read_csv(path) for name, path in CSV_FILES.items()}

    names: list[str] = []
    for row in rows["directory"]:
        name = clean(row.get("Name"))
        if name and name.lower() != "total":
            names.append(name)
    for source in ("payroll", "labor", "shift_new", "shift_old"):
        for row in rows[source]:
            name = clean(row.get("Employee Name"))
            if name and name.lower() != "total":
                names.append(name)

    canonical_names = sorted(set(names), key=lambda n: n.casefold())
    directory_by_name = {
        clean(row.get("Name")).casefold(): row
        for row in rows["directory"]
        if clean(row.get("Name"))
    }

    jobs_by_name: dict[str, Counter[str]] = defaultdict(Counter)
    rates_by_name: dict[str, Counter[Decimal]] = defaultdict(Counter)
    for source, job_col, rate_col in (
        ("labor", "Job Name", "Pay Rate"),
        ("payroll", "Job Name", "Pay Rate"),
    ):
        for row in rows[source]:
            name = clean(row.get("Employee Name"))
            job = title_case_job(row.get(job_col))
            rate = dec(row.get(rate_col))
            if name and job:
                jobs_by_name[name.casefold()][job] += 1
            if name and rate is not None and rate > 0:
                rates_by_name[name.casefold()][rate] += 1

    employees: list[dict[str, object]] = []
    for name in canonical_names:
        given, family = split_name(name)
        dir_row = directory_by_name.get(name.casefold(), {})
        square_id = f"IMPORT_TM_{slug(name)}"
        employees.append({
            "id": stable_id("team_member", name.casefold()),
            "square_id": square_id,
            "name": name,
            "given_name": given,
            "family_name": family,
            "email": none_if_blank(dir_row.get("Email Address")),
            "phone": none_if_blank(dir_row.get("Phone Number(s)")),
            "title": jobs_by_name[name.casefold()].most_common(1)[0][0]
            if jobs_by_name[name.casefold()] else None,
            "hourly_rate": rates_by_name[name.casefold()].most_common(1)[0][0]
            if rates_by_name[name.casefold()] else None,
        })

    employees_by_name = {str(e["name"]).casefold(): e for e in employees}

    tips_by_shift: dict[tuple[str, str, str], Decimal] = {}
    for source in ("shift_new", "shift_old", "payroll"):
        for row in rows[source]:
            name = clean(row.get("Employee Name"))
            if not name or name.lower() == "total":
                continue
            start = parse_dt(row.get("Shift Start"))
            end = parse_dt(row.get("Shift End"))
            key = shift_key(name, start, end)
            tip = tip_amount(row)
            if key not in tips_by_shift or tip:
                tips_by_shift[key] = tip

    shifts: list[dict[str, object]] = []
    sequence = 1
    for row in rows["labor"]:
        name = clean(row.get("Employee Name"))
        if not name or name.lower() == "total":
            continue

        clock_in = parse_dt(row.get("Clocked In"))
        clock_out = parse_dt(row.get("Clocked Out"))
        is_aggregate = clock_in is None and clock_out is None and not clean(row.get("Pay Rate"))
        if is_aggregate:
            continue

        employee = employees_by_name.get(name.casefold())
        if employee is None:
            continue

        square_id = f"IMPORT_SH_{sequence:04d}"
        key = shift_key(name, clock_in, clock_out)
        shifts.append({
            "id": stable_id("labor_shift", square_id),
            "employee_id": employee["id"],
            "square_id": square_id,
            "square_team_member_id": employee["square_id"],
            "clock_in": clock_in,
            "clock_out": clock_out,
            "status": "COMPLETED" if clock_in and clock_out else "OPEN",
            "declared_tips": tips_by_shift.get(key, Decimal("0")),
            "break_hours": dec(row.get("Break Time (Hr)"), Decimal("0")) or Decimal("0"),
            "meal_taken": (dec(row.get("Break Time (Hr)"), Decimal("0")) or Decimal("0")) >= Decimal("0.5"),
            "late_clockin": False,
            "missed_clockin": clock_in is None,
        })
        sequence += 1

    stats = {
        "directory_rows": len(rows["directory"]),
        "employees": len(employees),
        "labor_rows": len(rows["labor"]),
        "shifts": len(shifts),
    }
    return employees, shifts, stats


def render(employees: list[dict[str, object]], shifts: list[dict[str, object]], stats: dict[str, int]) -> str:
    lines: list[str] = [
        "-- Generated from Square payroll CSV exports.",
        f"-- Employees: {stats['employees']}; labor shifts: {stats['shifts']}.",
        "-- Re-runnable: rows are keyed by (owner_id, square_id).",
        "BEGIN;",
        "",
    ]

    lines.extend([
        "INSERT INTO team_members (",
        "  id, owner_id, restaurant_id, square_id, square_location_id,",
        "  given_name, family_name, email, phone, status, is_owner,",
        "  title, hourly_rate, tax_declared, advance_taken, advance_amount, advance_date,",
        "  created_at, updated_at",
        ") VALUES",
    ])
    employee_values = []
    for e in employees:
        employee_values.append(
            "  ("
            + ", ".join([
                sql_str(e["id"]),
                str(OWNER_ID),
                sql_str(RESTAURANT_ID),
                sql_str(e["square_id"]),
                "NULL",
                sql_str(e["given_name"]),
                sql_str(e["family_name"]),
                sql_str(e["email"]),
                sql_str(e["phone"]),
                sql_str("ACTIVE"),
                "FALSE",
                sql_str(e["title"]),
                sql_num(e["hourly_rate"]),
                "FALSE",
                "FALSE",
                "NULL",
                "NULL",
                "NOW()",
                "NOW()",
            ])
            + ")"
        )
    lines.append(",\n".join(employee_values) + "\nON CONFLICT (owner_id, square_id) DO UPDATE SET")
    lines.extend([
        "  restaurant_id = EXCLUDED.restaurant_id,",
        "  given_name = EXCLUDED.given_name,",
        "  family_name = EXCLUDED.family_name,",
        "  email = EXCLUDED.email,",
        "  phone = EXCLUDED.phone,",
        "  status = EXCLUDED.status,",
        "  is_owner = EXCLUDED.is_owner,",
        "  title = EXCLUDED.title,",
        "  hourly_rate = EXCLUDED.hourly_rate,",
        "  tax_declared = EXCLUDED.tax_declared,",
        "  advance_taken = EXCLUDED.advance_taken,",
        "  advance_amount = EXCLUDED.advance_amount,",
        "  advance_date = EXCLUDED.advance_date,",
        "  updated_at = NOW();",
        "",
    ])

    lines.extend([
        "INSERT INTO labor_shifts (",
        "  id, owner_id, employee_id, restaurant_id, square_id, square_team_member_id,",
        "  square_location_id, clock_in, clock_out, status, declared_tips,",
        "  created_at, updated_at, break_hours, meal_taken, late_clockin, missed_clockin",
        ") VALUES",
    ])
    shift_values = []
    for s in shifts:
        shift_values.append(
            "  ("
            + ", ".join([
                sql_str(s["id"]),
                str(OWNER_ID),
                sql_str(s["employee_id"]),
                sql_str(RESTAURANT_ID),
                sql_str(s["square_id"]),
                sql_str(s["square_team_member_id"]),
                "NULL",
                sql_dt(s["clock_in"]),
                sql_dt(s["clock_out"]),
                sql_str(s["status"]),
                sql_num(s["declared_tips"]),
                "NOW()",
                "NOW()",
                sql_num(s["break_hours"]),
                sql_bool(bool(s["meal_taken"])),
                sql_bool(bool(s["late_clockin"])),
                sql_bool(bool(s["missed_clockin"])),
            ])
            + ")"
        )
    lines.append(",\n".join(shift_values) + "\nON CONFLICT (owner_id, square_id) DO UPDATE SET")
    lines.extend([
        "  employee_id = EXCLUDED.employee_id,",
        "  restaurant_id = EXCLUDED.restaurant_id,",
        "  square_team_member_id = EXCLUDED.square_team_member_id,",
        "  square_location_id = EXCLUDED.square_location_id,",
        "  clock_in = EXCLUDED.clock_in,",
        "  clock_out = EXCLUDED.clock_out,",
        "  status = EXCLUDED.status,",
        "  declared_tips = EXCLUDED.declared_tips,",
        "  break_hours = EXCLUDED.break_hours,",
        "  meal_taken = EXCLUDED.meal_taken,",
        "  late_clockin = EXCLUDED.late_clockin,",
        "  missed_clockin = EXCLUDED.missed_clockin,",
        "  updated_at = NOW();",
        "",
        "COMMIT;",
        "",
    ])
    return "\n".join(lines)


def main() -> None:
    missing = [str(path) for path in CSV_FILES.values() if not path.exists()]
    if missing:
        raise SystemExit("Missing CSV file(s):\n" + "\n".join(missing))

    employees, shifts, stats = build()
    OUTPUT.write_text(render(employees, shifts, stats), encoding="utf-8")
    print(f"Wrote {OUTPUT}")
    print(f"Employees: {stats['employees']}")
    print(f"Labor shifts: {stats['shifts']}")


if __name__ == "__main__":
    main()

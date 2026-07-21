"""
CRUD / onboarding routes for JHAX.

These let a signed-in owner build their real data — restaurants (locations),
menu items, customers, and orders — instead of relying on a mock seed. Every
route is authenticated with `get_current_user`, stamps `owner_id = user.id`
server-side, and validates that any referenced restaurant/customer/menu id
belongs to the caller. This is the tenant-isolation boundary for writes; the
read/analytics side is isolated by PostgresDataSource(owner_id).

Mounted under /api by server.py.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from auth import get_current_user
from database import (
    Customer, Employee, MenuItem, Order, OrderItem, Restaurant, Shift, User,
    get_db,
)

crud = APIRouter(prefix="/api")


# ==================== helpers ====================
def _own_restaurant(db: Session, user: User, restaurant_id: str) -> Restaurant:
    """Fetch a restaurant, 404 if it doesn't exist or isn't the caller's."""
    r = db.get(Restaurant, restaurant_id)
    if r is None or r.owner_id != user.id:
        raise HTTPException(404, "Restaurant not found")
    return r


def _own_menu_item(db: Session, user: User, item_id: str) -> MenuItem:
    m = db.get(MenuItem, item_id)
    if m is None or m.owner_id != user.id:
        raise HTTPException(404, "Menu item not found")
    return m


def _own_customer(db: Session, user: User, customer_id: str) -> Customer:
    c = db.get(Customer, customer_id)
    if c is None or c.owner_id != user.id:
        raise HTTPException(404, "Customer not found")
    return c


# ==================== restaurants ====================
class RestaurantIn(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    city: str | None = None
    address: str | None = None
    manager: str | None = None
    phone: str | None = None


class RestaurantPatch(BaseModel):
    name: str | None = None
    city: str | None = None
    address: str | None = None
    manager: str | None = None
    phone: str | None = None
    is_active: bool | None = None


@crud.post("/restaurants")
def create_restaurant(
    req: RestaurantIn,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    r = Restaurant(owner_id=user.id, **req.model_dump())
    db.add(r)
    db.commit()
    db.refresh(r)
    return r.to_dict()


@crud.get("/restaurants")
def list_restaurants(
    user: User = Depends(get_current_user), db: Session = Depends(get_db)
):
    rows = (db.query(Restaurant)
            .filter_by(owner_id=user.id)
            .order_by(Restaurant.created_at).all())
    return {"restaurants": [r.to_dict() for r in rows]}


@crud.patch("/restaurants/{restaurant_id}")
def update_restaurant(
    restaurant_id: str,
    req: RestaurantPatch,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    r = _own_restaurant(db, user, restaurant_id)
    for field, value in req.model_dump(exclude_unset=True).items():
        setattr(r, field, value)
    db.commit()
    db.refresh(r)
    return r.to_dict()


@crud.delete("/restaurants/{restaurant_id}")
def delete_restaurant(
    restaurant_id: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    # Soft delete so historical orders/analytics stay intact.
    r = _own_restaurant(db, user, restaurant_id)
    r.is_active = False
    db.commit()
    return {"ok": True, "id": restaurant_id, "is_active": False}


# ==================== menu ====================
class MenuItemIn(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    category: str = "Uncategorized"
    price: float = Field(ge=0)
    cost: float = Field(ge=0)
    featured: bool = False


class MenuItemPatch(BaseModel):
    name: str | None = None
    category: str | None = None
    price: float | None = Field(default=None, ge=0)
    cost: float | None = Field(default=None, ge=0)
    featured: bool | None = None
    is_active: bool | None = None


@crud.post("/restaurants/{restaurant_id}/menu")
def create_menu_item(
    restaurant_id: str,
    req: MenuItemIn,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _own_restaurant(db, user, restaurant_id)
    m = MenuItem(owner_id=user.id, restaurant_id=restaurant_id, **req.model_dump())
    db.add(m)
    db.commit()
    db.refresh(m)
    return m.to_dict()


@crud.get("/menu/items")
def list_menu_items(
    restaurant_id: str | None = None,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    q = db.query(MenuItem).filter_by(owner_id=user.id)
    if restaurant_id:
        _own_restaurant(db, user, restaurant_id)
        q = q.filter_by(restaurant_id=restaurant_id)
    return {"items": [m.to_dict() for m in q.order_by(MenuItem.name).all()]}


@crud.patch("/menu/items/{item_id}")
def update_menu_item(
    item_id: str,
    req: MenuItemPatch,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    m = _own_menu_item(db, user, item_id)
    for field, value in req.model_dump(exclude_unset=True).items():
        setattr(m, field, value)
    db.commit()
    db.refresh(m)
    return m.to_dict()


@crud.delete("/menu/items/{item_id}")
def delete_menu_item(
    item_id: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    m = _own_menu_item(db, user, item_id)
    m.is_active = False
    db.commit()
    return {"ok": True, "id": item_id, "is_active": False}


# ==================== customers ====================
class CustomerIn(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    phone: str | None = None
    email: str | None = None
    restaurant_id: str | None = None
    tags: list[str] = Field(default_factory=list)


class CustomerPatch(BaseModel):
    name: str | None = None
    phone: str | None = None
    email: str | None = None
    restaurant_id: str | None = None
    tags: list[str] | None = None
    loyalty_points: int | None = None


@crud.post("/customers")
def create_customer(
    req: CustomerIn,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if req.restaurant_id:
        _own_restaurant(db, user, req.restaurant_id)
    c = Customer(owner_id=user.id, **req.model_dump())
    db.add(c)
    db.commit()
    db.refresh(c)
    return c.to_dict()


@crud.get("/customers/list")
def list_customers(
    user: User = Depends(get_current_user), db: Session = Depends(get_db)
):
    rows = (db.query(Customer)
            .filter_by(owner_id=user.id)
            .order_by(Customer.name).all())
    return {"customers": [c.to_dict() for c in rows]}


@crud.patch("/customers/{customer_id}")
def update_customer(
    customer_id: str,
    req: CustomerPatch,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    c = _own_customer(db, user, customer_id)
    data = req.model_dump(exclude_unset=True)
    if data.get("restaurant_id"):
        _own_restaurant(db, user, data["restaurant_id"])
    for field, value in data.items():
        setattr(c, field, value)
    db.commit()
    db.refresh(c)
    return c.to_dict()


# ==================== orders (analytics-critical write path) ====================
class OrderLineIn(BaseModel):
    menu_item_id: str
    qty: int = Field(ge=1)


class OrderIn(BaseModel):
    restaurant_id: str
    customer_id: str | None = None
    channel: str = "Dine In"
    placed_at: datetime | None = None
    tax: float = Field(default=0.0, ge=0)
    tip: float = Field(default=0.0, ge=0)
    wait_minutes: int = Field(default=0, ge=0)
    rating: int = Field(default=5, ge=1, le=5)
    items: list[OrderLineIn] = Field(min_length=1)


@crud.post("/orders")
def create_order(
    req: OrderIn,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Create an order with line items.

    price/cost/name are SNAPSHOTTED from each menu item at sale time so later
    menu edits don't rewrite historical KPIs. subtotal = Σ qty*price;
    total = subtotal + tax + tip.
    """
    _own_restaurant(db, user, req.restaurant_id)
    if req.customer_id:
        _own_customer(db, user, req.customer_id)

    placed_at = req.placed_at or datetime.now(timezone.utc)
    if placed_at.tzinfo is None:
        placed_at = placed_at.replace(tzinfo=timezone.utc)

    line_items: list[OrderItem] = []
    subtotal = 0.0
    for line in req.items:
        m = _own_menu_item(db, user, line.menu_item_id)
        if m.restaurant_id != req.restaurant_id:
            raise HTTPException(
                400, f"Menu item {m.id} does not belong to this restaurant"
            )
        subtotal += line.qty * m.price
        line_items.append(OrderItem(
            menu_item_id=m.id, name=m.name, qty=line.qty,
            price=m.price, cost=m.cost,
        ))

    subtotal = round(subtotal, 2)
    total = round(subtotal + req.tax + req.tip, 2)
    order = Order(
        owner_id=user.id, restaurant_id=req.restaurant_id,
        customer_id=req.customer_id, placed_at=placed_at, channel=req.channel,
        subtotal=subtotal, tax=req.tax, tip=req.tip, total=total,
        wait_minutes=req.wait_minutes, rating=req.rating, items=line_items,
    )
    db.add(order)

    # Best-effort loyalty bump so customer analytics reflects the visit.
    if req.customer_id:
        c = db.get(Customer, req.customer_id)
        c.visits = (c.visits or 0) + 1
        c.last_visit_at = placed_at
        c.lifetime_value = round((c.lifetime_value or 0.0) + total, 2)
        c.avg_spend = round(c.lifetime_value / max(c.visits, 1), 2)

    db.commit()
    db.refresh(order)
    return order.to_dict()


@crud.get("/orders")
def list_orders(
    restaurant_id: str | None = None,
    days: int = 30,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    from datetime import timedelta
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    q = (db.query(Order)
         .filter(Order.owner_id == user.id, Order.placed_at >= cutoff))
    if restaurant_id:
        _own_restaurant(db, user, restaurant_id)
        q = q.filter(Order.restaurant_id == restaurant_id)
    rows = q.order_by(Order.placed_at.desc()).all()
    return {"days": days, "orders": [o.to_dict() for o in rows]}


# ==================== employees + shifts (Square sync, read-only) ====================
# These rows are populated by sync_square.py (Square Team + Labor APIs), not by
# app writes. Reads are owner_id-scoped like everything else.
def _own_employee(db: Session, user: User, employee_id: str) -> Employee:
    e = db.get(Employee, employee_id)
    if e is None or e.owner_id != user.id:
        raise HTTPException(404, "Employee not found")
    return e


@crud.get("/employees")
def list_employees(
    restaurant_id: str | None = None,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Employee roster for the owner, optionally scoped to one restaurant.

    Each employee carries `last_shift` (their most recent clock-in/out) so the
    UI can show who's on/off without a second request per row.
    """
    q = db.query(Employee).filter_by(owner_id=user.id)
    if restaurant_id:
        _own_restaurant(db, user, restaurant_id)
        q = q.filter_by(restaurant_id=restaurant_id)
    rows = q.order_by(Employee.given_name, Employee.family_name).all()

    out = []
    for e in rows:
        last = (db.query(Shift)
                .filter_by(owner_id=user.id, employee_id=e.id)
                .order_by(Shift.clock_in.desc()).first())
        data = e.to_dict()
        data["last_shift"] = last.to_dict() if last else None
        out.append(data)
    return {"employees": out}


@crud.get("/employees/{employee_id}")
def get_employee(
    employee_id: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Single employee (for the branch-wise employee detail view)."""
    return _own_employee(db, user, employee_id).to_dict()


@crud.get("/employees/{employee_id}/shifts")
def list_employee_shifts(
    employee_id: str,
    days: int = 30,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    from datetime import timedelta
    _own_employee(db, user, employee_id)
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    rows = (db.query(Shift)
            .filter(Shift.owner_id == user.id,
                    Shift.employee_id == employee_id,
                    Shift.clock_in >= cutoff)
            .order_by(Shift.clock_in.desc()).all())
    return {"days": days, "shifts": [s.to_dict() for s in rows]}


# Overtime kicks in past a standard 8-hour shift.
_OT_THRESHOLD_HOURS = 8.0


def _worked_hours(sh: Shift) -> float | None:
    """Net hours worked on a closed, non-missed shift (span minus break)."""
    if sh.missed_clockin or sh.status == "MISSED":
        return None
    if not sh.clock_in or not sh.clock_out:
        return None
    span = (sh.clock_out - sh.clock_in).total_seconds() / 3600.0
    return max(0.0, round(span - (sh.break_hours or 0.0), 2))


@crud.get("/team/labor")
def team_labor(
    restaurant_id: str,
    days: int = 30,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Labor KPIs for one branch + a per-employee breakdown.

    Branch KPIs: total labor hours, labor cost, labor cost % of sales, overtime
    hours, clock-ins missed. Employee KPIs (for the table): hours worked,
    overtime, late clock-ins, labor cost, tips — sortable into "top performers".
    """
    from datetime import timedelta
    _own_restaurant(db, user, restaurant_id)
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)

    emps = {e.id: e for e in db.query(Employee)
            .filter_by(owner_id=user.id, restaurant_id=restaurant_id).all()}
    shifts = (db.query(Shift)
              .filter(Shift.owner_id == user.id,
                      Shift.restaurant_id == restaurant_id,
                      Shift.clock_in >= cutoff).all())

    # Per-employee aggregation.
    agg: dict[str, dict] = {
        eid: {"hours": 0.0, "overtime": 0.0, "late": 0, "missed": 0,
              "cost": 0.0, "tips": 0.0, "shifts": 0}
        for eid in emps
    }
    total_hours = total_cost = total_ot = 0.0
    missed_total = late_total = 0

    for sh in shifts:
        a = agg.get(sh.employee_id)
        if a is None:
            continue
        rate = emps[sh.employee_id].hourly_rate or 0.0
        if sh.missed_clockin or sh.status == "MISSED":
            a["missed"] += 1
            missed_total += 1
            continue
        if sh.late_clockin:
            a["late"] += 1
            late_total += 1
        worked = _worked_hours(sh)
        if worked is None:      # still on shift (open) — no hours yet
            continue
        ot = max(0.0, worked - _OT_THRESHOLD_HOURS)
        a["hours"] += worked
        a["overtime"] += ot
        a["cost"] += worked * rate
        a["tips"] += sh.declared_tips or 0.0
        a["shifts"] += 1
        total_hours += worked
        total_ot += ot
        total_cost += worked * rate

    # Branch sales in the same window (for labor cost %).
    orders = (db.query(Order)
              .filter(Order.owner_id == user.id,
                      Order.restaurant_id == restaurant_id,
                      Order.placed_at >= cutoff).all())
    revenue = round(sum(o.total for o in orders), 2)
    labor_cost_pct = round(total_cost / revenue * 100, 1) if revenue else None

    employees_out = []
    for eid, a in agg.items():
        e = emps[eid]
        name = " ".join(p for p in (e.given_name, e.family_name) if p)
        employees_out.append({
            "id": eid, "name": name or None, "title": e.title,
            "hourly_rate": e.hourly_rate,
            "hours_worked": round(a["hours"], 2),
            "overtime_hours": round(a["overtime"], 2),
            "late_clockins": a["late"],
            "missed_clockins": a["missed"],
            "labor_cost": round(a["cost"], 2),
            "tips": round(a["tips"], 2),
            "shifts": a["shifts"],
        })
    # Default order: most hours first (workforce utilization / top performers).
    employees_out.sort(key=lambda x: x["hours_worked"], reverse=True)

    return {
        "restaurant_id": restaurant_id,
        "days": days,
        "labor": {
            "total_labor_hours": round(total_hours, 2),
            "labor_cost": round(total_cost, 2),
            "labor_cost_pct": labor_cost_pct,
            "overtime_hours": round(total_ot, 2),
            "clockins_missed": missed_total,
            "late_clockins": late_total,
            "revenue": revenue,
        },
        "employees": employees_out,
    }


# ==================== Team workforce assistant (period-based) ====================
# Tunable targets used for KPI status + the chat answers.
_LABOR_COST_TARGET_PCT = 30.0      # healthy labor is under this share of sales
_OT_PREMIUM = 0.5                  # time-and-a-half -> the "extra" 0.5x on OT hours
_REV_PER_HOUR_GOOD = 40.0          # revenue per labor hour we consider healthy


def _period_range(period: str):
    """Map a period name to (start, end, label). Weeks start Monday; all UTC."""
    from datetime import timedelta
    now = datetime.now(timezone.utc)
    today = now.replace(hour=0, minute=0, second=0, microsecond=0)
    p = (period or "this_week").lower()
    if p == "today":
        return today, now, "Today"
    if p == "yesterday":
        return today - timedelta(days=1), today, "Yesterday"
    if p in ("this_week", "week"):
        return today - timedelta(days=today.weekday()), now, "This Week"
    if p == "last_week":
        this_mon = today - timedelta(days=today.weekday())
        return this_mon - timedelta(days=7), this_mon, "Last Week"
    if p in ("this_month", "month"):
        return today.replace(day=1), now, "This Month"
    if p == "last_month":
        first = today.replace(day=1)
        return (first - timedelta(days=1)).replace(day=1), first, "Last Month"
    return today - timedelta(days=7), now, "Last 7 Days"


def _labor_dataset(db: Session, owner_id: int, restaurant_id: str, start, end,
                   label: str) -> dict:
    """Compute the full labor picture for one branch over [start, end):
    totals, per-employee, per-shift, and per-day (rush vs staffing)."""
    emps = {e.id: e for e in db.query(Employee)
            .filter_by(owner_id=owner_id, restaurant_id=restaurant_id).all()}
    shifts = (db.query(Shift)
              .filter(Shift.owner_id == owner_id,
                      Shift.restaurant_id == restaurant_id,
                      Shift.clock_in >= start, Shift.clock_in < end).all())
    orders = (db.query(Order)
              .filter(Order.owner_id == owner_id,
                      Order.restaurant_id == restaurant_id,
                      Order.placed_at >= start, Order.placed_at < end).all())

    per_emp: dict[str, dict] = {}
    per_day: dict[str, dict] = {}
    shift_rows: list[dict] = []
    total_hours = total_cost = total_ot = total_extra = 0.0
    missed_total = late_total = 0

    def _day(dt):
        return dt.date().isoformat()

    for sh in shifts:
        e = emps.get(sh.employee_id)
        name = " ".join(p for p in ((e.given_name if e else None),
                                    (e.family_name if e else None)) if p) or "Unknown"
        rate = (e.hourly_rate if e else 0) or 0.0
        pe = per_emp.setdefault(sh.employee_id, {
            "id": sh.employee_id, "name": name, "title": e.title if e else None,
            "rate": rate, "hours": 0.0, "overtime": 0.0, "cost": 0.0,
            "tips": 0.0, "late": 0, "missed": 0, "shifts": 0})
        d = per_day.setdefault(_day(sh.clock_in), {
            "date": _day(sh.clock_in), "revenue": 0.0, "orders": 0,
            "labor_hours": 0.0, "labor_cost": 0.0, "staff": set()})
        if sh.missed_clockin or sh.status == "MISSED":
            pe["missed"] += 1
            missed_total += 1
            continue
        if sh.late_clockin:
            pe["late"] += 1
            late_total += 1
        worked = _worked_hours(sh)
        if worked is None:
            continue
        ot = max(0.0, worked - _OT_THRESHOLD_HOURS)
        cost = worked * rate
        extra = ot * rate * _OT_PREMIUM
        pe["hours"] += worked
        pe["overtime"] += ot
        pe["cost"] += cost
        pe["tips"] += sh.declared_tips or 0.0
        pe["shifts"] += 1
        d["labor_hours"] += worked
        d["labor_cost"] += cost
        d["staff"].add(sh.employee_id)
        total_hours += worked
        total_ot += ot
        total_cost += cost
        total_extra += extra
        shift_rows.append({
            "employee": name, "title": e.title if e else None,
            "date": _day(sh.clock_in),
            "hours": round(worked, 2), "rate": rate, "cost": round(cost, 2),
            "overtime": round(ot, 2),
        })

    for o in orders:
        d = per_day.setdefault(_day(o.placed_at), {
            "date": _day(o.placed_at), "revenue": 0.0, "orders": 0,
            "labor_hours": 0.0, "labor_cost": 0.0, "staff": set()})
        d["revenue"] += o.total
        d["orders"] += 1

    revenue = round(sum(o.total for o in orders), 2)
    labor_cost_pct = round(total_cost / revenue * 100, 1) if revenue else None
    rev_per_hour = round(revenue / total_hours, 2) if total_hours else None

    days_out = []
    for d in sorted(per_day.values(), key=lambda x: x["date"]):
        lh = round(d["labor_hours"], 2)
        rev = round(d["revenue"], 2)
        rph = round(rev / lh, 2) if lh else None
        flag = "balanced"
        if lh > 0 and rph is not None:
            if rph < _REV_PER_HOUR_GOOD * 0.6:
                flag = "overstaffed"
            elif rph > _REV_PER_HOUR_GOOD * 1.6:
                flag = "understaffed"
        days_out.append({
            "date": d["date"], "revenue": rev, "orders": d["orders"],
            "labor_hours": lh, "labor_cost": round(d["labor_cost"], 2),
            "staff": len(d["staff"]), "revenue_per_hour": rph, "flag": flag,
        })

    emps_out = sorted(
        [{**pe, "hours": round(pe["hours"], 2), "overtime": round(pe["overtime"], 2),
          "cost": round(pe["cost"], 2), "tips": round(pe["tips"], 2)}
         for pe in per_emp.values()],
        key=lambda x: x["cost"], reverse=True)

    return {
        "label": label,
        "total_labor_hours": round(total_hours, 2),
        "labor_cost": round(total_cost, 2),
        "overtime_hours": round(total_ot, 2),
        "overtime_extra_cost": round(total_extra, 2),
        "revenue": revenue,
        "labor_cost_pct": labor_cost_pct,
        "revenue_per_hour": rev_per_hour,
        "clockins_missed": missed_total,
        "late_clockins": late_total,
        "staff_count": len([e for e in per_emp.values() if e["shifts"] > 0]),
        "employees": emps_out,
        "shifts": shift_rows,
        "per_day": days_out,
    }


def _kpi_cards(ds: dict) -> list[dict]:
    """Turn the dataset into the KPI cards the Team screen renders."""
    pct = ds["labor_cost_pct"]
    rph = ds["revenue_per_hour"]
    return [
        {"key": "overtime_hours", "label": "Overtime Hours",
         "value": f"{ds['overtime_hours']}h",
         "detail": (f"Costing extra: {_usd(ds['overtime_extra_cost'])}"
                    if ds["overtime_hours"] else "None"),
         "status": "warn" if ds["overtime_hours"] > 0 else "ok"},
        {"key": "labor_cost_pct", "label": "Labor Cost %",
         "value": f"{pct}%" if pct is not None else "—",
         "detail": f"Target: <{int(_LABOR_COST_TARGET_PCT)}%",
         "status": ("ok" if pct is not None and pct <= _LABOR_COST_TARGET_PCT
                    else "warn" if pct is not None else "muted")},
        {"key": "revenue_per_staff", "label": "Revenue Per Staff",
         "value": f"{_usd(rph)}/hr" if rph is not None else "—",
         "detail": ("Good" if rph is not None and rph >= _REV_PER_HOUR_GOOD
                    else "Below target" if rph is not None else "No sales"),
         "status": ("ok" if rph is not None and rph >= _REV_PER_HOUR_GOOD
                    else "warn" if rph is not None else "muted")},
        {"key": "clockins_missed", "label": "Clock-ins Missed",
         "value": str(ds["clockins_missed"]), "detail": "Attendance",
         "status": "warn" if ds["clockins_missed"] > 0 else "ok"},
        {"key": "late_clockins", "label": "Late Clock-ins",
         "value": str(ds["late_clockins"]), "detail": "Punctuality",
         "status": "warn" if ds["late_clockins"] > 0 else "ok"},
    ]


def _usd(n) -> str:
    if n is None:
        return "—"
    return f"${n:,.0f}" if float(n).is_integer() else f"${n:,.2f}"


# ---------------- deterministic chat answers ----------------
def _ans_labor_high(ds: dict) -> dict:
    pct, rev, cost, label = (ds["labor_cost_pct"], ds["revenue"],
                             ds["labor_cost"], ds["label"])
    if pct is None:
        return {"answer": f"No sales were recorded for {label}, so labor cost % "
                f"can't be computed. Total wages were {_usd(cost)} across "
                f"{ds['total_labor_hours']}h."}
    if pct <= _LABOR_COST_TARGET_PCT:
        return {"answer": f"Labor is healthy for {label}: **{pct}%** of sales — "
                f"under the {int(_LABOR_COST_TARGET_PCT)}% target. "
                f"{_usd(cost)} wages on {_usd(rev)} sales."}
    lines = [f"Labor is **{pct}%** of sales for {label} — above the "
             f"{int(_LABOR_COST_TARGET_PCT)}% target ({_usd(cost)} wages on "
             f"{_usd(rev)} sales). Main drivers:"]
    for e in ds["employees"][:3]:
        lines.append(f"• {e['name']} ({e['title'] or 'staff'}) — {_usd(e['cost'])} "
                     f"over {e['hours']}h")
    if ds["overtime_hours"] > 0:
        lines.append(f"• Overtime added ~{_usd(ds['overtime_extra_cost'])} across "
                     f"{ds['overtime_hours']}h — trimming OT is the fastest cut.")
    over = [d for d in ds["per_day"] if d["flag"] == "overstaffed"]
    if over:
        ds_list = ", ".join(d["date"] for d in over)
        lines.append(f"• On {ds_list}, staffing outpaced demand (low revenue per "
                     f"labor hour) — fewer shifts those days would help.")
    return {"answer": "\n".join(lines)}


def _ans_expensive_shift(ds: dict) -> dict:
    if not ds["shifts"]:
        return {"answer": f"No completed shifts in {ds['label']}."}
    top = max(ds["shifts"], key=lambda s: s["cost"])
    extra = (" (includes overtime)" if top["overtime"] > 0 else "")
    return {"answer": f"Your most expensive shift in {ds['label']}: **{top['employee']}** "
            f"({top['title'] or 'staff'}) on {top['date']} — {top['hours']}h at "
            f"{_usd(top['rate'])}/h = **{_usd(top['cost'])}**{extra}.",
            "metrics": [
                {"label": "Shift Cost", "value": _usd(top["cost"])},
                {"label": "Hours", "value": f"{top['hours']}h"},
                {"label": "Rate", "value": f"{_usd(top['rate'])}/h"},
                {"label": "Overtime", "value": f"{top['overtime']}h"},
            ]}


def _ans_overstaffed(ds: dict) -> dict:
    rph = ds["revenue_per_hour"]
    label = ds["label"]
    if not ds["total_labor_hours"]:
        return {"answer": f"No labor hours recorded for {label}, so I can't assess "
                "staffing levels."}
    if rph is None:
        return {"answer": f"You logged {ds['total_labor_hours']}h of labor for {label} "
                "but I have no sales for the period to compare against — add sales "
                "data to gauge over/understaffing."}
    verdict = ("You look **overstaffed** for the demand"
               if rph < _REV_PER_HOUR_GOOD
               else "Staffing looks **well-matched** to demand")
    lines = [f"{verdict} — revenue per labor hour is {_usd(rph)}/h "
             f"(healthy is ~{_usd(_REV_PER_HOUR_GOOD)}/h)."]
    over = [d for d in ds["per_day"] if d["flag"] == "overstaffed"]
    under = [d for d in ds["per_day"] if d["flag"] == "understaffed"]
    if over:
        lines.append("Overstaffed days (labor > demand): " +
                     ", ".join(f"{d['date']} ({_usd(d['revenue'])} sales, "
                               f"{d['labor_hours']}h)" for d in over))
    if under:
        lines.append("Understaffed / high-rush days: " +
                     ", ".join(f"{d['date']} ({_usd(d['revenue'])} sales, "
                               f"{d['labor_hours']}h)" for d in under))
    if not over and not under:
        lines.append("Daily staffing tracked demand reasonably well.")
    return {"answer": "\n".join(lines),
            "metrics": [
                {"label": "Rev / Labor-hr",
                 "value": f"{_usd(rph)}/h" if rph is not None else "—"},
                {"label": "Labor Hours", "value": f"{ds['total_labor_hours']}h"},
                {"label": "Overstaffed Days", "value": str(len(over))},
                {"label": "Staff", "value": str(ds["staff_count"])},
            ],
            "table": {
                "title": "Day-by-day: rush vs staffing",
                "columns": ["Date", "Sales", "Orders", "Labor h", "Staff",
                            "$/labor-hr", "Read"],
                "rows": [[d["date"], _usd(d["revenue"]), d["orders"],
                          d["labor_hours"], d["staff"],
                          _usd(d["revenue_per_hour"]) + "/h" if d["revenue_per_hour"]
                          else "—", d["flag"]]
                         for d in ds["per_day"]],
            }}


def _ans_employee_list(ds: dict) -> dict:
    if not ds["employees"]:
        return {"answer": f"No employees have logged shifts in {ds['label']}."}
    return {"answer": f"{len(ds['employees'])} employees worked in {ds['label']} "
            "(ranked by labor cost):",
            "metrics": [
                {"label": "Employees", "value": str(len(ds["employees"]))},
                {"label": "Total Hours", "value": f"{ds['total_labor_hours']}h"},
                {"label": "Labor Cost", "value": _usd(ds["labor_cost"])},
            ],
            "table": {
                "title": "Employees",
                "columns": ["Name", "Role", "Hours", "Overtime", "Late",
                            "Labor Cost", "Tips"],
                "rows": [[e["name"], e["title"] or "—", f"{e['hours']}h",
                          f"{e['overtime']}h", e["late"], _usd(e["cost"]),
                          _usd(e["tips"]) if e["tips"] else "—"]
                         for e in ds["employees"]],
            }}


def _route_question(question: str, ds: dict) -> dict:
    q = (question or "").lower()
    if any(k in q for k in ("expensive", "costliest", "priciest")):
        return _ans_expensive_shift(ds)
    if any(k in q for k in ("overstaff", "understaff", "too many", "too few",
                            "staffing", "rush")):
        return _ans_overstaffed(ds)
    if any(k in q for k in ("employee list", "list of", "show employee",
                            "who works", "roster", "team list")):
        return _ans_employee_list(ds)
    if any(k in q for k in ("labor cost high", "cost high", "why is my labor",
                            "labor high", "expensive labor", "cost so")):
        return _ans_labor_high(ds)
    # default: a labor summary
    pct = ds["labor_cost_pct"]
    return {"answer": f"For {ds['label']}: {ds['total_labor_hours']}h logged, "
            f"{_usd(ds['labor_cost'])} in wages"
            + (f", {pct}% of sales" if pct is not None else "")
            + f", {ds['overtime_hours']}h overtime, {ds['clockins_missed']} missed "
            f"and {ds['late_clockins']} late clock-ins. Ask about labor cost, your "
            "most expensive shift, overstaffing, or the employee list."}


@crud.get("/team/insights")
def team_insights(
    restaurant_id: str,
    period: str = "this_week",
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """KPI cards for the Team workforce screen, scoped to a branch + period."""
    _own_restaurant(db, user, restaurant_id)
    start, end, label = _period_range(period)
    ds = _labor_dataset(db, user.id, restaurant_id, start, end, label)
    return {
        "restaurant_id": restaurant_id, "period": period, "period_label": label,
        "start": start.isoformat(), "end": end.isoformat(),
        "kpis": _kpi_cards(ds),
        "summary": {
            "total_labor_hours": ds["total_labor_hours"],
            "labor_cost": ds["labor_cost"], "revenue": ds["revenue"],
            "staff_count": ds["staff_count"],
        },
    }


def _labor_context_json(ds: dict) -> str:
    """Compact, LLM-ready snapshot of the (already accurate) labor data."""
    top = max(ds["shifts"], key=lambda s: s["cost"]) if ds["shifts"] else None
    payload = {
        "period": ds["label"],
        "targets": {
            "labor_cost_pct_target": _LABOR_COST_TARGET_PCT,
            "healthy_revenue_per_labor_hour": _REV_PER_HOUR_GOOD,
            "overtime_after_hours_per_shift": _OT_THRESHOLD_HOURS,
        },
        "totals": {
            "labor_hours": ds["total_labor_hours"],
            "labor_cost": ds["labor_cost"],
            "labor_cost_pct_of_sales": ds["labor_cost_pct"],
            "sales_revenue": ds["revenue"],
            "revenue_per_labor_hour": ds["revenue_per_hour"],
            "overtime_hours": ds["overtime_hours"],
            "overtime_extra_cost": ds["overtime_extra_cost"],
            "clockins_missed": ds["clockins_missed"],
            "late_clockins": ds["late_clockins"],
            "staff_count": ds["staff_count"],
        },
        "most_expensive_shift": top,
        "top_employees_by_cost": [
            {"name": e["name"], "role": e["title"], "hours": e["hours"],
             "overtime_hours": e["overtime"], "late_clockins": e["late"],
             "missed_clockins": e["missed"], "labor_cost": e["cost"],
             "tips": e["tips"]}
            for e in ds["employees"][:12]
        ],
        "per_day_rush_vs_staffing": [
            {"date": d["date"], "sales": d["revenue"], "orders": d["orders"],
             "labor_hours": d["labor_hours"], "staff": d["staff"],
             "revenue_per_labor_hour": d["revenue_per_hour"], "read": d["flag"]}
            for d in ds["per_day"]
        ],
    }
    return json.dumps(payload, default=str)


class TeamAskIn(BaseModel):
    restaurant_id: str
    period: str = "this_week"
    question: str = Field(min_length=1, max_length=500)


@crud.post("/team/ask")
async def team_ask(
    req: TeamAskIn,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Hybrid answer: numbers are computed deterministically (accurate), then an
    LLM explains them conversationally over the injected data (streamed, SSE).

    A structured `table` (employee list / per-day rush) is emitted first and
    rendered as-is. If the LLM is unavailable, we fall back to the deterministic
    text answer so the chat always responds.
    """
    _own_restaurant(db, user, req.restaurant_id)
    start, end, label = _period_range(req.period)
    ds = _labor_dataset(db, user.id, req.restaurant_id, start, end, label)
    det = _route_question(req.question, ds)          # deterministic table + fallback text
    table = det.get("table")
    context_json = _labor_context_json(ds)

    # Headline metric pills shown on the answer card. Prefer the question-specific
    # set from the router (e.g. the actual shift's cost/hours/rate for "most
    # expensive shift") so the card is always relevant to what was asked; fall
    # back to the general labor snapshot for cost/summary questions.
    metrics = det.get("metrics") or [
        {"label": "Labor Cost", "value": _usd(ds["labor_cost"])},
        {"label": "Labor Cost %",
         "value": f"{ds['labor_cost_pct']}%" if ds["labor_cost_pct"] is not None else "—"},
        {"label": "Overtime", "value": f"{ds['overtime_hours']}h"},
        {"label": "Rev / Labor-hr",
         "value": f"{_usd(ds['revenue_per_hour'])}/h"
                  if ds["revenue_per_hour"] is not None else "—"},
    ]

    import ai_service  # lazy import (keeps import order simple)

    async def gen():
        # 1) structured metrics + table + meta up front
        yield ("event: meta\ndata: "
               + json.dumps({"table": table, "metrics": metrics,
                             "period_label": label}) + "\n\n")
        # 2) stream the LLM explanation grounded in the computed numbers
        streamed = False
        try:
            async for tok in ai_service.stream_labor_reply(req.question, context_json):
                if tok:
                    streamed = True
                    yield "event: delta\ndata: " + json.dumps({"text": tok}) + "\n\n"
        except Exception:
            pass
        # 3) fallback to the deterministic answer if the LLM produced nothing
        if not streamed:
            yield "event: delta\ndata: " + json.dumps({"text": det["answer"]}) + "\n\n"
        yield "event: done\ndata: {}\n\n"

    return StreamingResponse(
        gen(), media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no",
                 "Connection": "keep-alive"},
    )

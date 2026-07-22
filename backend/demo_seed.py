"""
Demo-data seeder for the onboarding "Connect a POS" step.

We are not wired to any real POS API yet, so when an owner picks a POS provider
we instead populate their account with a realistic single-restaurant dataset:
menu, customers, ~30 days of orders (with line items), a staff roster, and labor
shifts spread across today / this week / last week / this / last month so every
screen (Home, Branches, Menu, Customers, Team) has something to show.

The restaurant is named after the `restaurant_name` the owner entered during
onboarding. Everything is scoped to the owner_id (tenant key) and marked with
DEMO_* ids so re-connecting (or switching providers) can wipe and reseed cleanly
without ever touching real data.
"""
from __future__ import annotations

import random
from datetime import datetime, timedelta, timezone

from sqlalchemy import text
from sqlalchemy.orm import Session

from database import (
    Customer, Employee, MenuItem, Order, OrderItem, Restaurant, Shift,
)

# Deterministic-per-owner uuid for the demo restaurant, so a reseed reuses the
# same restaurant row (and its FKs) instead of orphaning one.
def _demo_restaurant_id(owner_id: int) -> str:
    return f"demo0000-0000-4000-8000-{owner_id:012d}"


# --- static catalog / name pools (mirrors mock_data shapes) ------------------
_MENU = [
    ("BLT Sandwich",        "Sandwiches",   13.37, 4.10, False),
    ("Belgian Waffle",      "Breakfast",    10.69, 2.40, False),
    ("Beverage Bar",        "Drinks",        4.79, 0.80, False),
    ("Bacon & Eggs",        "Breakfast",    11.39, 3.20, True),
    ("Baby's Best Burger",  "Burgers",       4.69, 1.50, False),
    ("Bacon Burger",        "Burgers",       9.19, 3.30, True),
    ("BBQ Ribs Platter",    "Mains",        22.50, 7.40, True),
    ("Truffle Fries",       "Sides",         8.50, 1.90, False),
    ("Caesar Salad",        "Salads",       11.99, 2.80, False),
    ("Kids Mac & Cheese",   "Just for Kids", 6.99, 1.70, False),
    ("Chocolate Lava Cake", "Desserts",      7.49, 1.40, False),
    ("Iced Latte",          "Drinks",        5.25, 0.70, False),
]

_CHANNELS = ["Dine In", "To-Go", "Delivery"]
_FIRST = ["Alex", "Sam", "Jordan", "Taylor", "Riley", "Casey", "Morgan", "Quinn",
          "Drew", "Skyler", "Reese", "Avery", "Hayden", "Cameron", "Devon",
          "Emerson", "Finley", "Harper", "Jamie", "Kendall"]
_LAST = ["Patel", "Nguyen", "Smith", "Garcia", "Chen", "Kim", "Brown", "Lee",
         "Lopez", "Wilson", "Davis", "Singh", "Martinez", "Jha", "Khan", "Rao",
         "Mehta", "Park", "Carter", "Reyes"]

# (given, family, title, hourly_rate, tax_declared, advance_taken, advance_amt)
_STAFF = [
    ("Marcus", "Bennett", "Manager",   32.0, True,  False, None),
    ("Elena",  "Rossi",   "Chef",      25.0, True,  False, None),
    ("Priya",  "Patel",   "Chef",      19.5, True,  True,  150.0),
    ("Tom",    "Nguyen",  "Cashier",   16.5, False, False, None),
    ("Raj",    "Sharma",  "Cashier",   16.0, False, True,  200.0),
    ("Sarah",  "Khan",    "Server",    15.0, True,  False, None),
    ("Alex",   "Carter",  "Server",    14.5, True,  False, None),
    ("Jordan", "Lee",     "Server",    14.0, False, False, None),
    ("Mia",    "Garcia",  "Busser",    13.5, True,  False, None),
    ("Leo",    "Martins", "Busser",    13.0, False, True,  100.0),
    ("Nina",   "Okafor",  "Server",    14.0, True,  False, None),
]

_OT_THRESHOLD = 8.0  # net hours over this in one shift = overtime (matches Team KPIs)


def _demand_weight(price: float, featured: bool, category: str) -> float:
    w = 60.0 / (price ** 0.55)
    if featured:
        w *= 1.7
    cat = category.lower()
    if any(k in cat for k in ("burger", "sandwich", "breakfast", "side", "kid")):
        w *= 1.6
    elif any(k in cat for k in ("salad", "drink", "dessert")):
        w *= 1.2
    return max(w, 0.05)


def _clear_demo_rows(db: Session, owner_id: int) -> None:
    """Remove any previously-seeded demo rows for this owner (FK-safe order).

    Scoped to DEMO_* markers so an owner's real restaurants/orders are untouched.
    order_items cascade from orders at the DB level (FK ondelete=CASCADE)."""
    rid = _demo_restaurant_id(owner_id)
    db.query(Shift).filter(
        Shift.owner_id == owner_id, Shift.square_id.like("DEMO_SH_%")
    ).delete(synchronize_session=False)
    db.query(Employee).filter(
        Employee.owner_id == owner_id, Employee.square_id.like("DEMO_TM_%")
    ).delete(synchronize_session=False)
    db.query(Order).filter(
        Order.owner_id == owner_id, Order.id.like("DEMOORD_%")
    ).delete(synchronize_session=False)
    db.query(MenuItem).filter(
        MenuItem.owner_id == owner_id, MenuItem.id.like("DEMOMENU_%")
    ).delete(synchronize_session=False)
    db.query(Customer).filter(
        Customer.owner_id == owner_id, Customer.id.like("DEMOCUST_%")
    ).delete(synchronize_session=False)
    db.query(Restaurant).filter(
        Restaurant.owner_id == owner_id, Restaurant.id == rid
    ).delete(synchronize_session=False)
    db.flush()


def seed_demo_for_owner(db: Session, owner_id: int, restaurant_name: str,
                        provider: str = "square") -> dict:
    """Seed a full single-restaurant demo dataset for `owner_id`.

    Idempotent: clears prior demo rows first, so re-connecting a POS (or picking
    a different one) reseeds cleanly. Returns row counts for the API response.
    """
    # Deterministic per owner so reseeds are stable, but varied between owners.
    rng = random.Random(1000 + owner_id)
    now = datetime.now(timezone.utc)
    today = now.replace(hour=0, minute=0, second=0, microsecond=0)
    name = (restaurant_name or "My Restaurant").strip() or "My Restaurant"

    _clear_demo_rows(db, owner_id)

    rid = _demo_restaurant_id(owner_id)
    restaurant = Restaurant(
        id=rid, owner_id=owner_id, name=name, city="San Francisco",
        address="500 Market St, San Francisco, CA", manager="Marcus Bennett",
        phone="+14155550100", square_location_id="DEMO_LOC", is_active=True,
    )
    db.add(restaurant)
    db.flush()  # parent must exist before menu / customers / orders FK to it

    # --- menu ---
    menu_rows: list[MenuItem] = []
    for i, (mname, cat, price, cost, featured) in enumerate(_MENU, 1):
        m = MenuItem(
            id=f"DEMOMENU_{owner_id}_{i:02d}", owner_id=owner_id, restaurant_id=rid,
            name=mname, category=cat, price=price, cost=cost,
            featured=featured, is_active=True,
        )
        menu_rows.append(m)
        db.add(m)
    weights = [_demand_weight(m.price, m.featured, m.category) for m in menu_rows]
    db.flush()  # menu rows must exist before order_items FK to them

    # --- customers ---
    cust_rows: list[Customer] = []
    for i in range(1, 121):
        first, last = rng.choice(_FIRST), rng.choice(_LAST)
        visits = rng.choices([1, 2, 3, 5, 8, 14, 22], weights=[40, 25, 15, 10, 5, 3, 2])[0]
        days_ago = rng.choices([0, 1, 2, 4, 7, 14, 30, 60, 90],
                               weights=[8, 12, 15, 15, 15, 15, 10, 6, 4])[0]
        avg_spend = round(rng.uniform(12.0, 65.0), 2)
        tags = (
            (["vip"] if visits >= 8 and days_ago <= 14 else [])
            + (["at_risk"] if days_ago >= 30 else [])
            + (["new"] if visits == 1 else [])
        )
        c = Customer(
            id=f"DEMOCUST_{owner_id}_{i:04d}", owner_id=owner_id, restaurant_id=rid,
            name=f"{first} {last}",
            phone=f"+1-415-555-{rng.randint(1000, 9999):04d}",
            email=f"{first.lower()}.{last.lower()}{i}@example.com",
            visits=visits, last_visit_at=today - timedelta(days=days_ago),
            avg_spend=avg_spend, lifetime_value=round(visits * avg_spend, 2),
            loyalty_points=visits * rng.randint(5, 22), tags=tags,
        )
        cust_rows.append(c)
        db.add(c)
    db.flush()  # customers must exist before orders FK to them

    # --- orders (last 30 days) + line items ---
    n_orders = 0
    n_items = 0
    hour_weights = [2, 3, 5, 8, 15, 18, 14, 8, 5, 6, 9, 12, 10, 7, 4, 2]  # 07..22
    for d in range(30):
        day = today - timedelta(days=29 - d)
        weekend = day.weekday() >= 5
        count = max(8, int(rng.gauss(22 * (1.18 if weekend else 1.0), 5)))
        for _ in range(count):
            hour = rng.choices(range(7, 23), weights=hour_weights)[0]
            ts = day.replace(hour=hour, minute=rng.randint(0, 59))
            n_line = rng.choices([1, 2, 3, 4, 5], weights=[15, 38, 25, 15, 7])[0]
            items, subtotal = [], 0.0
            for _ in range(n_line):
                m = rng.choices(menu_rows, weights=weights)[0]
                qty = rng.choices([1, 2, 3], weights=[80, 15, 5])[0]
                items.append(OrderItem(
                    id=f"DEMOOI_{owner_id}_{n_items+1:07d}", menu_item_id=m.id,
                    name=m.name, qty=qty, price=m.price, cost=m.cost,
                ))
                subtotal += m.price * qty
                n_items += 1
            tax = round(subtotal * 0.0875, 2)
            tip = round(subtotal * rng.choices(
                [0, 0.10, 0.15, 0.18, 0.20, 0.25],
                weights=[20, 10, 15, 28, 20, 7])[0], 2)
            cust = rng.choice(cust_rows)
            n_orders += 1
            db.add(Order(
                id=f"DEMOORD_{owner_id}_{n_orders:06d}", owner_id=owner_id,
                restaurant_id=rid, customer_id=cust.id, placed_at=ts,
                channel=rng.choices(_CHANNELS, weights=[55, 28, 17])[0],
                subtotal=round(subtotal, 2), tax=tax, tip=tip,
                total=round(subtotal + tax + tip, 2),
                wait_minutes=rng.choices([4, 6, 9, 12, 16, 22, 30],
                                         weights=[10, 25, 30, 18, 10, 5, 2])[0],
                rating=rng.choices([3, 4, 5], weights=[10, 40, 50])[0],
                items=items,
            ))

    # --- team members ---
    emp_rows: list[Employee] = []
    for i, (given, family, title, rate, tax, adv, amt) in enumerate(_STAFF, 1):
        e = Employee(
            id=f"demo0000-0000-4000-9000-{owner_id:07d}{i:05d}", owner_id=owner_id,
            restaurant_id=rid, square_id=f"DEMO_TM_{owner_id}_{i:02d}",
            square_location_id="DEMO_LOC", given_name=given, family_name=family,
            email=f"{given.lower()}.{family.lower()}@example.com", phone=None,
            status="ACTIVE", is_owner=False, title=title, hourly_rate=rate,
            tax_declared=tax, advance_taken=adv, advance_amount=amt,
            advance_date=(today - timedelta(days=6) if adv else None),
        )
        emp_rows.append(e)
        db.add(e)
    db.flush()  # assign employee ids for shift FKs

    # --- labor shifts: spread across the date-filter buckets ---
    # Each rep day gets Overtime (Manager, ~10h), Late (a Cashier), Missed (a
    # Busser), and normal shifts, so every Team KPI card has data in every
    # period. Rep days: today, yesterday, this-week, last-week, earlier-this-
    # month, last-month.
    rep_offsets = [0, 1, 2, 8, 15, 34]  # days ago (34 lands in the previous month)
    n_shifts = 0
    for off in rep_offsets:
        day = today - timedelta(days=off)
        for j, e in enumerate(emp_rows):
            role = (e.title or "").lower()
            # Rotate who works which day a bit so it's not identical every day.
            if (j + off) % 3 == 2 and off not in (0, 1):
                continue
            n_shifts += 1
            sid = f"DEMO_SH_{owner_id}_{n_shifts:04d}"
            base = dict(owner_id=owner_id, employee_id=e.id, restaurant_id=rid,
                        square_id=sid, square_team_member_id=e.square_id,
                        square_location_id="DEMO_LOC")
            if "manager" in role:  # overtime
                db.add(Shift(**base, clock_in=day.replace(hour=8),
                             clock_out=day.replace(hour=18, minute=30),
                             status="COMPLETED", declared_tips=0.0, break_hours=0.5,
                             meal_taken=True, late_clockin=False, missed_clockin=False))
            elif "cashier" in role and j % 2 == 0:  # late
                db.add(Shift(**base, clock_in=day.replace(hour=11, minute=18),
                             clock_out=day.replace(hour=19),
                             status="COMPLETED", declared_tips=round(rng.uniform(20, 60), 2),
                             break_hours=0.5, meal_taken=True, late_clockin=True,
                             missed_clockin=False))
            elif "busser" in role and j % 2 == 1:  # missed (no-show)
                db.add(Shift(**base, clock_in=day.replace(hour=16), clock_out=None,
                             status="MISSED", declared_tips=0.0, break_hours=0.0,
                             meal_taken=False, late_clockin=False, missed_clockin=True))
            else:  # normal
                db.add(Shift(**base, clock_in=day.replace(hour=9),
                             clock_out=day.replace(hour=16),
                             status="COMPLETED", declared_tips=round(rng.uniform(40, 95), 2),
                             break_hours=0.5, meal_taken=True, late_clockin=False,
                             missed_clockin=False))

    db.commit()
    return {
        "restaurant": name,
        "provider": provider,
        "menu_items": len(menu_rows),
        "customers": len(cust_rows),
        "orders": n_orders,
        "order_items": n_items,
        "team_members": len(emp_rows),
        "labor_shifts": n_shifts,
    }

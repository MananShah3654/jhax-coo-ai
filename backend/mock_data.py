"""
JHAX - Deterministic mock restaurant data generator.

Seeded with a fixed RNG so the same data is returned every cold start.
Represents a 4-branch restaurant chain "Jha Bistro" with 30 days of
orders, customers, menu performance, tips, and operational metrics.
"""
from __future__ import annotations

import random
from datetime import datetime, timedelta, timezone
from typing import Dict, List

RNG = random.Random(42)

# `seats` / `tables` = physical dining capacity per branch. They power the
# seating KPIs (Table Turnover Rate, RevPASH) — a POS like Square can't report
# these, so they live on the branch record. ~4 seats per table.
BRANCHES: List[Dict] = [
    {"id": "br_downtown", "name": "Downtown",      "city": "San Francisco", "manager": "Avinn", "seats": 96, "tables": 24},
    {"id": "br_marina",   "name": "Marina",        "city": "San Francisco", "manager": "Priya", "seats": 72, "tables": 18},
    {"id": "br_palo_alto","name": "Palo Alto",     "city": "Palo Alto",     "manager": "Rohan", "seats": 56, "tables": 14},
    {"id": "br_sj",       "name": "San Jose",      "city": "San Jose",      "manager": "Diego", "seats": 48, "tables": 12},
]

# Business hours 07:00–22:00 (matches the hourly order distribution below and
# the 7–22 windows in analytics). Available seat-hours = seats × this × days,
# the denominator for RevPASH (Revenue Per Available Seat-Hour).
SERVICE_HOURS_PER_DAY = 15

MENU_ITEMS: List[Dict] = [
    {"id": "m_btl_sand",  "name": "BLT Sandwich",         "category": "Sandwiches", "price": 13.37, "cost": 4.10},
    {"id": "m_bel_waf",   "name": "Belgian Waffle",       "category": "Breakfast",  "price": 10.69, "cost": 2.40},
    {"id": "m_bev_bar",   "name": "Beverage Bar",         "category": "Drinks",     "price": 4.79,  "cost": 0.80},
    {"id": "m_bacon_egg", "name": "Bacon & Eggs",         "category": "Breakfast",  "price": 11.39, "cost": 3.20},
    {"id": "m_bb_burger", "name": "Baby's Best Burger",   "category": "Burgers",    "price": 4.69,  "cost": 1.50},
    {"id": "m_bacon_bur", "name": "Bacon Burger",         "category": "Burgers",    "price": 9.19,  "cost": 3.30},
    {"id": "m_bbq_ribs",  "name": "BBQ Ribs Platter",     "category": "Mains",      "price": 22.50, "cost": 7.40},
    {"id": "m_truffle_f", "name": "Truffle Fries",        "category": "Sides",      "price": 8.50,  "cost": 1.90},
    {"id": "m_caesar",    "name": "Caesar Salad",         "category": "Salads",     "price": 11.99, "cost": 2.80},
    {"id": "m_kids_mac",  "name": "Kids Mac & Cheese",    "category": "Just for Kids", "price": 6.99, "cost": 1.70},
    {"id": "m_choco_lava","name": "Chocolate Lava Cake",  "category": "Desserts",   "price": 7.49,  "cost": 1.40},
    {"id": "m_iced_latte","name": "Iced Latte",           "category": "Drinks",     "price": 5.25,  "cost": 0.70},
]

CHANNELS = ["Dine In", "To-Go", "Delivery"]

FIRST_NAMES = ["Alex","Sam","Jordan","Taylor","Riley","Casey","Morgan","Quinn","Drew","Skyler",
               "Reese","Avery","Hayden","Cameron","Devon","Emerson","Finley","Harper","Jamie","Kendall"]
LAST_NAMES  = ["Patel","Nguyen","Smith","Garcia","Chen","Kim","Brown","Lee","Lopez","Wilson",
               "Davis","Singh","Martinez","Jha","Khan","Rao","Mehta","Park","Carter","Reyes"]


def _gen_customers(n: int = 240) -> List[Dict]:
    customers = []
    for i in range(n):
        first = RNG.choice(FIRST_NAMES)
        last = RNG.choice(LAST_NAMES)
        visits = RNG.choices([1,2,3,5,8,14,22], weights=[40,25,15,10,5,3,2])[0]
        last_visit_days_ago = RNG.choices([0,1,2,4,7,14,30,60,90], weights=[8,12,15,15,15,15,10,6,4])[0]
        avg_spend = round(RNG.uniform(12.0, 65.0), 2)
        loyalty_pts = visits * RNG.randint(5, 22)
        customers.append({
            "id": f"c_{i+1:04d}",
            "name": f"{first} {last}",
            "phone": f"+1-415-555-{RNG.randint(1000,9999):04d}",
            "email": f"{first.lower()}.{last.lower()}{i}@example.com",
            "visits": visits,
            "last_visit_days_ago": last_visit_days_ago,
            "avg_spend": avg_spend,
            "lifetime_value": round(visits * avg_spend, 2),
            "loyalty_points": loyalty_pts,
            "favorite_branch": RNG.choice(BRANCHES)["id"],
            "tags": (
                (["vip"] if visits >= 8 and last_visit_days_ago <= 14 else [])
                + (["at_risk"] if last_visit_days_ago >= 30 else [])
                + (["new"] if visits == 1 else [])
            ),
        })
    return customers


def _demand_weight(item: Dict) -> float:
    """Estimate relative demand for a menu item from its REAL attributes.

    Uses only real menu data (price, featured flag, category) so that
    simulated order volume is realistic instead of uniform. Cheaper items
    sell more units; featured items get a lift; everyday categories (burgers,
    sandwiches, breakfast, sides) outsell niche ones (wine, champagne).
    This is what makes 'most profitable' vs 'underperforming' meaningful
    rather than a plain price sort. Real order data (when a token is wired)
    replaces this entirely.
    """
    price = item.get("price") or 1.0
    # Price elasticity: lower price -> more units (gentle inverse curve).
    w = 60.0 / (price ** 0.55)
    if item.get("featured"):
        w *= 1.7
    cat = (item.get("category") or "").lower()
    if any(k in cat for k in ("burger", "sandwich", "breakfast", "side", "kid", "great stuff")):
        w *= 1.6
    elif any(k in cat for k in ("salad", "beverage", "goodies", "draft", "bottled")):
        w *= 1.2
    elif any(k in cat for k in ("wine", "champagne", "cocktail")):
        w *= 0.45
    return max(w, 0.05)


def _gen_orders(customers: List[Dict], menu: List[Dict] | None = None,
                days: int = 30) -> List[Dict]:
    menu = menu or MENU_ITEMS
    menu_weights = [_demand_weight(m) for m in menu]
    orders: List[Dict] = []
    today = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
    # Branch base volume (orders per day)
    base_per_branch = {
        "br_downtown": 92,
        "br_marina":   74,
        "br_palo_alto":58,
        "br_sj":       41,   # underperformer
    }
    for d in range(days):
        day = today - timedelta(days=days - 1 - d)
        weekend = day.weekday() >= 5
        for br in BRANCHES:
            # Lunch traffic deliberately drops over last 7 days for downtown to create a story
            base = base_per_branch[br["id"]]
            if br["id"] == "br_downtown" and d >= days - 7:
                base = int(base * 0.78)
            count = max(8, int(RNG.gauss(base * (1.18 if weekend else 1.0), 8)))
            for _ in range(count):
                hour = RNG.choices(range(7, 23),
                                   weights=[2,3,5,8,15,18,14,8,5,6,9,12,10,7,4,2])[0]
                ts = day.replace(hour=hour, minute=RNG.randint(0,59))
                n_items = RNG.choices([1,2,3,4,5], weights=[15,38,25,15,7])[0]
                items = []
                subtotal = 0.0
                for _ in range(n_items):
                    m = RNG.choices(menu, weights=menu_weights)[0]
                    qty = RNG.choices([1,2,3], weights=[80,15,5])[0]
                    items.append({"menu_id": m["id"], "name": m["name"], "qty": qty,
                                  "price": m["price"], "cost": m["cost"]})
                    subtotal += m["price"] * qty
                # Per-order discount: most orders carry none, some a promo.
                # Tracked as real POS data so the discount-overuse signal works.
                discount_pct = RNG.choices([0, 0.10, 0.15, 0.20, 0.25],
                                           weights=[70, 12, 9, 6, 3])[0]
                discount = round(subtotal * discount_pct, 2)
                tax = round((subtotal - discount) * 0.0875, 2)
                tip_pct = RNG.choices([0,0.10,0.15,0.18,0.20,0.25], weights=[20,10,15,28,20,7])[0]
                tip = round(subtotal * tip_pct, 2)
                total = round(subtotal - discount + tax + tip, 2)
                cust = RNG.choice(customers)
                # party_size = covers (guests) on the order. Drives the Covers
                # KPI; the party count on dine-in orders also drives Table
                # Turnover (one seated party ≈ one table turn).
                party_size = RNG.choices([1,2,3,4,5,6], weights=[22,34,18,14,8,4])[0]
                orders.append({
                    "id": f"o_{len(orders)+1:06d}",
                    "branch_id": br["id"],
                    "ts": ts.isoformat(),
                    "channel": RNG.choices(CHANNELS, weights=[55,28,17])[0],
                    "customer_id": cust["id"],
                    "items": items,
                    "party_size": party_size,
                    "subtotal": round(subtotal, 2),
                    "discount": discount,
                    "tax": tax,
                    "tip": tip,
                    "total": total,
                    "wait_minutes": RNG.choices([4,6,9,12,16,22,30], weights=[10,25,30,18,10,5,2])[0],
                    "rating": RNG.choices([3,4,5], weights=[10,40,50])[0],
                })
    return orders


def _gen_carts(orders: List[Dict], abandon_prob: float = 0.28) -> List[Dict]:
    """Abandoned online checkout sessions — the denominator half a POS never sees.

    Cart Abandonment Rate only makes sense for online channels (To-Go / Delivery),
    where a guest can start a checkout and bail. Dine-in walk-ins have no cart. For
    each completed online order we emit an abandoned session with probability
    `abandon_prob`, so the rate = abandoned / (abandoned + completed-online) lands
    around 22%. These sessions are NOT orders — they exist only in this stream, so
    a source without it (e.g. Square) honestly reports the KPI as unavailable.
    """
    carts: List[Dict] = []
    for o in orders:
        channel = (o.get("channel") or "").strip().lower()
        if channel in ("to-go", "delivery") and RNG.random() < abandon_prob:
            carts.append({
                "id": f"cart_{len(carts)+1:06d}",
                "branch_id": o["branch_id"],
                "ts": o["ts"],                      # session time (never became an order)
                "channel": o["channel"],
                "cart_value": o["subtotal"],
                "abandoned_at": RNG.choice(["cart", "checkout", "payment"]),
            })
    return carts


def build_dataset(menu: List[Dict] | None = None,
                  owner: Dict | None = None) -> Dict:
    """Build a deterministic dataset.

    Pass `menu` to generate orders against a real menu (e.g. the live
    Knowlwood catalog) while keeping the seeded branch/customer/order
    generation. Falls back to the built-in demo menu when omitted.
    """
    # Reseed so a caller-supplied menu still yields deterministic output.
    RNG.seed(42)
    menu = menu or MENU_ITEMS
    customers = _gen_customers()
    # Generate a full quarter of orders so weekly / 15-day / monthly /
    # quarterly views all have real underlying data.
    orders = _gen_orders(customers, menu, days=90)
    carts = _gen_carts(orders)
    return {
        "owner": owner or {"name": "Manan", "restaurant": "Jha Bistro"},
        "branches": BRANCHES,
        "menu": menu,
        "customers": customers,
        "orders": orders,
        "carts": carts,
    }


DATASET = build_dataset()

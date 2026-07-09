"""
One-off helper to seed a Square *sandbox* account with a large, realistic
dataset (customers + orders) so the COO dashboard looks full during demos.

It reads SQUARE_ACCESS_TOKEN / SQUARE_ENVIRONMENT from backend/.env (never
hardcodes a token) and only ever talks to the sandbox host.

    ./venv/Scripts/python.exe seed_square_sandbox.py

What it does:
  * Reuses the menu items already in the Square catalog (does NOT create new
    catalog items). If the catalog is empty it bootstraps 6 categorized items.
  * Tops customers up to TARGET_CUSTOMERS with varied names/emails/phones.
  * Generates orders with tiered per-customer visit counts:
      - heavy spenders  (many orders -> VIP)
      - regulars        (a handful of orders)
      - occasional      (1-3 orders -> new / one-time)
    Orders reference existing catalog variations; Square prices them.

NOTE on dates: Square stamps every order created_at = "now" and rejects
backdated orders, so these orders all land today. To make the 30-day / weekly
/ monthly views and the At-Risk segment look realistic, the READ side
(SquareDataSource, gated by SQUARE_DEMO_SPREAD_DAYS in .env) spreads the order
timestamps across time at read-time. That spreading is a labelled demo aid;
this script only creates the real orders.

After it finishes it re-runs the data_source verification so you can see the
new volume and customer segments.
"""
from __future__ import annotations

import datetime as dt
import random
import uuid
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import httpx
from dotenv import load_dotenv

load_dotenv(Path(__file__).with_name(".env"))

import os  # noqa: E402  (after load_dotenv so env is populated)

TOKEN = os.environ.get("SQUARE_ACCESS_TOKEN", "")
ENV = os.environ.get("SQUARE_ENVIRONMENT", "sandbox").lower()
BASE = (
    "https://connect.squareupsandbox.com"
    if ENV == "sandbox"
    else "https://connect.squareup.com"
)
SQUARE_VERSION = "2024-10-17"

if ENV != "sandbox":
    raise SystemExit("Refusing to seed a non-sandbox environment. Set SQUARE_ENVIRONMENT=sandbox.")
if not TOKEN:
    raise SystemExit("SQUARE_ACCESS_TOKEN is empty in backend/.env")

HEADERS = {
    "Authorization": f"Bearer {TOKEN}",
    "Square-Version": SQUARE_VERSION,
    "Content-Type": "application/json",
}

RNG = random.Random(42)

TARGET_CUSTOMERS = 100         # topped up from whatever already exists
TARGET_ORDERS = 1000           # topped up toward (orders can't be deleted)

# Name pools for varied test customers.
FIRST_NAMES = [
    "Alex", "Sam", "Jordan", "Taylor", "Riley", "Casey", "Morgan", "Quinn",
    "Drew", "Skyler", "Reese", "Avery", "Hayden", "Cameron", "Devon", "Emerson",
    "Finley", "Harper", "Jamie", "Kendall", "Logan", "Parker", "Rowan", "Sawyer",
    "Blake", "Dakota", "Elliot", "Frankie", "Gray", "Marlow",
]
LAST_NAMES = [
    "Patel", "Nguyen", "Smith", "Garcia", "Chen", "Kim", "Brown", "Lee",
    "Lopez", "Wilson", "Davis", "Singh", "Martinez", "Jha", "Khan", "Rao",
    "Mehta", "Park", "Carter", "Reyes", "Flores", "Bennett", "Nakamura",
    "Okafor", "Rossi", "Haddad", "Novak", "Silva", "Cohen", "Adeyemi",
]

# Bootstrap menu (only used if the catalog is empty). (name, price_cents, category)
MENU = [
    ("Cheeseburger", 950, "Burgers"),
    ("BLT Sandwich", 1337, "Sandwiches"),
    ("Truffle Fries", 850, "Sides"),
    ("Caesar Salad", 1199, "Salads"),
    ("Iced Latte", 525, "Drinks"),
    ("Chocolate Lava Cake", 749, "Desserts"),
]


def _post(path: str, body: dict) -> dict:
    r = httpx.post(f"{BASE}{path}", headers=HEADERS, json=body, timeout=20.0)
    if r.status_code >= 300:
        print(f"  ! {path} -> {r.status_code}: {r.text[:300]}")
        r.raise_for_status()
    return r.json()


def get_location_id() -> str:
    r = httpx.get(f"{BASE}/v2/locations", headers=HEADERS, timeout=15.0)
    r.raise_for_status()
    locs = r.json().get("locations") or []
    if not locs:
        raise SystemExit("No sandbox locations found.")
    print(f"Location: {locs[0]['id']} ({locs[0].get('name')})")
    return locs[0]["id"]


def get_variation_ids() -> list[str]:
    """Read the ITEM_VARIATION ids already in the catalog — we generate orders
    against these, never creating new catalog items."""
    data = _post("/v2/catalog/search-catalog-items", {"limit": 100})
    var_ids: list[str] = []
    for it in data.get("items") or []:
        for v in (it.get("item_data") or {}).get("variations") or []:
            if v.get("id"):
                var_ids.append(v["id"])
    return var_ids


def seed_catalog() -> list[str]:
    """Bootstrap categories + menu items ONLY when the catalog is empty; returns
    the created ITEM_VARIATION ids."""
    objects = []
    cat_client_id = {}
    for i, cname in enumerate(sorted({c for _, _, c in MENU})):
        cid = f"#cat_{i}"
        cat_client_id[cname] = cid
        objects.append({"type": "CATEGORY", "id": cid, "category_data": {"name": cname}})
    for i, (name, price, cname) in enumerate(MENU):
        cid = cat_client_id[cname]
        objects.append({
            "type": "ITEM",
            "id": f"#item_{i}",
            "item_data": {
                "name": name,
                "categories": [{"id": cid}],
                "reporting_category": {"id": cid},
                "variations": [{
                    "type": "ITEM_VARIATION",
                    "id": f"#var_{i}",
                    "item_variation_data": {
                        "name": "Regular",
                        "pricing_type": "FIXED_PRICING",
                        "price_money": {"amount": price, "currency": "USD"},
                    },
                }],
            },
        })
    resp = _post("/v2/catalog/batch-upsert", {
        "idempotency_key": str(uuid.uuid4()),
        "batches": [{"objects": objects}],
    })
    mappings = {m["client_object_id"]: m["object_id"] for m in resp.get("id_mappings", [])}
    var_ids = [mappings[f"#var_{i}"] for i in range(len(MENU)) if f"#var_{i}" in mappings]
    print(f"Catalog bootstrap: {len(cat_client_id)} categories, {len(MENU)} items")
    return var_ids


def ensure_customers(target: int) -> list[str]:
    """Reuse existing customers and create new ones until we reach `target`, so
    re-runs top up rather than duplicating the whole set."""
    r = httpx.get(f"{BASE}/v2/customers", headers=HEADERS, timeout=15.0)
    r.raise_for_status()
    ids = [c["id"] for c in (r.json().get("customers") or [])]
    have = len(ids)
    to_make = max(0, target - have)
    # Valid US area codes + the 555 exchange keep libphonenumber (Square's
    # validator) happy while still varying the numbers.
    area_codes = ["212", "213", "312", "415", "202", "305", "404", "512", "617", "702"]
    for i in range(to_make):
        first = RNG.choice(FIRST_NAMES)
        last = RNG.choice(LAST_NAMES)
        n = have + i
        resp = _post("/v2/customers", {
            "idempotency_key": str(uuid.uuid4()),
            "given_name": first,
            "family_name": last,
            "email_address": f"{first.lower()}.{last.lower()}{n}@example.com",
            "phone_number": f"+1{RNG.choice(area_codes)}555{RNG.randint(1000, 9999)}",
        })
        ids.append(resp["customer"]["id"])
    print(f"Customers: {have} existing + {to_make} created = {len(ids)} total")
    return ids


def count_orders(location_id: str) -> int:
    """Count existing orders so we only top up toward TARGET_ORDERS (orders
    can't be deleted, so the script converges on the target instead of
    duplicating the whole set on every run)."""
    start_at = (dt.datetime.now(dt.timezone.utc) - dt.timedelta(days=365)).isoformat()
    total, cursor = 0, None
    for _ in range(40):
        body = {
            "location_ids": [location_id],
            "query": {"filter": {"date_time_filter": {"created_at": {"start_at": start_at}}}},
            "limit": 500,
        }
        if cursor:
            body["cursor"] = cursor
        data = _post("/v2/orders/search", body)
        total += len(data.get("orders") or [])
        cursor = data.get("cursor")
        if not cursor:
            break
    return total


def _tier_weight(index: int) -> int:
    """Weight a customer's share of order volume so segments emerge: heavy
    spenders (VIP), regulars, and occasional/one-time visitors."""
    if index < 25:
        return 12   # heavy -> VIP
    if index < 60:
        return 4    # regulars
    return 1        # occasional / one-time


def build_order_specs(customer_ids: list[str], var_ids: list[str], n_orders: int) -> list[dict]:
    """Distribute `n_orders` across customers by tier weight so a few customers
    rack up many visits (VIP) while most order occasionally."""
    if n_orders <= 0:
        return []
    weights = [_tier_weight(i) for i in range(len(customer_ids))]
    chosen = RNG.choices(customer_ids, weights=weights, k=n_orders)
    specs = []
    for cid in chosen:
        lines = [
            {"quantity": str(RNG.choices([1, 2, 3], weights=[80, 15, 5])[0]),
             "catalog_object_id": vid}
            for vid in RNG.sample(var_ids, k=RNG.randint(1, min(3, len(var_ids))))
        ]
        specs.append({"customer_id": cid, "line_items": lines})
    return specs


def create_orders(location_id: str, specs: list[dict]) -> int:
    """Create orders concurrently (Square stamps them all 'now'; the read side
    spreads the dates)."""
    def _one(spec: dict) -> bool:
        for attempt in range(3):
            r = httpx.post(f"{BASE}/v2/orders", headers=HEADERS, timeout=20.0, json={
                "idempotency_key": str(uuid.uuid4()),
                "order": {
                    "location_id": location_id,
                    "customer_id": spec["customer_id"],
                    "line_items": spec["line_items"],
                },
            })
            if r.status_code < 300:
                return True
            if r.status_code in (429, 500, 503) and attempt < 2:
                continue
            print(f"  ! order -> {r.status_code}: {r.text[:160]}")
            return False
        return False

    made = 0
    with ThreadPoolExecutor(max_workers=6) as pool:
        for i, ok in enumerate(pool.map(_one, specs), 1):
            made += 1 if ok else 0
            if i % 100 == 0:
                print(f"  ...{i}/{len(specs)} orders")
    print(f"Orders: created {made}/{len(specs)}")
    return made


def main() -> None:
    print(f"Seeding Square sandbox at {BASE}\n")
    loc = get_location_id()
    var_ids = get_variation_ids()
    if not var_ids:
        print("Catalog is empty — bootstrapping menu items")
        var_ids = seed_catalog()
    print(f"Using {len(var_ids)} existing catalog variations")
    cust_ids = ensure_customers(TARGET_CUSTOMERS)
    existing_orders = count_orders(loc)
    to_add = max(0, TARGET_ORDERS - existing_orders)
    print(f"Orders: {existing_orders} existing, target {TARGET_ORDERS} -> adding {to_add}")
    specs = build_order_specs(cust_ids, var_ids, to_add)
    create_orders(loc, specs)

    print("\n--- Re-running data_source verification ---")
    import data_source as ds

    ds._SOURCE = None  # reset the cached singleton
    s = ds.get_source()
    customers = s.customers()
    vip = [c for c in customers if "vip" in c["tags"]]
    at_risk = [c for c in customers if "at_risk" in c["tags"]]
    new = [c for c in customers if "new" in c["tags"]]
    print("source:", s.name)
    print("branches:", len(s.branches()))
    print("menu count:", len(s.menu()))
    print("orders count:", len(s.orders()))
    print("customers count:", len(customers))
    print(f"segments -> vip: {len(vip)} | at_risk: {len(at_risk)} | new: {len(new)}")


if __name__ == "__main__":
    main()

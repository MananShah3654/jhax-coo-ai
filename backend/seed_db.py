"""
DEV-ONLY seeder for the multi-tenant schema.

Creates one demo owner (a `User` row) and populates the new owner-scoped tables
from the deterministic mock dataset, so you can exercise the app end-to-end
without wiring Firebase or hand-entering data. NOT for production — real owners
create their data through the CRUD/onboarding endpoints (see crud_routes.py).

    python seed_db.py

Idempotent: it deletes the demo owner's existing rows first, then reloads.
Menu is restaurant-scoped in the new schema, so the shared mock menu is
replicated under each restaurant and orders are remapped to their restaurant's
copy to preserve referential integrity.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).parent / ".env")

from database import (  # noqa: E402
    Customer, MenuItem, Order, OrderItem, Restaurant, SessionLocal, User,
    get_or_create_user, init_db,
)
from mock_data import DATASET  # noqa: E402

DEMO_FIREBASE_UID = "demo-owner-seed"


def _parse(ts: str) -> datetime:
    dt = datetime.fromisoformat(ts)
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


def seed() -> None:
    init_db()
    with SessionLocal() as s:
        owner_info = DATASET["owner"]
        user = get_or_create_user(
            s, firebase_uid=DEMO_FIREBASE_UID,
            name=owner_info["name"], restaurant_name=owner_info["restaurant"],
        )

        # Wipe just this demo owner's data so re-seeding is deterministic.
        for model in (OrderItem, Order, Customer, MenuItem, Restaurant):
            if model is OrderItem:
                s.query(OrderItem).filter(OrderItem.order_id.in_(
                    s.query(Order.id).filter_by(owner_id=user.id)
                )).delete(synchronize_session=False)
            else:
                s.query(model).filter_by(owner_id=user.id).delete(
                    synchronize_session=False
                )
        s.commit()

        # Restaurants (old "branches") — map old id -> new Restaurant.
        rest_map: dict[str, Restaurant] = {}
        for b in DATASET["branches"]:
            r = Restaurant(owner_id=user.id, name=b["name"],
                           city=b.get("city"), manager=b.get("manager"))
            s.add(r)
            rest_map[b["id"]] = r
        s.flush()  # assign restaurant ids

        # Menu is restaurant-scoped: replicate the shared mock menu under each
        # restaurant. menu_map[(old_branch_id, old_menu_id)] -> new MenuItem.
        menu_map: dict[tuple[str, str], MenuItem] = {}
        for old_bid, r in rest_map.items():
            for m in DATASET["menu"]:
                mi = MenuItem(owner_id=user.id, restaurant_id=r.id,
                              name=m["name"], category=m.get("category", "Uncategorized"),
                              price=m["price"], cost=m["cost"])
                s.add(mi)
                menu_map[(old_bid, m["id"])] = mi
        s.flush()

        # Customers are owner-scoped.
        cust_map: dict[str, Customer] = {}
        for c in DATASET["customers"]:
            last_visit = None
            days_ago = c.get("last_visit_days_ago")
            if days_ago is not None:
                last_visit = datetime.now(timezone.utc) - timedelta(days=days_ago)
            cust = Customer(
                owner_id=user.id, name=c["name"], phone=c.get("phone"),
                email=c.get("email"), visits=c.get("visits", 0),
                last_visit_at=last_visit, avg_spend=c.get("avg_spend", 0.0),
                lifetime_value=c.get("lifetime_value", 0.0),
                loyalty_points=c.get("loyalty_points", 0), tags=c.get("tags", []),
            )
            s.add(cust)
            cust_map[c["id"]] = cust
        s.flush()

        # Orders + line items, remapped to their restaurant's menu copy.
        n_orders = 0
        for o in DATASET["orders"]:
            r = rest_map.get(o["branch_id"])
            if r is None:
                continue
            cust = cust_map.get(o.get("customer_id"))
            items = []
            for it in o["items"]:
                mi = menu_map.get((o["branch_id"], it["menu_id"]))
                items.append(OrderItem(
                    menu_item_id=mi.id if mi else None, name=it["name"],
                    qty=it["qty"], price=it["price"], cost=it["cost"],
                ))
            s.add(Order(
                owner_id=user.id, restaurant_id=r.id,
                customer_id=cust.id if cust else None,
                placed_at=_parse(o["ts"]), channel=o["channel"],
                subtotal=o["subtotal"], tax=o["tax"], tip=o["tip"],
                total=o["total"], wait_minutes=o["wait_minutes"],
                rating=o["rating"], items=items,
            ))
            n_orders += 1
        s.commit()

        print("Seeded demo owner:", {
            "user_id": user.id,
            "restaurants": len(rest_map),
            "menu_items": len(menu_map),
            "customers": len(cust_map),
            "orders": n_orders,
        })


if __name__ == "__main__":
    seed()

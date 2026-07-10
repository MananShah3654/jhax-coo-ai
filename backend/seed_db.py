"""
Seed the PostgreSQL database from the deterministic mock dataset.

Run once after creating the database:
    python seed_db.py

Idempotent: wipes and reloads the tables each run so you always get the
same seed=42 dataset the app was built against.
"""
from __future__ import annotations

from dotenv import load_dotenv
from pathlib import Path

load_dotenv(Path(__file__).parent / ".env")

from db import Base, Branch, Customer, MenuItem, Order, Owner, SessionLocal, engine, init_db  # noqa: E402
from mock_data import DATASET  # noqa: E402


def seed() -> None:
    # Fresh schema every run so re-seeding is deterministic.
    Base.metadata.drop_all(engine)
    init_db()

    with SessionLocal() as s:
        o = DATASET["owner"]
        s.add(Owner(name=o["name"], restaurant=o["restaurant"]))

        s.add_all(Branch(**b) for b in DATASET["branches"])
        s.add_all(MenuItem(**m) for m in DATASET["menu"])
        s.add_all(Customer(**c) for c in DATASET["customers"])
        s.add_all(Order(**ord_) for ord_ in DATASET["orders"])

        s.commit()

        counts = {
            "owner": 1,
            "branches": len(DATASET["branches"]),
            "menu_items": len(DATASET["menu"]),
            "customers": len(DATASET["customers"]),
            "orders": len(DATASET["orders"]),
        }
    print("Seeded PostgreSQL:", counts)


if __name__ == "__main__":
    seed()

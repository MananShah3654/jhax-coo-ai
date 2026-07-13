"""
One-time migration to the multi-tenant schema (one owner -> many restaurants).

Drops the legacy single-tenant business tables (which held only throwaway seed
data) and the old `owner`/`branches` tables, then recreates the unified schema
from database.py. The `users` table (Firebase identity) is PRESERVED.

    python migrate_multitenant.py

This is a DESTRUCTIVE dev/ops script — it is intentionally NOT part of the
app's startup init_db() (which is idempotent and never drops). Run it once when
moving an existing environment onto the new schema.
"""
from __future__ import annotations

from pathlib import Path

from dotenv import load_dotenv
from sqlalchemy import text

load_dotenv(Path(__file__).parent / ".env")

from database import Base, engine, init_db  # noqa: E402

# Order matters: children before parents (though CASCADE handles FKs anyway).
LEGACY_TABLES = [
    "order_items",
    "orders",
    "customers",
    "menu_items",
    "branches",   # old single-tenant table name for restaurants
    "owner",      # old redundant owner table
]


def migrate() -> None:
    with engine.begin() as conn:
        for tbl in LEGACY_TABLES:
            conn.execute(text(f'DROP TABLE IF EXISTS "{tbl}" CASCADE'))
    print("Dropped legacy business tables (users preserved).")

    init_db()  # create_all() for the unified schema
    print("Recreated unified multi-tenant schema:")
    for name in sorted(Base.metadata.tables):
        print(f"  - {name}")


if __name__ == "__main__":
    migrate()

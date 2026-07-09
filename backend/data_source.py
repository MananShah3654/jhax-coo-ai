"""
DataSource adapter for JhaPay AI COO.

The COO never reads `mock_data.py` directly anymore. It reads through a
DataSource, which today is `MockDataSource` (deterministic seeded data)
and tomorrow can be `JhaPOSDataSource` — an HTTP client that calls the
real JhaPOS / JhaPay Wallet / Loyalty Engine endpoints.

Switch sources by setting `DATA_SOURCE` in /app/backend/.env to:
  - "mock"   (default) - uses mock_data.py
  - "jhapos" - calls these env-configured URLs (set them when you have keys):
      JHAPOS_API_URL          (orders, branches, menu)
      JHAPAY_WALLET_API_URL   (payments, tips, channels)
      LOYALTY_API_URL         (customers, VIP, at-risk)
      JHAPOS_API_KEY          (Bearer token for all of the above)
  - "square" - calls Square's Connect REST API (sandbox or production):
      SQUARE_ACCESS_TOKEN     (Bearer token from the Square Developer Dashboard)
      SQUARE_ENVIRONMENT      ("sandbox" or "production")

Each *DataSource exposes the same shape:
  .branches()   -> list[branch]
  .menu()       -> list[menu_item]
  .customers()  -> list[customer]
  .orders()     -> list[order]   (last 30 days)
  .owner()      -> {"name","restaurant"}
"""
from __future__ import annotations

import hashlib
import logging
import os
import time
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from typing import Dict, List

import httpx

logger = logging.getLogger("jhapay.datasource")


# ---------- Mock ----------
class MockDataSource:
    name = "mock"

    def __init__(self) -> None:
        from mock_data import DATASET  # local seeded dataset

        self._d = DATASET

    def branches(self) -> List[Dict]: return self._d["branches"]
    def menu(self)     -> List[Dict]: return self._d["menu"]
    def customers(self)-> List[Dict]: return self._d["customers"]
    def orders(self)   -> List[Dict]: return self._d["orders"]
    def owner(self)    -> Dict:       return self._d["owner"]


# ---------- JhaPOS (live HTTP adapter — used when DATA_SOURCE=jhapos) ----------
class JhaPOSDataSource:
    """HTTP adapter. Endpoints + auth come from env. Falls back to mock data
    for any sub-resource whose env URL is missing or whose call fails — so
    you can wire ONE system at a time."""

    name = "jhapos"

    def __init__(self) -> None:
        self.pos_url    = os.environ.get("JHAPOS_API_URL", "").rstrip("/")
        self.wallet_url = os.environ.get("JHAPAY_WALLET_API_URL", "").rstrip("/")
        self.loyalty_url= os.environ.get("LOYALTY_API_URL", "").rstrip("/")
        self.key        = os.environ.get("JHAPOS_API_KEY", "")
        self._fallback = MockDataSource()
        self._cache: Dict[str, object] = {}

    def _headers(self) -> Dict[str, str]:
        return {"Authorization": f"Bearer {self.key}"} if self.key else {}

    def _get(self, base: str, path: str) -> object | None:
        if not base:
            return None
        try:
            with httpx.Client(timeout=8.0, headers=self._headers()) as c:
                r = c.get(f"{base}{path}")
                r.raise_for_status()
                return r.json()
        except Exception as exc:
            logger.warning("DataSource fallback %s%s: %s", base, path, exc)
            return None

    def branches(self) -> List[Dict]:
        if "branches" not in self._cache:
            data = self._get(self.pos_url, "/branches")
            self._cache["branches"] = data or self._fallback.branches()
        return self._cache["branches"]  # type: ignore[return-value]

    def menu(self) -> List[Dict]:
        if "menu" not in self._cache:
            data = self._get(self.pos_url, "/menu")
            self._cache["menu"] = data or self._fallback.menu()
        return self._cache["menu"]  # type: ignore[return-value]

    def orders(self) -> List[Dict]:
        if "orders" not in self._cache:
            data = self._get(self.pos_url, "/orders?days=30")
            self._cache["orders"] = data or self._fallback.orders()
        return self._cache["orders"]  # type: ignore[return-value]

    def customers(self) -> List[Dict]:
        if "customers" not in self._cache:
            data = self._get(self.loyalty_url, "/customers")
            self._cache["customers"] = data or self._fallback.customers()
        return self._cache["customers"]  # type: ignore[return-value]

    def owner(self) -> Dict:
        if "owner" not in self._cache:
            data = self._get(self.pos_url, "/owner")
            self._cache["owner"] = data or self._fallback.owner()
        return self._cache["owner"]  # type: ignore[return-value]


# ---------- Postgres (persistent store — used when DATA_SOURCE=postgres) ----------
class PostgresDataSource:
    """Reads the same shapes as MockDataSource, but from PostgreSQL.
    Seed it first with `python seed_db.py`."""

    name = "postgres"

    def branches(self) -> List[Dict]:
        from db import Branch, SessionLocal
        with SessionLocal() as s:
            return [b.to_dict() for b in s.query(Branch).all()]

    def menu(self) -> List[Dict]:
        from db import MenuItem, SessionLocal
        with SessionLocal() as s:
            return [m.to_dict() for m in s.query(MenuItem).all()]

    def customers(self) -> List[Dict]:
        from db import Customer, SessionLocal
        with SessionLocal() as s:
            return [c.to_dict() for c in s.query(Customer).all()]

    def orders(self) -> List[Dict]:
        from db import Order, SessionLocal
        with SessionLocal() as s:
            return [o.to_dict() for o in s.query(Order).all()]

    def owner(self) -> Dict:
        from db import Owner, SessionLocal
        with SessionLocal() as s:
            row = s.query(Owner).first()
            return row.to_dict() if row else MockDataSource().owner()


# ---------- Factory ----------
_SOURCE: object | None = None


def get_source():
    global _SOURCE
    if _SOURCE is None:
        which = os.environ.get("DATA_SOURCE", "mock").lower()
        if which in ("knowlwood", "live"):
            logger.info("Using Knowlwood live menu data source")
            _SOURCE = KnowlwoodDataSource()
        elif which == "jhapos":
            logger.info("Using JhaPOS live data source")
            _SOURCE = JhaPOSDataSource()
        elif which == "postgres":
            logger.info("Using PostgreSQL data source")
            _SOURCE = PostgresDataSource()
        else:
            logger.info("Using mock data source")
            _SOURCE = MockDataSource()
    return _SOURCE

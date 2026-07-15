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
import json
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
    # Abandoned online checkout sessions — powers the Cart Abandonment Rate KPI.
    # Only the mock source has this stream; live POS adapters (Square/JhaPOS)
    # don't expose it, so analytics reports the KPI as unavailable there.
    def carts(self)    -> List[Dict]: return self._d.get("carts", [])


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
    """Reads the same dict shapes as MockDataSource, but from PostgreSQL,
    scoped to a single owner (tenant). Every query filters by `owner_id` so
    one owner never sees another owner's restaurants, menu, customers, or orders.

    Data is created through the app's CRUD/onboarding endpoints — no seed."""

    name = "postgres"

    def __init__(self, owner_id: int) -> None:
        self.owner_id = owner_id

    def branches(self) -> List[Dict]:
        from database import Restaurant, SessionLocal
        with SessionLocal() as s:
            rows = (s.query(Restaurant)
                    .filter_by(owner_id=self.owner_id, is_active=True).all())
            return [r.to_dict() for r in rows]

    def menu(self) -> List[Dict]:
        from database import MenuItem, SessionLocal
        with SessionLocal() as s:
            rows = (s.query(MenuItem)
                    .filter_by(owner_id=self.owner_id, is_active=True).all())
            return [m.to_dict() for m in rows]

    def customers(self) -> List[Dict]:
        from database import Customer, SessionLocal
        with SessionLocal() as s:
            rows = s.query(Customer).filter_by(owner_id=self.owner_id).all()
            return [c.to_dict() for c in rows]

    def orders(self) -> List[Dict]:
        # Last 30 days, matching the mock/live adapters' window. Order.items
        # is selectin-loaded (see database.Order) so this is 2 queries, no N+1.
        from database import Order, SessionLocal
        cutoff = datetime.now(timezone.utc) - timedelta(days=30)
        with SessionLocal() as s:
            rows = (s.query(Order)
                    .filter(Order.owner_id == self.owner_id,
                            Order.placed_at >= cutoff)
                    .order_by(Order.placed_at).all())
            return [o.to_dict() for o in rows]

    def owner(self) -> Dict:
        from database import User, SessionLocal
        with SessionLocal() as s:
            u = s.get(User, self.owner_id)
            if u is None:
                return {"name": "Owner", "restaurant": "My Restaurant"}
            return {"name": u.name or "Owner",
                    "restaurant": u.restaurant_name or "My Restaurant"}


# ---------- Square (live POS adapter — used when DATA_SOURCE=square) ----------
# Square does not expose a food cost, so we estimate food cost by category to
# keep margin analytics meaningful. Beverages carry a lower food cost.
_FOOD_COST_PCT = 0.32
_BEVERAGE_COST_PCT = 0.22
_BEVERAGE_HINTS = ("beer", "wine", "champagne", "cocktail", "beverage", "draft")


def _estimate_cost(price: float, category: str) -> float:
    cat = (category or "").lower()
    pct = _BEVERAGE_COST_PCT if any(h in cat for h in _BEVERAGE_HINTS) else _FOOD_COST_PCT
    return round(price * pct, 2)


# The Square Connect API returns money in the smallest currency unit (cents),
# so every *_money amount is divided by 100. Bump _SQUARE_VERSION to the current
# value from the Square API changelog
# (https://developer.squareup.com/docs/build-basics/versioning) when you need
# newer fields.
_SQUARE_VERSION = "2024-10-17"


# Square exposes no dining capacity, but the Table Turnover and RevPASH KPIs need
# seats/tables per branch. We attach a static capacity to each mapped location so
# those KPIs light up on live Square. Precedence:
#   1. SQUARE_SEAT_CAPACITY env (JSON) keyed by location id OR name (case-insensitive)
#   2. _SQUARE_DEFAULT_CAPACITY (tunable via SQUARE_DEFAULT_SEATS/_TABLES)
# Example: SQUARE_SEAT_CAPACITY='{"LA8VJR69N9V6E": {"seats": 64, "tables": 16}}'
_SQUARE_DEFAULT_CAPACITY = {
    "seats": int(os.environ.get("SQUARE_DEFAULT_SEATS", "64") or 64),
    "tables": int(os.environ.get("SQUARE_DEFAULT_TABLES", "16") or 16),
}


def _load_square_capacity() -> Dict[str, Dict]:
    """Parse SQUARE_SEAT_CAPACITY (JSON) into a lowercased id/name -> capacity map."""
    raw = os.environ.get("SQUARE_SEAT_CAPACITY", "").strip()
    if not raw:
        return {}
    try:
        data = json.loads(raw)
        return {str(k).lower(): v for k, v in data.items()}
    except Exception as exc:
        logger.warning("SQUARE_SEAT_CAPACITY ignored (invalid JSON): %s", exc)
        return {}


_SQUARE_CAPACITY = _load_square_capacity()


def _square_capacity(loc_id: str | None, name: str | None) -> Dict[str, int]:
    """Seats/tables for a Square location, matched by id then name, else default."""
    cap = (
        _SQUARE_CAPACITY.get((loc_id or "").lower())
        or _SQUARE_CAPACITY.get((name or "").lower())
        or _SQUARE_DEFAULT_CAPACITY
    )
    return {"seats": int(cap.get("seats") or 0), "tables": int(cap.get("tables") or 0)}


class SquareDataSource:
    """Live adapter for Square's Connect REST API (sandbox or production).

    Auth + environment come from env. Falls back to mock data for any
    sub-resource whose call fails or returns nothing — so you can wire Square
    one resource at a time and the COO always boots. Square-shaped responses
    are mapped into the internal branch/menu/order/customer shapes so every
    downstream analytic keeps working unchanged.
    """

    name = "square"

    def __init__(self) -> None:
        self.token = os.environ.get("SQUARE_ACCESS_TOKEN", "")
        env = os.environ.get("SQUARE_ENVIRONMENT", "sandbox").lower()
        self.base = (
            "https://connect.squareupsandbox.com"
            if env == "sandbox"
            else "https://connect.squareup.com"
        )
        self._fallback = MockDataSource()
        # Per-resource cache with a TTL so live Square data refreshes instead of
        # being frozen for the process lifetime. Set SQUARE_CACHE_TTL=0 to fetch
        # on every call, or a larger value (seconds) to fetch less often.
        self.cache_ttl = float(os.environ.get("SQUARE_CACHE_TTL", "300"))
        # DEMO ONLY: Square stamps every order created_at = "now" and rejects
        # backdated orders, so seeded sandbox orders all land today. Setting
        # SQUARE_DEMO_SPREAD_DAYS>0 reassigns each order's timestamp across the
        # last N days at read-time so time-window analytics + the At-Risk
        # segment look realistic. These dates are SYNTHETIC — set it to 0 (the
        # default) for real/production data.
        self.demo_spread_days = int(os.environ.get("SQUARE_DEMO_SPREAD_DAYS", "0") or 0)
        self._cache: Dict[str, object] = {}
        self._cache_at: Dict[str, float] = {}

    def _fresh(self, key: str) -> bool:
        return (
            key in self._cache
            and (time.monotonic() - self._cache_at.get(key, 0.0)) < self.cache_ttl
        )

    def _store(self, key: str, value: object) -> object:
        self._cache[key] = value
        self._cache_at[key] = time.monotonic()
        return value

    def _headers(self) -> Dict[str, str]:
        return {
            "Authorization": f"Bearer {self.token}",
            "Square-Version": _SQUARE_VERSION,
            "Content-Type": "application/json",
        }

    def _request(self, method: str, path: str,
                 json_body: Dict | None = None) -> object | None:
        if not self.token:
            return None
        try:
            with httpx.Client(timeout=10.0, headers=self._headers()) as c:
                r = c.request(method, f"{self.base}{path}", json=json_body)
                r.raise_for_status()
                return r.json()
        except Exception as exc:
            logger.warning("Square fallback %s %s: %s", method, path, exc)
            return None

    # --- mappers (Square shape -> internal shape) ---
    @staticmethod
    def _map_location(loc: Dict) -> Dict:
        addr = loc.get("address") or {}
        loc_id = loc.get("id")
        name = loc.get("name") or "Location"
        cap = _square_capacity(loc_id, name)
        return {
            "id": loc_id,
            "name": name,
            "city": addr.get("locality") or "",
            "manager": "",
            # Static dining capacity (Square can't report it) so Table Turnover
            # and RevPASH compute on live Square. See _square_capacity.
            "seats": cap["seats"],
            "tables": cap["tables"],
        }

    @staticmethod
    def _map_item(it: Dict, cat_names: Dict[str, str] | None = None) -> Dict | None:
        cat_names = cat_names or {}
        data = it.get("item_data") or {}
        name = data.get("name") or ""
        if not name:
            return None
        # First variation with a price wins; Square prices are in cents.
        price = 0.0
        for v in data.get("variations") or []:
            money = (v.get("item_variation_data") or {}).get("price_money") or {}
            amount = money.get("amount")
            if amount:
                price = round(amount / 100.0, 2)
                break
        # Resolve the item's category id (reporting_category first, then the
        # first assigned category, then the legacy single field) to a real name
        # via the batch-retrieved lookup; falls back to "Uncategorized".
        cat_id = (
            (data.get("reporting_category") or {}).get("id")
            or next((c.get("id") for c in (data.get("categories") or []) if c.get("id")), None)
            or data.get("category_id")
        )
        category = cat_names.get(cat_id) or "Uncategorized"
        return {
            "id": it.get("id"),
            "name": name,
            "category": category,
            "price": price,
            "cost": _estimate_cost(price, category),
        }

    @staticmethod
    def _map_order(o: Dict, var_to_item: Dict[str, str] | None = None) -> Dict:
        var_to_item = var_to_item or {}

        def _money(key: str) -> float:
            return round((o.get(key) or {}).get("amount", 0) / 100.0, 2)

        items = []
        for li in o.get("line_items") or []:
            price = round(((li.get("base_price_money") or {}).get("amount", 0)) / 100.0, 2)
            # Square line items reference the ITEM_VARIATION id; the analytics
            # layer joins on the parent ITEM id (menu[].id), so remap it.
            var_id = li.get("catalog_object_id") or ""
            items.append({
                "menu_id": var_to_item.get(var_id, var_id),
                "name": li.get("name") or "",
                "qty": int(li.get("quantity") or 1),
                "price": price,
                "cost": _estimate_cost(price, ""),
            })
        total = _money("total_money")
        tax = _money("total_tax_money")
        tip = _money("total_tip_money")
        # Square exposes aggregate discounts on the order; map it so the
        # discount-overuse signal runs on real POS data (0.0 when none applied).
        discount = _money("total_discount_money")
        return {
            "id": o.get("id"),
            "branch_id": o.get("location_id"),
            "ts": o.get("created_at"),
            "channel": (o.get("source") or {}).get("name") or "Dine In",
            "customer_id": o.get("customer_id") or "",
            "items": items,
            "subtotal": round(total - tax - tip, 2),
            "discount": discount,
            "tax": tax,
            "tip": tip,
            "total": total,
            "wait_minutes": 0,
            "rating": 0,
        }

    @staticmethod
    def _map_customer(c: Dict) -> Dict:
        name = " ".join(filter(None, [c.get("given_name"), c.get("family_name")])) or "Guest"
        return {
            "id": c.get("id"),
            "name": name,
            "phone": c.get("phone_number") or "",
            "email": c.get("email_address") or "",
            "visits": 0,
            "last_visit_days_ago": 0,
            "avg_spend": 0.0,
            "lifetime_value": 0.0,
            "loyalty_points": 0,
            "favorite_branch": "",
            "tags": [],
        }

    # --- resources ---
    def branches(self) -> List[Dict]:
        if not self._fresh("branches"):
            data = self._request("GET", "/v2/locations")
            locations = data.get("locations") if isinstance(data, dict) else None
            mapped = [self._map_location(l) for l in locations] if locations else None
            self._store("branches", mapped or self._fallback.branches())
        return self._cache["branches"]  # type: ignore[return-value]

    def _catalog_items(self) -> List[Dict]:
        """Fetch the raw catalog items once per TTL; shared by menu() and the
        variation→item map so we don't hit the API twice."""
        if not self._fresh("_items"):
            data = self._request("POST", "/v2/catalog/search-catalog-items", {"limit": 100})
            self._store("_items", (data.get("items") if isinstance(data, dict) else None) or [])
        return self._cache["_items"]  # type: ignore[return-value]

    def _variation_to_item(self) -> Dict[str, str]:
        """Map each ITEM_VARIATION id to its parent ITEM id so order line items
        (which reference variations) join to menu items (keyed by item id)."""
        if not self._fresh("_var2item"):
            m: Dict[str, str] = {}
            for it in self._catalog_items():
                iid = it.get("id")
                for v in (it.get("item_data") or {}).get("variations") or []:
                    if v.get("id") and iid:
                        m[v["id"]] = iid
            self._store("_var2item", m)
        return self._cache["_var2item"]  # type: ignore[return-value]

    def menu(self) -> List[Dict]:
        if not self._fresh("menu"):
            items = self._catalog_items()
            cat_names = self._fetch_category_names(items)
            mapped = [m for m in (self._map_item(it, cat_names) for it in items) if m]
            self._store("menu", mapped or self._fallback.menu())
        return self._cache["menu"]  # type: ignore[return-value]

    def _fetch_category_names(self, items: List[Dict]) -> Dict[str, str]:
        """Resolve every category id referenced by the items to its name in one
        batch-retrieve call — Square returns only category ids on catalog items,
        never their names."""
        ids = set()
        for it in items:
            data = it.get("item_data") or {}
            rc = data.get("reporting_category") or {}
            if rc.get("id"):
                ids.add(rc["id"])
            for c in data.get("categories") or []:
                if c.get("id"):
                    ids.add(c["id"])
            if data.get("category_id"):
                ids.add(data["category_id"])
        if not ids:
            return {}
        data = self._request("POST", "/v2/catalog/batch-retrieve", {"object_ids": list(ids)})
        objs = (data.get("objects") if isinstance(data, dict) else None) or []
        return {
            o.get("id"): (o.get("category_data") or {}).get("name")
            for o in objs
            if o.get("type") == "CATEGORY" and (o.get("category_data") or {}).get("name")
        }

    def orders(self) -> List[Dict]:
        if not self._fresh("orders"):
            data = self._fetch_orders()
            if data is not None and self.demo_spread_days:
                data = self._apply_demo_spread(data)
            self._store("orders", data or self._fallback.orders())
        return self._cache["orders"]  # type: ignore[return-value]

    def _apply_demo_spread(self, orders: List[Dict]) -> List[Dict]:
        """DEMO ONLY — overwrite each order's `ts` with a synthetic date so the
        dataset spans time (Square can't backdate real orders). Deterministic
        from the order/customer ids: ~20% of customers are a 'lapsed' cohort
        whose orders land 30–75 days ago (→ At-Risk), the rest spread across the
        last SQUARE_DEMO_SPREAD_DAYS days (→ recent visits / VIP)."""
        days = self.demo_spread_days
        now = datetime.now(timezone.utc)

        def _h(s: str) -> int:
            return int(hashlib.sha1(s.encode()).hexdigest(), 16)

        for o in orders:
            cid = o.get("customer_id") or o.get("id") or ""
            oid = o.get("id") or cid
            oh = _h("ord:" + oid)
            lapsed = (_h("cust:" + cid) % 100) < 20
            days_ago = (30 + oh % 46) if lapsed else (oh % (days + 1))
            ts = (now - timedelta(days=days_ago)).replace(
                hour=7 + (oh // 60) % 15, minute=oh % 60, second=0, microsecond=0
            )
            o["ts"] = ts.isoformat()
        logger.info(
            "Square DEMO date-spreading applied to %d orders over %d days "
            "(timestamps are SYNTHETIC)", len(orders), days
        )
        return orders

    def _fetch_orders(self) -> List[Dict] | None:
        location_ids = [b.get("id") for b in self.branches() if b.get("id")]
        if not location_ids:
            return None
        # With demo date-spreading on, orders were all created "now" and are
        # re-dated at read time, so widen the created_at window to capture them
        # all; otherwise use the real last-30-days window.
        lookback = max(30, self.demo_spread_days + 5)
        start_at = (datetime.now(timezone.utc) - timedelta(days=lookback)).isoformat()
        raw: List[Dict] = []
        cursor = None
        for _ in range(20):  # safety cap: 20 pages * 500 = 10k orders
            body = {
                "location_ids": location_ids,
                "query": {
                    "filter": {"date_time_filter": {"created_at": {"start_at": start_at}}},
                    "sort": {"sort_field": "CREATED_AT", "sort_order": "DESC"},
                },
                "limit": 500,
            }
            if cursor:
                body["cursor"] = cursor
            data = self._request("POST", "/v2/orders/search", body)
            if not isinstance(data, dict):
                break
            raw.extend(data.get("orders") or [])
            cursor = data.get("cursor")
            if not cursor:
                break
        if not raw:
            return None
        var_to_item = self._variation_to_item()
        return [self._map_order(o, var_to_item) for o in raw]

    def customers(self) -> List[Dict]:
        if not self._fresh("customers"):
            data = self._request("GET", "/v2/customers")
            raw = data.get("customers") if isinstance(data, dict) else None
            mapped = [self._map_customer(c) for c in raw] if raw else None
            if mapped:
                self._enrich_customers(mapped, self.orders())
            self._store("customers", mapped or self._fallback.customers())
        return self._cache["customers"]  # type: ignore[return-value]

    @staticmethod
    def _enrich_customers(customers: List[Dict], orders: List[Dict]) -> None:
        """Derive visits / spend / loyalty / tags from each customer's real
        orders — Square's customer object carries none of these, so we aggregate
        the order history the same way the mock generator does."""
        spend: Dict[str, float] = defaultdict(float)
        visits: Dict[str, int] = defaultdict(int)
        last_ts: Dict[str, str] = {}
        branch_hits: Dict[str, Dict[str, int]] = defaultdict(lambda: defaultdict(int))
        for o in orders:
            cid = o.get("customer_id")
            if not cid:
                continue
            visits[cid] += 1
            spend[cid] += o.get("total") or 0.0
            ts = o.get("ts") or ""
            if ts > last_ts.get(cid, ""):
                last_ts[cid] = ts
            if o.get("branch_id"):
                branch_hits[cid][o["branch_id"]] += 1
        now = datetime.now(timezone.utc)
        for c in customers:
            cid = c["id"]
            v = visits.get(cid, 0)
            ltv = round(spend.get(cid, 0.0), 2)
            c["visits"] = v
            c["lifetime_value"] = ltv
            c["avg_spend"] = round(ltv / v, 2) if v else 0.0
            c["loyalty_points"] = int(ltv)
            if cid in last_ts:
                try:
                    dtv = datetime.fromisoformat(last_ts[cid].replace("Z", "+00:00"))
                    c["last_visit_days_ago"] = max(0, (now - dtv).days)
                except ValueError:
                    pass
            if branch_hits.get(cid):
                c["favorite_branch"] = max(branch_hits[cid].items(), key=lambda kv: kv[1])[0]
            c["tags"] = (
                (["vip"] if v >= 8 and c["last_visit_days_ago"] <= 14 else [])
                + (["at_risk"] if c["last_visit_days_ago"] >= 30 else [])
                + (["new"] if v == 1 else [])
            )

    def owner(self) -> Dict:
        # Square has no owner/merchant-profile equivalent in this shape.
        if not self._fresh("owner"):
            self._store("owner", self._fallback.owner())
        return self._cache["owner"]  # type: ignore[return-value]


# ---------- Factory ----------
# Non-postgres sources are single-tenant dev/fallback sources and share one
# process-wide singleton. Only the postgres source is tenant-aware: it is built
# fresh per request with the caller's owner_id and is never cached.
_SOURCE: object | None = None


def get_source(owner_id: int | None = None):
    """Return a DataSource for the current request.

    When DATA_SOURCE=postgres, `owner_id` is REQUIRED and a per-request,
    owner-scoped PostgresDataSource is returned (not cached). For every other
    source (mock/jhapos/knowlwood) the shared single-tenant singleton is
    returned and `owner_id` is ignored.
    """
    global _SOURCE
    which = os.environ.get("DATA_SOURCE", "mock").lower()

    if which == "postgres":
        if owner_id is None:
            raise ValueError("postgres data source requires an owner_id")
        return PostgresDataSource(owner_id)

    if _SOURCE is None:
        if which in ("knowlwood", "live"):
            logger.info("Using Knowlwood live menu data source")
            _SOURCE = KnowlwoodDataSource()  # noqa: F821 (optional adapter)
        elif which == "jhapos":
            logger.info("Using JhaPOS live data source")
            _SOURCE = JhaPOSDataSource()
        elif which == "postgres":
            logger.info("Using PostgreSQL data source")
            _SOURCE = PostgresDataSource()
        elif which == "square":
            logger.info("Using Square live POS data source")
            _SOURCE = SquareDataSource()
        else:
            logger.info("Using mock data source (single-tenant, dev only)")
            _SOURCE = MockDataSource()
    return _SOURCE

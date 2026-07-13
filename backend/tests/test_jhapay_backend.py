"""
JhaPay AI COO™ backend regression tests (multi-tenant).

Runs IN-PROCESS against a FastAPI TestClient, not a remote URL. Auth is
satisfied by overriding `get_current_user` with a freshly-created test owner,
and the tenant's data is seeded THROUGH the CRUD endpoints (no mock dataset).
Every test therefore exercises the owner-scoped data path.

Requires a reachable Postgres (DATABASE_URL in backend/.env) and DATA_SOURCE=postgres.

LLM-dependent tests (AI chat, campaigns, clarify gate) need a live LLM key and
are skipped unless RUN_LLM_TESTS=1 is set, since they're non-deterministic.
"""
import io
import os
import uuid
import wave
from pathlib import Path

import pytest
from dotenv import load_dotenv
from fastapi.testclient import TestClient

load_dotenv(Path(__file__).resolve().parent.parent / ".env")

import server  # noqa: E402
from auth import get_current_user  # noqa: E402
from database import (  # noqa: E402
    Customer, MenuItem, Order, OrderItem, Restaurant, SessionLocal, User,
    get_or_create_user,
)

RUN_LLM = os.environ.get("RUN_LLM_TESTS") == "1"
llm_only = pytest.mark.skipif(not RUN_LLM, reason="set RUN_LLM_TESTS=1 to run LLM tests")


class _override:
    """Context manager that temporarily sets (or clears, if fn is None) the
    get_current_user override and restores whatever was there before. Avoids
    tests clobbering each other's overrides on the shared app object."""

    def __init__(self, fn):
        self.fn = fn

    def __enter__(self):
        self.prev = server.app.dependency_overrides.get(get_current_user)
        if self.fn is None:
            server.app.dependency_overrides.pop(get_current_user, None)
        else:
            server.app.dependency_overrides[get_current_user] = self.fn
        return self

    def __exit__(self, *exc):
        if self.prev is None:
            server.app.dependency_overrides.pop(get_current_user, None)
        else:
            server.app.dependency_overrides[get_current_user] = self.prev


def _delete_owner(uid_int: int) -> None:
    with SessionLocal() as s:
        s.query(OrderItem).filter(OrderItem.order_id.in_(
            s.query(Order.id).filter_by(owner_id=uid_int)
        )).delete(synchronize_session=False)
        for model in (Order, Customer, MenuItem, Restaurant):
            s.query(model).filter_by(owner_id=uid_int).delete(synchronize_session=False)
        u = s.get(User, uid_int)
        if u:
            s.delete(u)
        s.commit()


@pytest.fixture(scope="module")
def owner():
    """Create an isolated test owner; clean up all their rows afterwards."""
    fb_uid = f"pytest-{uuid.uuid4().hex}"
    with SessionLocal() as s:
        u = get_or_create_user(
            s, firebase_uid=fb_uid, name="Test Owner",
            restaurant_name="Test Restaurant Group",
        )
        uid_int = u.id
    yield uid_int
    _delete_owner(uid_int)


@pytest.fixture(scope="module")
def client(owner):
    """TestClient whose get_current_user resolves to the test owner."""
    def _fake_user():
        with SessionLocal() as s:
            return s.get(User, owner)

    server.app.dependency_overrides[get_current_user] = _fake_user
    with TestClient(server.app) as c:
        yield c
    server.app.dependency_overrides.pop(get_current_user, None)


@pytest.fixture(scope="module")
def seeded(client):
    """Seed the owner with 2 restaurants, menu items, a customer, and orders
    (placed today so 7-day KPIs see them). Returns key ids."""
    r1 = client.post("/api/restaurants",
                     json={"name": "Alpha", "city": "SF", "manager": "Ana"}).json()
    r2 = client.post("/api/restaurants",
                     json={"name": "Beta", "city": "LA", "manager": "Ben"}).json()
    m1 = client.post(f"/api/restaurants/{r1['id']}/menu",
                     json={"name": "Burger", "category": "Mains", "price": 10.0, "cost": 3.0}).json()
    m2 = client.post(f"/api/restaurants/{r1['id']}/menu",
                     json={"name": "Fries", "category": "Sides", "price": 4.0, "cost": 1.0}).json()
    m3 = client.post(f"/api/restaurants/{r2['id']}/menu",
                     json={"name": "Salad", "category": "Mains", "price": 8.0, "cost": 2.5}).json()
    cust = client.post("/api/customers", json={"name": "Dana", "tags": ["vip"]}).json()

    # Alpha: two orders (higher revenue) so it ranks above Beta.
    client.post("/api/orders", json={
        "restaurant_id": r1["id"], "customer_id": cust["id"], "channel": "Dine In",
        "tip": 2.0, "rating": 5, "wait_minutes": 7,
        "items": [{"menu_item_id": m1["id"], "qty": 2}, {"menu_item_id": m2["id"], "qty": 1}],
    })
    client.post("/api/orders", json={
        "restaurant_id": r1["id"], "channel": "To-Go", "rating": 4, "wait_minutes": 5,
        "items": [{"menu_item_id": m1["id"], "qty": 1}],
    })
    # Beta: one smaller order.
    client.post("/api/orders", json={
        "restaurant_id": r2["id"], "channel": "Delivery", "rating": 5, "wait_minutes": 12,
        "items": [{"menu_item_id": m3["id"], "qty": 1}],
    })
    return {"r1": r1, "r2": r2, "m1": m1, "cust": cust}


# -------------- Health & Auth --------------
class TestHealthAuth:
    def test_health(self, client):
        r = client.get("/api/")
        assert r.status_code == 200
        d = r.json()
        assert d.get("ok") is True
        assert d.get("service") == "JhaPay AI COO"

    def test_business_route_requires_auth(self, owner):
        # With no override active, /dashboard must reject the request.
        with _override(None), TestClient(server.app) as anon:
            assert anon.get("/api/dashboard").status_code == 401


# -------------- CRUD write path --------------
class TestCrud:
    def test_restaurant_lifecycle(self, client):
        created = client.post("/api/restaurants", json={"name": "Temp"}).json()
        assert created["id"] and created["name"] == "Temp"
        listed = client.get("/api/restaurants").json()["restaurants"]
        assert any(x["id"] == created["id"] for x in listed)
        patched = client.patch(f"/api/restaurants/{created['id']}",
                               json={"manager": "Zoe"}).json()
        assert patched["manager"] == "Zoe"
        client.delete(f"/api/restaurants/{created['id']}")  # soft delete

    def test_order_totals_snapshot(self, client, seeded):
        # 2x Burger(10) + 1x Fries(4) = 24 subtotal, +2 tip = 26 total
        r = client.get(f"/api/orders?restaurant_id={seeded['r1']['id']}")
        assert r.status_code == 200
        orders = r.json()["orders"]
        big = max(orders, key=lambda o: o["total"])
        assert big["subtotal"] == 24.0
        assert big["total"] == 26.0

    def test_cross_tenant_guard(self, client):
        # A restaurant id that isn't ours -> 404.
        assert client.patch(f"/api/restaurants/{uuid.uuid4().hex}",
                            json={"name": "x"}).status_code == 404


# -------------- Dashboard / KPI (owner-scoped) --------------
class TestDashboard:
    def test_dashboard(self, client, seeded):
        d = client.get("/api/dashboard").json()
        for k in ["owner", "today", "health", "briefing", "branches_top3"]:
            assert k in d
        assert d["data_source"] == "postgres"
        assert 0 <= d["health"]["score"] <= 100
        assert 1 <= len(d["branches_top3"]) <= 3

    def test_branches(self, client, seeded):
        bs = client.get("/api/branches", params={"days": 7}).json()["branches"]
        assert len(bs) == 2  # exactly the two we seeded
        revs = [b["revenue"] for b in bs]
        assert revs == sorted(revs, reverse=True)
        assert bs[0]["name"] == "Alpha"  # higher revenue ranks first
        for b in bs:
            assert "growth_pct" in b

    def test_menu(self, client, seeded):
        d = client.get("/api/menu").json()
        assert d["top"] and d["all"]
        names = {m["name"] for m in d["all"]}
        assert {"Burger", "Fries", "Salad"} <= names
        for item in d["top"]:
            for k in ["revenue", "profit", "margin_pct"]:
                assert k in item

    def test_customers(self, client, seeded):
        d = client.get("/api/customers").json()
        for k in ["vip_count", "at_risk_count", "repeat_rate_pct", "top_vips", "at_risk_list"]:
            assert k in d
        assert d["vip_count"] >= 1

    def test_revenue(self, client, seeded):
        d = client.get("/api/revenue").json()
        for k in ["by_channel", "by_day", "by_hour"]:
            assert isinstance(d.get(k), list)
        assert len(d["by_channel"]) > 0

    def test_forecast(self, client, seeded):
        d = client.get("/api/forecast").json()
        assert "projected_revenue" in d
        assert isinstance(d["series"], list) and len(d["series"]) == 30

    def test_operations(self, client, seeded):
        d = client.get("/api/operations").json()
        for k in ["avg_wait_minutes", "peak_hours", "slow_hours"]:
            assert k in d


# -------------- Empty tenant must not crash --------------
class TestEmptyTenant:
    def test_fresh_owner_dashboard(self):
        fb_uid = f"pytest-empty-{uuid.uuid4().hex}"
        with SessionLocal() as s:
            u = get_or_create_user(s, firebase_uid=fb_uid, name="Fresh",
                                   restaurant_name="Nothing Yet")
            uid_int = u.id

        def _fake():
            with SessionLocal() as s:
                return s.get(User, uid_int)

        try:
            with _override(_fake), TestClient(server.app) as c:
                d = c.get("/api/dashboard")
                assert d.status_code == 200
                assert d.json()["branches_top3"] == []
                assert c.get("/api/branches").json()["branches"] == []
                assert c.get("/api/briefing").json()["top_seller"] is None
        finally:
            _delete_owner(uid_int)


# -------------- Actions / Reports (deterministic) --------------
class TestActions:
    def test_execute(self, client):
        d = client.post("/api/actions/execute",
                        json={"id": "test", "kind": "campaign", "label": "Test"}).json()
        assert d["ok"] is True and d["mocked"] is True


class TestReports:
    def test_daily_markdown(self, client, seeded):
        d = client.get("/api/reports/daily").json()
        assert d["type"] == "daily"
        assert isinstance(d["markdown"], str) and len(d["markdown"]) > 50

    def test_invalid(self, client):
        assert client.get("/api/reports/banana").status_code == 400

    @pytest.mark.parametrize("rtype", ["daily", "weekly", "monthly", "branch", "investor", "marketing"])
    def test_pdf_ok(self, client, seeded, rtype):
        r = client.get(f"/api/reports/{rtype}/pdf")
        assert r.status_code == 200, f"{rtype} -> {r.status_code}"
        assert "application/pdf" in r.headers.get("content-type", "")
        assert r.content[:4] == b"%PDF"

    def test_pdf_invalid_type(self, client):
        assert client.get("/api/reports/bogus/pdf").status_code == 400


# -------------- Voice --------------
def _make_wav_bytes() -> bytes:
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(16000)
        w.writeframes(b"\x00\x00" * 8000)
    return buf.getvalue()


class TestVoice:
    def test_transcribe_empty(self, client):
        files = {"file": ("empty.webm", b"", "audio/webm")}
        assert client.post("/api/ai/transcribe", files=files).status_code == 400


# -------------- LLM-dependent (opt-in) --------------
@llm_only
class TestAIChat:
    def test_chat_once_decision_card(self, client, seeded):
        d = client.post("/api/ai/chat_once",
                        json={"message": "How is my business today?"}).json()
        reply = d["reply"]
        for k in ["status", "reason"]:
            assert reply.get(k)

    def test_campaign_generate(self, client, seeded):
        d = client.post("/api/campaigns/generate",
                        json={"audience": "At-risk", "channel": "sms",
                              "goal": "Reactivate"}).json()
        draft = d["draft"]
        assert draft["subject"] and draft["body"] and draft["cta"]

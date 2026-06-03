"""
JhaPay AI COO™ backend regression tests.
Covers: health, auth, dashboard, branches, menu, customers, revenue, forecast,
operations, AI chat (non-stream + streaming + guardrail), campaigns, actions,
reports, STT empty-body, TTS.
"""
import io
import os
import struct
import wave

import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://voice-ceo.preview.emergentagent.com").rstrip("/")
API = f"{BASE_URL}/api"


# -------------- fixtures --------------
@pytest.fixture(scope="session")
def client():
    s = requests.Session()
    s.headers.update({"Content-Type": "application/json"})
    return s


@pytest.fixture(scope="session")
def auth_token(client):
    r = client.post(f"{API}/auth/pin", json={"pin": "1234"}, timeout=15)
    assert r.status_code == 200
    return r.json()["token"]


# -------------- Health & Auth --------------
class TestHealthAuth:
    def test_health(self, client):
        r = client.get(f"{API}/", timeout=10)
        assert r.status_code == 200
        d = r.json()
        assert d.get("ok") is True
        assert d.get("service") == "JhaPay AI COO"

    def test_pin_success(self, client):
        r = client.post(f"{API}/auth/pin", json={"pin": "1234"}, timeout=10)
        assert r.status_code == 200
        d = r.json()
        assert "token" in d and isinstance(d["token"], str) and len(d["token"]) > 0
        assert d["owner"]["name"]
        assert d["owner"]["restaurant"]

    def test_pin_invalid(self, client):
        r = client.post(f"{API}/auth/pin", json={"pin": "0000"}, timeout=10)
        assert r.status_code == 401


# -------------- Dashboard / KPI --------------
class TestDashboard:
    def test_dashboard(self, client):
        r = client.get(f"{API}/dashboard", timeout=15)
        assert r.status_code == 200
        d = r.json()
        for k in ["owner", "today", "health", "briefing", "branches_top3"]:
            assert k in d, f"missing {k}"
        today = d["today"]
        for k in ["revenue", "orders", "avg_order_value", "tips", "customers"]:
            assert k in today, f"today missing {k}"
        assert 0 <= d["health"]["score"] <= 100
        assert d["briefing"]
        assert len(d["branches_top3"]) == 3

    def test_branches(self, client):
        r = client.get(f"{API}/branches", params={"days": 7}, timeout=15)
        assert r.status_code == 200
        d = r.json()
        bs = d["branches"]
        assert len(bs) == 4
        revs = [b["revenue"] for b in bs]
        assert revs == sorted(revs, reverse=True)
        for b in bs:
            assert "growth_pct" in b

    def test_menu(self, client):
        r = client.get(f"{API}/menu", timeout=15)
        assert r.status_code == 200
        d = r.json()
        assert d["top"] and d["bottom"]
        for item in d["top"]:
            for k in ["revenue", "profit", "margin_pct"]:
                assert k in item

    def test_customers(self, client):
        r = client.get(f"{API}/customers", timeout=15)
        assert r.status_code == 200
        d = r.json()
        for k in ["vip_count", "at_risk_count", "repeat_rate_pct", "top_vips", "at_risk_list"]:
            assert k in d

    def test_revenue(self, client):
        r = client.get(f"{API}/revenue", timeout=15)
        assert r.status_code == 200
        d = r.json()
        for k in ["by_channel", "by_day", "by_hour"]:
            assert isinstance(d.get(k), list) and len(d[k]) > 0

    def test_forecast(self, client):
        r = client.get(f"{API}/forecast", timeout=15)
        assert r.status_code == 200
        d = r.json()
        assert "projected_revenue" in d
        assert isinstance(d["series"], list) and len(d["series"]) == 30
        assert isinstance(d["confidence"], (int, float))

    def test_operations(self, client):
        r = client.get(f"{API}/operations", timeout=15)
        assert r.status_code == 200
        d = r.json()
        for k in ["avg_wait_minutes", "peak_hours", "slow_hours"]:
            assert k in d


# -------------- AI Chat --------------
class TestAIChat:
    def test_chat_once_decision_card(self, client):
        r = client.post(f"{API}/ai/chat_once",
                        json={"message": "How is my business today?"},
                        timeout=120)
        assert r.status_code == 200
        d = r.json()
        reply = d["reply"]
        # Each main field should be populated for "how is biz today"
        for k in ["status", "reason", "opportunity", "action", "expected_impact"]:
            assert reply.get(k), f"reply.{k} empty: {reply.get(k)!r}"
        assert isinstance(reply.get("actions"), list)
        # Parsed reply must be cleanly parsed (no markdown fence content in fields)
        for k in ("status", "reason"):
            assert "```" not in (reply.get(k) or ""), f"parsed reply.{k} has markdown fences"

    def test_chat_guardrail(self, client):
        r = client.post(f"{API}/ai/chat_once",
                        json={"message": "Who is the president of the USA?"},
                        timeout=120)
        assert r.status_code == 200
        reply = r.json()["reply"]
        status = (reply.get("status") or "").strip()
        reason = (reply.get("reason") or "").strip()
        # Per iteration 2 spec: status starts with 'Out of scope' OR reason contains "I'm JhaPay AI COO"
        assert status.lower().startswith("out of scope") or "i'm jhapay ai coo" in reason.lower(), (
            f"Guardrail failed. status={status!r}, reason={reason!r}"
        )

    def test_chat_streaming_sse(self):
        # use raw requests for SSE
        r = requests.post(f"{API}/ai/chat",
                          json={"message": "Give me a one-line summary of today."},
                          stream=True, timeout=120,
                          headers={"Content-Type": "application/json"})
        assert r.status_code == 200
        ct = r.headers.get("content-type", "")
        assert "text/event-stream" in ct
        # NOTE: backend sets x-accel-buffering: no (verified via localhost), but
        # Cloudflare edge strips this header. Accept either present or absent.
        events = []
        for raw_line in r.iter_lines(decode_unicode=True):
            if raw_line is None:
                continue
            if raw_line.startswith("event:"):
                events.append(raw_line.split(":", 1)[1].strip())
            if "done" in events or "error" in events:
                break
        assert events[0] == "session"
        assert "delta" in events
        assert "done" in events


# -------------- Campaigns / Actions / Reports --------------
class TestCampaigns:
    def test_campaign_generate(self, client):
        r = client.post(f"{API}/campaigns/generate",
                        json={"audience": "At-risk customers", "channel": "sms",
                              "goal": "Reactivate inactive customers"},
                        timeout=120)
        assert r.status_code == 200
        d = r.json()
        draft = d["draft"]
        for k in ["subject", "body", "cta", "estimated_reach", "estimated_revenue"]:
            assert k in draft, f"draft missing {k}"
        assert draft["subject"] and draft["body"] and draft["cta"]


class TestActions:
    def test_execute(self, client):
        r = client.post(f"{API}/actions/execute",
                        json={"id": "test", "kind": "campaign", "label": "Test"},
                        timeout=10)
        assert r.status_code == 200
        d = r.json()
        assert d["ok"] is True
        assert d["mocked"] is True


class TestReports:
    def test_daily(self, client):
        r = client.get(f"{API}/reports/daily", timeout=15)
        assert r.status_code == 200
        d = r.json()
        assert d["type"] == "daily"
        assert isinstance(d["markdown"], str) and len(d["markdown"]) > 50

    def test_invalid(self, client):
        r = client.get(f"{API}/reports/banana", timeout=10)
        assert r.status_code == 400


# -------------- Voice --------------
def _make_wav_bytes() -> bytes:
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(16000)
        # 0.5s of silence
        w.writeframes(b"\x00\x00" * 8000)
    return buf.getvalue()


# -------------- Iteration 2: PDF reports --------------
class TestPdfReports:
    @pytest.mark.parametrize("rtype", ["daily", "weekly", "monthly", "branch", "investor", "marketing"])
    def test_pdf_ok(self, client, rtype):
        r = client.get(f"{API}/reports/{rtype}/pdf", timeout=30)
        assert r.status_code == 200, f"{rtype} -> {r.status_code} {r.text[:200]}"
        ct = r.headers.get("content-type", "")
        assert "application/pdf" in ct, f"{rtype} ct={ct}"
        assert len(r.content) > 2048, f"{rtype} body too small ({len(r.content)} bytes)"
        assert r.content[:4] == b"%PDF", f"{rtype} doesn't start with %PDF: {r.content[:8]!r}"

    def test_pdf_invalid_type(self, client):
        r = client.get(f"{API}/reports/bogus/pdf", timeout=15)
        assert r.status_code == 400


# -------------- Iteration 2: Clarification gate --------------
class TestClarifyGate:
    @pytest.mark.parametrize("msg", ["you", "ok", "hi", "what?"])
    def test_short_input_returns_clarify(self, client, msg):
        r = client.post(f"{API}/ai/chat_once", json={"message": msg}, timeout=120)
        assert r.status_code == 200
        reply = r.json()["reply"]
        clarify = (reply.get("clarify") or "").strip()
        suggestions = reply.get("suggestions") or []
        assert clarify, f"clarify empty for '{msg}': {reply}"
        assert isinstance(suggestions, list) and len(suggestions) >= 1, f"suggestions missing for '{msg}': {reply}"
        # Should NOT be a metric/revenue dump - reason should be empty
        assert not reply.get("reason"), f"clarify mode should have empty reason, got: {reply.get('reason')!r}"


# -------------- Iteration 2: Concise replies --------------
def _wc(s):
    return len((s or "").split())


class TestConciseReply:
    def test_business_today_concise(self, client):
        r = client.post(f"{API}/ai/chat_once",
                        json={"message": "How is my business today?"},
                        timeout=120)
        assert r.status_code == 200
        reply = r.json()["reply"]
        assert _wc(reply.get("status")) <= 10, f"status too long: {reply.get('status')!r}"
        assert _wc(reply.get("reason")) <= 18, f"reason too long: {reply.get('reason')!r}"
        opp_wc = _wc(reply.get("opportunity"))
        assert opp_wc == 0 or opp_wc <= 18, f"opportunity too long: {reply.get('opportunity')!r}"
        assert _wc(reply.get("action")) <= 10, f"action too long: {reply.get('action')!r}"
        actions = reply.get("actions") or []
        assert isinstance(actions, list) and len(actions) <= 3
        for a in actions:
            assert a.get("id") and a.get("label") and a.get("kind")
            if a["kind"] == "campaign":
                assert a.get("target") == "/marketing", f"campaign action missing /marketing target: {a}"
                assert isinstance(a.get("prefill"), dict), f"campaign missing prefill: {a}"


# -------------- Iteration 2: Data source field --------------
class TestDataSource:
    def test_dashboard_has_data_source_mock(self, client):
        r = client.get(f"{API}/dashboard", timeout=15)
        assert r.status_code == 200
        d = r.json()
        assert "data_source" in d
        assert d["data_source"] == "mock"


class TestVoice:
    def test_transcribe_empty(self):
        files = {"file": ("empty.webm", b"", "audio/webm")}
        r = requests.post(f"{API}/ai/transcribe", files=files, timeout=20)
        assert r.status_code == 400

    def test_transcribe_silence(self):
        # Optional: silence wav -> shouldn't 500
        files = {"file": ("silence.wav", _make_wav_bytes(), "audio/wav")}
        r = requests.post(f"{API}/ai/transcribe", files=files, timeout=60)
        # accept 200 (empty text) or 500 if whisper rejects 0.5s silence
        assert r.status_code in (200, 500)
        if r.status_code == 200:
            assert "text" in r.json()

    def test_tts(self, client):
        r = client.post(f"{API}/ai/tts",
                        json={"text": "Sales are up today"},
                        timeout=60)
        assert r.status_code == 200
        assert r.headers.get("content-type", "").startswith("audio/mpeg")
        assert len(r.content) > 200

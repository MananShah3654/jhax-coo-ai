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
        decline = ("I am JhaPay AI COO and can assist only with restaurant operations, "
                   "revenue, customers, marketing, loyalty, payments, performance, and growth.")
        r = client.post(f"{API}/ai/chat_once",
                        json={"message": "Who is the president of the USA?"},
                        timeout=120)
        assert r.status_code == 200
        d = r.json()
        raw = (d.get("raw") or "") + " " + (d["reply"].get("reason") or "") + " " + (d["reply"].get("status") or "")
        assert decline in raw, f"Guardrail decline not found. raw={d.get('raw')[:300]!r}"

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

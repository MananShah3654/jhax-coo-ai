# JHAX

**The AI Operating System for Restaurant Owners.**
Ask your restaurant anything. Get one decisive answer. Execute one action. In under 30 seconds.

> _"One Question. One Answer. One Action."_

JHAX is not a chatbot and not a dashboard. It's a digital Chief Operating Officer that understands restaurant data, analyzes performance, recommends actions, executes business workflows, and shares branded PDF reports — all from a single voice or text prompt.

---

## ✨ What it does

| | |
|---|---|
| 🎙️ **Voice-first** | Tap the mic, speak the question. Whisper transcribes, the COO answers, OpenAI TTS reads it back. |
| 🧠 **AI Decision Cards** | Claude Sonnet 4.5 returns structured replies — `Status` + 1-line `Reason · Opportunity` + impact pill + 1–3 one-click action chips. No more 5-section walls of text. |
| 🚦 **Restaurant Health Score** | Apple-Watch-style ring out of 100, composed from revenue growth, repeat customers, reviews, wait times, tips, staff efficiency. |
| 📅 **Daily CEO Briefing** | Every morning: yesterday's numbers, growth %, top seller, best/worst branch, risk areas, recommended action, expected $ opportunity. |
| 🎯 **Real action wiring** | Action buttons go to real screens: `Create Combo → Promotions builder (prefilled)`, `Launch Campaign → Marketing AI (prefilled)`, `Share Report → Share Modal (PDF + WhatsApp + Email)`, `Notify Manager → Manager Mode (prefilled)`. |
| 🧾 **Branded PDF reports** | Daily, Weekly, Monthly, Branch, Investor, Marketing — generated server-side with reportlab. Share via WhatsApp, Email, or download. |
| 💬 **Persistent chat history** | ChatGPT-style left sidebar — every conversation is saved in `localStorage` with per-session and bulk delete. |
| 🏢 **Multi-location** | Branch ranking, best vs. needs-attention callouts, branch-level KPIs. |
| 🧮 **Intelligence modules** | Customer (VIP / at-risk / LTV), Menu (top profitable / underperformers), Revenue (channels, days, hours), Forecast (30-day projection with confidence). |
| 🛡️ **Domain guardrails** | Hard refuses non-restaurant questions. Asks for clarification on vague inputs instead of dumping irrelevant metrics. |

---

## 🏗️ Architecture (MCP-style)

```
Frontend (React)
    │
    ▼
AI Gateway  /api/ai/chat  (SSE streaming)
    │
    ▼
analytics.py  ── computes restaurant_context (KPIs, branches, menu, customers, forecast)
    │
    ▼
Prompt Builder  (system prompt + JSON-only Decision Card schema + restaurant_context)
    │
    ▼
Claude Sonnet 4.5  (via emergentintegrations)
    │
    ▼
Response Formatter  (parse JSON, strip fences, partial-stream extraction)
    │
    ▼
Frontend renders <DecisionCard /> with one-click action chips
```

**Critical:** the LLM **never** touches the database. It only sees a pre-computed, structured `restaurant_context` snapshot. Actions are executed by backend handlers, not the LLM.

---

## 📁 Repository layout

```
/app
├── backend/
│   ├── server.py            # FastAPI app + all /api/* routes
│   ├── ai_service.py        # Claude prompt, streaming, STT, TTS, parsing
│   ├── analytics.py         # KPI / branch / menu / customer / forecast / health
│   ├── data_source.py       # MockDataSource + JhaPOSDataSource (HTTP adapter)
│   ├── mock_data.py         # Deterministic seeded fixtures (seed=42)
│   ├── pdf_report.py        # Branded reportlab PDF generator
│   ├── requirements.txt
│   └── .env                 # MONGO_URL, EMERGENT_LLM_KEY, OWNER_PIN, DATA_SOURCE
│
├── frontend/
│   ├── package.json
│   └── src/
│       ├── App.js                       # Router + ShareModal mount
│       ├── components/
│       │   ├── DecisionCard.jsx         # Compact AI reply card + action routing
│       │   ├── ShareModal.jsx           # PDF preview + WhatsApp/Email/Download
│       │   ├── VoiceMic.jsx             # MediaRecorder → /ai/transcribe
│       │   ├── HealthRing.jsx           # SVG Apple-Watch-style ring
│       │   ├── KpiTile.jsx
│       │   ├── Layout.jsx               # Sidebar + bottom nav
│       │   └── Logo.jsx
│       ├── hooks/
│       │   ├── useCooChat.js            # SSE parser + partial JSON extract
│       │   └── useChatHistory.js        # localStorage-backed chat sessions
│       ├── screens/
│       │   ├── Login.jsx                # PIN keypad
│       │   ├── Home.jsx                 # KPIs, health, briefing, Ask Anything, mic
│       │   ├── Chat.jsx                 # Streaming chat + history sidebar
│       │   ├── Branches.jsx
│       │   ├── Customers.jsx
│       │   ├── Menu.jsx
│       │   ├── Marketing.jsx            # Campaign generator (prefill-aware)
│       │   ├── Promotions.jsx           # Combo builder (prefill-aware)
│       │   ├── Forecast.jsx
│       │   └── Manager.jsx              # Branch task plan (notify prefill-aware)
│       ├── contexts/AuthContext.jsx
│       ├── constants/testIds.js
│       ├── lib/api.js
│       ├── App.css
│       └── index.css                    # Brand tokens, mic-glow, fade-up, caret
│
└── memory/
    ├── PRD.md
    └── test_credentials.md
```

---

## 🚀 Getting started

### Prerequisites

- Python 3.11+
- Node 18+ / Yarn 1.22+
- MongoDB (not yet used by features but required by the platform)
- An **Emergent Universal Key** (`EMERGENT_LLM_KEY`) — already configured in `/app/backend/.env` for the demo build.

### 1. Backend

```bash
cd backend
pip install -r requirements.txt
# .env must contain:
#   MONGO_URL=mongodb://localhost:27017
#   DB_NAME=test_database
#   CORS_ORIGINS=*
#   EMERGENT_LLM_KEY=sk-emergent-...
#   OWNER_PIN=1234
#   OWNER_NAME=Manan
#   DATA_SOURCE=mock     # or "jhapos" to use the live adapter
uvicorn server:app --host 0.0.0.0 --port 8001 --reload
```

### 2. Frontend

```bash
cd frontend
yarn install
# .env must contain:
#   REACT_APP_BACKEND_URL=https://<your-backend>
yarn start
```

### 3. Sign in

Open the app → enter PIN **`1234`** → land on the AI COO Home.

---

## 🔌 Plugging in real JhaPOS data

The backend ships with two data sources (`backend/data_source.py`). Switch with one env var.

```bash
# /app/backend/.env
DATA_SOURCE=jhapos
JHAPOS_API_URL=https://api.jhapos.example.com
JHAPAY_WALLET_API_URL=https://wallet.jhapay.example.com
LOYALTY_API_URL=https://loyalty.jhapay.example.com
JHAPOS_API_KEY=eyJhbGciOi...
```

`JhaPOSDataSource` falls back to mock data **per resource** if any URL is missing or a call fails — so you can wire one system at a time without breaking the COO.

Each adapter exposes the same five methods:

| Method | Endpoint expected |
|---|---|
| `.branches()` | `GET {JHAPOS_API_URL}/branches` |
| `.menu()` | `GET {JHAPOS_API_URL}/menu` |
| `.orders()` | `GET {JHAPOS_API_URL}/orders?days=30` |
| `.customers()` | `GET {LOYALTY_API_URL}/customers` |
| `.owner()` | `GET {JHAPOS_API_URL}/owner` |

All calls send `Authorization: Bearer {JHAPOS_API_KEY}`.

`GET /api/dashboard` returns a `data_source` field so the UI can show which source is live.

---

## 🟩 Plugging in Square sandbox data

`SquareDataSource` (`backend/data_source.py`) calls Square's [Connect REST API](https://developer.squareup.com/reference/square) and maps the responses into the same internal shape the COO expects. Switch to it with one env var.

```bash
# /app/backend/.env
DATA_SOURCE=square
SQUARE_ACCESS_TOKEN=EAAAl...        # Square Developer Dashboard → Credentials → Sandbox
SQUARE_ENVIRONMENT=sandbox          # "sandbox" or "production"
```

Get the access token from the **Square Developer Dashboard → your app → Credentials → Sandbox** tab. `SQUARE_ENVIRONMENT` selects the base URL:

- `sandbox` → `https://connect.squareupsandbox.com`
- `production` → `https://connect.squareup.com`

Like `JhaPOSDataSource`, it falls back to mock data **per resource** if the token is missing or a call fails, so the COO always boots.

| Method | Square endpoint |
|---|---|
| `.branches()` | `GET /v2/locations` |
| `.menu()` | `POST /v2/catalog/search-catalog-items` |
| `.orders()` | `POST /v2/orders/search` (last 30 days, across `location_ids` from `.branches()`) |
| `.customers()` | `GET /v2/customers` |
| `.owner()` | _no Square equivalent — returns mock fallback_ |

All calls send `Authorization: Bearer {SQUARE_ACCESS_TOKEN}`, `Square-Version: <date>`, and (for POST) `Content-Type: application/json`. Money amounts come back in cents and are converted to dollars; food cost isn't provided by Square, so it's estimated by category (same as the Knowlwood adapter).

---

## 🌐 API reference (high-level)

| Method | Path | What it returns |
|---|---|---|
| `POST` | `/api/auth/pin` | `{token, owner}` — PIN login |
| `GET`  | `/api/dashboard` | Today KPIs + health + briefing + top 3 branches + `data_source` |
| `GET`  | `/api/briefing` | Daily CEO briefing |
| `GET`  | `/api/branches?days=7` | Ranked branches with growth |
| `GET`  | `/api/menu?days=30` | Top + bottom items with margin |
| `GET`  | `/api/customers` | VIP, at-risk, repeat rate, LTV |
| `GET`  | `/api/revenue?days=30` | By channel / day / hour |
| `GET`  | `/api/forecast?days=30` | 30-day projection + confidence |
| `GET`  | `/api/operations` | Peak / slow hours, wait times |
| `POST` | `/api/ai/chat` | SSE stream — `event: session / delta / done` |
| `POST` | `/api/ai/chat_once` | Non-streaming JSON for tests |
| `POST` | `/api/ai/transcribe` | Multipart audio → `{text}` (Whisper) |
| `POST` | `/api/ai/tts` | `{text,voice}` → `audio/mpeg` |
| `POST` | `/api/campaigns/generate` | Claude-drafted subject/body/cta |
| `POST` | `/api/actions/execute` | Mocked SMS/Email/Push (returns `mocked:true`) |
| `GET`  | `/api/reports/{type}` | Markdown report |
| `GET`  | `/api/reports/{type}/pdf` | Branded PDF (reportlab) |

`{type}` ∈ `daily | weekly | monthly | branch | investor | marketing`.

---

## 🎤 Voice flow

```
[Mic button]
  ↓ MediaRecorder (webm/opus)
[POST /api/ai/transcribe]
  ↓ Whisper-1
[transcribed text]
  ↓ auto-submitted to chat
[SSE stream of Decision Card JSON]
  ↓ progressive render
[Speaker button on reply]
  ↓ POST /api/ai/tts
[mp3 played back to owner]
```

---

## 🧩 Action button → screen mapping

The Decision Card returns action chips with a `kind`. Each kind maps to a real, prefilled screen:

| `kind` | Where it lands | Prefill payload |
|---|---|---|
| `campaign` | `/marketing` | `{audience, channel, goal}` |
| `promotion` | `/promotions` | `{name, items[], discount, audience}` — opens the Combo Builder |
| `notify` | `/manager` | `{branch, message}` — auto-generates a task plan |
| `share` / `report` | global Share Modal | `target` ∈ daily/weekly/monthly/... |
| `navigate` | React Router push | `target` is a route path |

No action button is a dead-end. Every chip leads somewhere meaningful and pre-filled.

---

## 🧪 Testing

```bash
# Backend
cd backend
pytest tests/ -v

# Frontend lint
cd frontend
yarn lint
```

The backend ships with **33 pytest cases** covering: auth, dashboard, all intelligence endpoints, SSE streaming, Whisper, TTS, campaign generation, action execute, all 6 PDF report types, the clarification gate (`"you" / "ok" / "hi"` → no metric dump), the domain guardrail (non-restaurant → polite decline), and the data source adapter.

---

## 🎨 Design language

- **Brand colors**: `#FF6B35` primary, `#1E293B` slate, `#22C55E` success, `#F59E0B` warning, `#EF4444` danger.
- **Type**: Outfit (display) + Manrope (body) + JetBrains Mono (numbers).
- **Inspiration**: Stripe, Toast, Linear, Notion AI — executive, premium, minimal, fast.
- **Anti-patterns avoided**: complex enterprise dashboards, info overload, AI-slop purple gradients, generic card grids.

---

## 🛣️ Roadmap

- [ ] Wire real JhaPOS / Wallet / Loyalty endpoints (adapter ready)
- [ ] Wake phrase ("Hey JhaPay") + always-on voice
- [ ] Server-side bearer-token middleware on `/api/*`
- [ ] PPT export (in addition to PDF)
- [ ] Cron-driven WhatsApp morning briefing to owner + managers
- [ ] Multi-owner / franchise / regional roles
- [ ] "What-if" simulator before executing an action
- [ ] Inventory + staff scheduling intelligence

---

## 📜 License

Proprietary — © JhaPay. All rights reserved.

---

<sub>JHAX™. Understand. Analyze. Recommend. Execute. Share.</sub>

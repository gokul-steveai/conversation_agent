# 🚀 AI Chat Assistant

An enterprise-grade **AI Chat Application** built with **FastAPI REST Backend**, **Groq LLM (`llama-3.3-70b-versatile`)**, **SQLAlchemy Async ORM (PostgreSQL & SQLite)**, **Tavily Real-Time Web Search**, and a **Streamlit Glassmorphism UI Client**.

---

## 🌟 Key Features

- **Open Conversational AI** — Ask any question from message #1: coding, live web search, weather, local facts, creative writing, or general Q&A.
- **Real-Time Token Streaming** — Typewriter-style token streaming via Server-Sent Events (SSE) and `st.write_stream(...)`.
- **FastAPI REST Backend** — Decoupled backend handling JWT Authentication (`/api/v1/auth`), Sessions (`/api/v1/sessions`), and Streaming Chat (`/api/v1/chat`).
- **Autonomous Web Search** — On-demand Tavily web search fetching live facts, news, and real-time information.
- **Context-Aware Clarification** — Detects missing parameters (e.g., location for weather) and asks clarification questions before acting.
- **Location Intelligence** — Separates query target locations from user profile locations to prevent search queries from overwriting stored user data.
- **Database Connection Resilience** — `pool_pre_ping` and `pool_recycle` for PostgreSQL; graceful engine teardown on shutdown.
- **Security Hardening** — JWT-enforced routes, HTML-escaped tool output, explicit CORS allowlist, no raw exception leakage.

---

## 📁 Project Structure

```
conversation_agent/
├── backend/                    # FastAPI REST Backend
│   ├── main.py                 # Application entrypoint
│   ├── agents/                 # Agent logic
│   ├── api/                    # Versioned REST endpoints (auth, sessions, chat)
│   │   ├── deps.py             # Dependency injection (JWT auth, DB sessions)
│   │   └── v1/                 # API v1 route handlers
│   ├── config/                 # Settings & constants
│   ├── controllers/            # Chat orchestration
│   ├── core/                   # Database engine & LLM factory
│   ├── models/                 # SQLAlchemy ORM models
│   ├── prompts/                # System & evaluation prompts
│   ├── repositories/           # Data access layer
│   ├── schemas/                # Pydantic request/response schemas
│   ├── services/               # Domain business logic
│   ├── tools/                  # Tavily search tools
│   └── utils/                  # Logging, sanitization, helpers
│
├── frontend/                   # Streamlit UI Client
│   ├── app.py                  # Streamlit entrypoint
│   └── ui/                     # UI components & API client
│       ├── api_client.py       # HTTP client with connection pooling
│       ├── auth_ui.py          # JWT authentication forms
│       ├── components.py       # Glassmorphism UI components
│       └── session.py          # Session manager
│
├── pyproject.toml              # Dependencies & Ruff config
├── .env.example                # Environment template
└── README.md
```

---

## 🚀 Getting Started

### Prerequisites

- Python 3.13+
- [uv](https://docs.astral.sh/uv/) package manager

### Installation

```bash
git clone https://github.com/gokul-steveai/conversation_agent.git
cd conversation_agent
uv sync
cp .env.example .env
# Edit .env with your API keys
```

### Running

**Terminal 1 — Backend:**
```bash
cd backend
uvicorn main:app --reload --port 8000
```

**Terminal 2 — Frontend:**
```bash
uv run streamlit run frontend/app.py
```

| Service  | URL                                                    |
|----------|--------------------------------------------------------|
| Backend  | [http://localhost:8000](http://localhost:8000)          |
| Swagger  | [http://localhost:8000/docs](http://localhost:8000/docs)|
| Frontend | [http://localhost:8501](http://localhost:8501)          |

---

## ⚙️ Environment Variables

```env
GROQ_API_KEY=gsk_your_groq_api_key
GROQ_MODEL=llama-3.3-70b-versatile
TAVILY_API_KEY=tvly-your_tavily_api_key
DATABASE_URL=sqlite:///data/conversations.db
JWT_SECRET_KEY=your-secret-key
BASE_API_URL=http://localhost:8000/api/v1
```

---

## 🧪 Code Quality

```bash
uv run ruff check --fix .
uv run ruff format .
```

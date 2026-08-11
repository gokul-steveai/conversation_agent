# 🚀 Autonomous Multi-Agent Onboarding Assistant

An enterprise-grade, distributed multi-agent onboarding platform built with **LangGraph**, **Groq LLM (`llama-3.3-70b-versatile`)**, **SQLAlchemy ORM (PostgreSQL & SQLite)**, **Tavily Live Web Search**, and a **Streamlit Glassmorphism UI**.

---

## 🌟 Key Features

- **Supervisor Router Orchestration**: LangGraph state graph with dynamic supervisor routing between specialized onboarding agents.
- **Autonomous Agentic Web Search**: On-demand Tavily web search integration fetching real-time facts, news updates, and location highlights.
- **Enterprise Multi-Session Memory (PostgreSQL & SQLite)**: Persistent session state storage built with SQLAlchemy ORM, supporting **PostgreSQL as Primary Storage** with automatic **SQLite Fallback** (`data/conversations.db`).
- **Strict Session Isolation & Resumption**: Each session maintains isolated profile states, UI chat history, and LangChain message memory—allowing users to resume conversations seamlessly right where they left off.
- **SOLID & DRY Architecture**: Decoupled repository pattern (`repositories/`), domain service layer (`services/`), ORM entities (`models/`), orchestration controllers (`controllers/`), and presentation layer (`ui/`).
- **Streamlit Glassmorphism UI**: Interactive sidebar session switcher, new session creation, quick suggestions, onboarding progress bar, and real-time tool execution logs.

---

## 🏗️ System Architecture

![System Architecture Map](onboarding.png)

```mermaid
flowchart TD
    User["User Input"] --> App["Streamlit Web App (app.py)"]
    App --> UI["Presentation & Session Adapter (ui/)"]
    App --> Controller["Orchestration Controller (controllers/onboarding_controller.py)"]
    
    Controller --> StateRefiner["State Extractor (StateUpdate)"]
    StateRefiner --> SessionSvc["Session Service (services/session_service.py)"]
    
    SessionSvc --> SessionRepo["Session Repository (repositories/session_repository.py)"]
    SessionRepo --> Database[("PostgreSQL Primary / SQLite Fallback")]
    
    Controller --> Graph["LangGraph Orchestrator (graph/workflow.py)"]
    Graph --> Supervisor["Supervisor Router Agent (agents/supervisor.py)"]
    
    Supervisor --> AgentPI["Personal Info Agent"]
    Supervisor --> AgentTP["Topic Preferences Agent"]
    Supervisor --> AgentCE["Customer Engagement Agent"]
    
    AgentCE --> SearchTool["Tavily Web Search Tool (tools/tavily_search.py)"]
    AgentCE --> ProfileService["Profile Persistence Service (services/profile_service.py)"]
```

---

## 📁 Distributed Project Directory Structure

```text
conversation_agent/
├── app.py                      # Streamlit UI composition root
├── main.py                     # CLI terminal application entrypoint
├── pyproject.toml              # UV dependency definition & Ruff linter settings
├── .env.example                # Public environment configuration template
├── config/                     # Centralized settings & prompt constants
│   ├── settings.py             # Environment settings loader
│   └── constants.py            # Prompt templates & node constants
├── core/                       # LLM Provider Factory
│   └── llm_factory.py          # Groq Chat model instance
├── models/                     # Domain Schemas & Database ORM Models
│   ├── db_models.py            # SQLAlchemy SessionModel ORM entity
│   ├── schemas.py              # Pydantic structured output models
│   └── state.py                # LangGraph OnboardingState definition
├── repositories/               # Enterprise Repository Data Access Layer
│   ├── base_repository.py      # IBaseRepository abstract contract (SOLID)
│   └── session_repository.py   # SQLAlchemy session database CRUD implementation
├── services/                   # Business Logic Services
│   ├── session_service.py      # Session lifecycle & domain logic
│   ├── memory_service.py       # Memory facade wrapper
│   ├── search_service.py       # Tavily Web Search API client
│   └── profile_service.py      # Profile persistence service
├── agents/                     # Specialized LangGraph Agent Nodes
│   ├── supervisor.py           # Routing supervisor
│   ├── personal_information.py # Personal details agent
│   ├── topic_preferences.py    # Topic preference agent
│   └── customer_engagement.py # Final engagement agent
├── graph/                      # LangGraph Workflow & Router
│   ├── workflow.py             # StateGraph definition
│   └── router.py               # Supervisor conditional router
├── tools/                      # Agent Tooling
│   └── tavily_search.py        # search_web_information @tool definition
├── ui/                         # Streamlit UI & Session Manager
│   ├── components.py           # Glassmorphism UI components & controls
│   └── session.py              # UI Session state adapter
└── utils/                      # Utilities
    ├── logger.py               # Centralized logger
    ├── console.py              # CLI Console UI formatter
    └── sanitizer.py            # Response regex sanitizer
```

---

## ⚙️ Environment Setup & Configuration

### 1. Requirements & Prerequisites
- Python `3.13+`
- [`uv`](https://github.com/astral-sh/uv) package manager

### 2. Environment Variables Setup
Copy `.env.example` to `.env`:
```bash
cp .env.example .env
```

Edit `.env` with your API keys:
```env
# Groq LLM Configuration
GROQ_API_KEY=gsk_your_groq_api_key_here
GROQ_MODEL=llama-3.3-70b-versatile

# Tavily Web Search API
TAVILY_API_KEY=tvly-your_tavily_api_key_here

# Database URL (PostgreSQL Primary with automatic SQLite Fallback)
DATABASE_URL=sqlite:///data/conversations.db
# For PostgreSQL: postgresql://username:password@localhost:5432/conversation_agent
```

---

## 🚀 Running the Application

### Launch Streamlit Web Interface
```bash
uv run streamlit run app.py
```
👉 Open your browser at **[http://localhost:8501](http://localhost:8501)**

### Launch CLI Terminal Interface
```bash
uv run main.py
```

### Code Formatting & Quality Auditing (Ruff)
```bash
uv run ruff check . --fix
uv run ruff format .
```

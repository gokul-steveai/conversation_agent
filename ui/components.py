import asyncio
import os

import streamlit as st

from config.constants import NODE_ENGAGEMENT, NODE_PERSONAL_INFO, NODE_TOPIC_PREF
from config.settings import settings
from services.session_service import SessionService
from ui.session import SessionManager


class UIComponents:
    @staticmethod
    def render_custom_styles():
        st.markdown(
            """
        <style>
            @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');
            
            html, body, [class*="css"] {
                font-family: 'Inter', system-ui, -apple-system, sans-serif;
            }

            .stApp {
                background: radial-gradient(circle at 50% 0%, #1e1b4b 0%, #090D16 70%);
                color: #F8FAFC;
            }

            .header-container {
                background: rgba(19, 27, 46, 0.6);
                backdrop-filter: blur(16px);
                border: 1px solid rgba(255, 255, 255, 0.08);
                border-radius: 16px;
                padding: 20px 24px;
                margin-bottom: 24px;
                box-shadow: 0 8px 32px 0 rgba(0, 0, 0, 0.37);
            }

            [data-testid="stSidebar"] {
                background: rgba(15, 23, 42, 0.8) !important;
                backdrop-filter: blur(12px);
                border-right: 1px solid rgba(255, 255, 255, 0.08);
            }

            .tool-card {
                background: rgba(49, 46, 129, 0.4);
                border-left: 4px solid #818cf8;
                border-radius: 8px;
                padding: 10px 16px;
                margin: 10px 0;
                font-family: monospace;
                font-size: 0.88rem;
                color: #e0e7ff;
            }

            .agent-badge {
                background: linear-gradient(135deg, #4f46e5 0%, #7c3aed 100%);
                color: #ffffff;
                padding: 6px 14px;
                border-radius: 20px;
                font-weight: 600;
                font-size: 0.85rem;
                display: inline-block;
                box-shadow: 0 0 12px rgba(99, 102, 241, 0.5);
            }

            .topic-pill {
                background: rgba(99, 102, 241, 0.15);
                border: 1px solid rgba(99, 102, 241, 0.3);
                color: #a5b4fc;
                padding: 4px 12px;
                border-radius: 14px;
                font-size: 0.82rem;
                display: inline-block;
                margin: 2px 4px 2px 0;
            }

            .stButton > button {
                background: rgba(30, 41, 59, 0.6) !important;
                border: 1px solid rgba(255, 255, 255, 0.1) !important;
                color: #c7d2fe !important;
                border-radius: 20px !important;
                font-size: 0.85rem !important;
                transition: all 0.2s ease !important;
            }
            .stButton > button:hover {
                background: rgba(99, 102, 241, 0.25) !important;
                border-color: #818cf8 !important;
                color: #ffffff !important;
                transform: translateY(-1px);
            }
        </style>
        """,
            unsafe_allow_html=True,
        )

    @staticmethod
    def render_header():
        st.markdown(
            """
        <div class="header-container">
            <h2 style="margin:0; font-size: 1.6rem; color:#f8fafc;">🚀 Autonomous Multi-Agent Onboarding</h2>
            <p style="margin: 4px 0 0 0; color:#94a3b8; font-size:0.92rem;">
                Powered by LangGraph Supervisor Routing, Groq LLM & Real-Time Tavily Web Search
            </p>
        </div>
        """,
            unsafe_allow_html=True,
        )

    @staticmethod
    def render_sidebar():
        with st.sidebar:
            st.title("⚡ Multi-Agent Control")

            st.markdown("### 📜 Session History")
            col_new, col_del = st.columns([3, 1])
            if col_new.button("➕ New Session", width="stretch"):
                SessionManager.create_new_session()
                st.rerun()

            if col_del.button("🗑️", help="Delete active session"):
                SessionManager.delete_current_session()
                st.rerun()

            sessions = asyncio.run(SessionService.list_sessions())
            if sessions:
                session_options = {
                    s["session_id"]: f"📌 {s['title']} ({s['updated_at'][11:16]})"
                    for s in sessions
                }
                current_id = st.session_state.get("current_session_id")
                option_ids = list(session_options.keys())
                curr_idx = (
                    option_ids.index(current_id) if current_id in option_ids else 0
                )

                selected_id = st.selectbox(
                    "Select Conversation Session:",
                    options=option_ids,
                    format_func=lambda sid: session_options[sid],
                    index=curr_idx,
                    key="session_select_box",
                )

                if selected_id and selected_id != current_id:
                    SessionManager.switch_session(selected_id)
                    st.rerun()

            st.markdown("---")

            agent_display = (
                st.session_state.state["current_agent"].replace("_", " ").title()
            )
            st.markdown(
                f"Active Agent: <span class='agent-badge'>🤖 {agent_display}</span>",
                unsafe_allow_html=True,
            )

            progress_val = SessionManager.get_progress()
            st.markdown("### 📊 Onboarding Progress")
            st.progress(progress_val / 100.0)
            st.caption(f"Completion: **{progress_val}%**")

            st.markdown("---")
            st.subheader("📋 Collected Profile Data")

            s = st.session_state.state
            st.markdown(f"👤 **Name:** `{s['name'] or 'Waiting...'}`")
            st.markdown(f"📍 **Location:** `{s['location'] or 'Waiting...'}`")

            if s["topic_preferences"]:
                st.markdown("🏷️ **Topics:**")
                pills_html = "".join(
                    [
                        f"<span class='topic-pill'>{t}</span>"
                        for t in s["topic_preferences"]
                    ]
                )
                st.markdown(pills_html, unsafe_allow_html=True)
            else:
                st.markdown("🏷️ **Topics:** `Waiting...` ")

            st.markdown("---")

            st.subheader("⚙️ System Status")
            st.caption(f"LLM Provider: **Groq ({settings.groq_model})**")
            st.caption(
                f"Search API: **Tavily ({'Connected' if settings.tavily_api_key else 'Fallback Mode'})**"
            )

            if st.button("🔄 Reset Current Session", width="stretch"):
                SessionManager.create_new_session()
                st.rerun()

            if os.path.exists("onboarding.png"):
                st.markdown("---")
                with st.expander("🔍 Architecture Graph Map"):
                    st.image("onboarding.png", width="stretch")

    @staticmethod
    def render_quick_actions() -> str | None:
        st.markdown("##### 💡 Suggested Responses:")
        cols = st.columns(3)
        current_agent = st.session_state.state["current_agent"]

        if current_agent == NODE_PERSONAL_INFO:
            if cols[0].button("📍 Why do you need my location?"):
                return "Why do you need my location?"
            if cols[1].button("👋 I am Ayush from Bangalore"):
                return "I am Ayush from Bangalore"
            if cols[2].button("👤 Hi, I am Gokul from Dhar"):
                return "Hi, I am Gokul from Dhar"
        elif current_agent == NODE_TOPIC_PREF:
            if cols[0].button("💡 What topic options do I have?"):
                return "What topic options do I have?"
            if cols[1].button("🚀 AI, Tech, and Space Science"):
                return "I am interested in AI, Technology, and Space Science"
            if cols[2].button("⚽ Sports, Travel, and Finance"):
                return "I love Sports, Travelling, and Finance"
        elif current_agent == NODE_ENGAGEMENT:
            if cols[0].button("✨ Tell me more about local tech facts!"):
                return "Tell me more about local tech facts!"
            if cols[1].button("📰 Any latest news in AI today?"):
                return "Any latest news in AI today?"
            if cols[2].button("✅ All good, thanks!"):
                return "All good, thanks!"
        return None

    @staticmethod
    def render_chat_messages():
        for msg in st.session_state.messages:
            if msg["role"] == "assistant":
                with st.chat_message("assistant", avatar="🤖"):
                    st.markdown(msg["content"])
            elif msg["role"] == "user":
                with st.chat_message("user", avatar="👤"):
                    st.markdown(msg["content"])
            elif msg["role"] == "tool":
                st.markdown(
                    f"<div class='tool-card'>{msg['content']}</div>",
                    unsafe_allow_html=True,
                )

import streamlit as st

from config.constants import APP_SUBTITLE, APP_TITLE
from ui.api_client import APIClient
from ui.session import SessionManager


class UIComponents:
    @staticmethod
    def render_custom_styles():
        """Renders CSS styles for glassmorphism layout, badges, buttons, and dark typography."""
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
            f"""
        <div class="header-container">
            <h2 style="margin:0; font-size: 1.6rem; color:#f8fafc;">🚀 {APP_TITLE}</h2>
            <p style="margin: 4px 0 0 0; color:#94a3b8; font-size:0.92rem;">
                {APP_SUBTITLE}
            </p>
        </div>
        """,
            unsafe_allow_html=True,
        )

    @staticmethod
    def _render_sidebar_account():
        user_name = st.session_state.get("user_name", "User")
        user_email = st.session_state.get("user_email", "")
        st.markdown(f"👤 **Account:** `{user_name}`  \n📧 `{user_email}`")

        from ui.auth_ui import AuthUI

        if st.button("🚪 Sign Out", use_container_width=True):
            AuthUI.logout()

    @staticmethod
    def _render_sidebar_session_history():
        """Renders active session selector and controls."""
        st.markdown("### 📜 Session History")
        col_new, col_del = st.columns([3, 1])

        if col_new.button("➕ New Session", use_container_width=True):
            SessionManager.create_new_session()
            st.rerun()

        if col_del.button("🗑️", help="Delete active session"):
            SessionManager.delete_current_session()
            st.rerun()

        user_id = SessionManager.get_current_user_id()
        sessions = APIClient.list_sessions(user_id)
        if sessions:
            session_options = {
                s[
                    "session_id"
                ]: f"📌 {s['title']} ({s['updated_at'][11:16] if 'updated_at' in s else 'recent'})"
                for s in sessions
            }
            current_id = st.session_state.get("current_session_id")
            option_ids = list(session_options.keys())

            if current_id not in option_ids and option_ids:
                current_id = option_ids[0]
                st.session_state.current_session_id = current_id

            curr_idx = option_ids.index(current_id) if current_id in option_ids else 0

            def handle_session_change():
                selected_id = st.session_state.get("session_selector_widget")
                if selected_id:
                    SessionManager.switch_session(selected_id)

            st.selectbox(
                "Select Conversation Session:",
                options=option_ids,
                format_func=lambda sid: session_options[sid],
                index=curr_idx,
                key="session_selector_widget",
                on_change=handle_session_change,
            )

    @staticmethod
    def render_sidebar():
        with st.sidebar:
            st.title("⚡ AI Chat Control")
            UIComponents._render_sidebar_account()
            st.markdown("---")
            UIComponents._render_sidebar_session_history()

    @staticmethod
    def render_quick_actions() -> str | None:
        st.markdown("##### 💡 Suggested Prompts:")
        cols = st.columns(3)

        if cols[0].button("🔍 Latest AI & Tech News", use_container_width=True):
            return (
                "What are the latest trending news stories in AI and technology today?"
            )
        if cols[1].button("🌤️ Weather & Local Facts", use_container_width=True):
            return "Tell me the local weather and interesting facts about my current location!"
        if cols[2].button("💻 Python Async Code Example", use_container_width=True):
            return "Explain Python asyncio and write a code example using async/await."
        return None

    @staticmethod
    def render_chat_messages():
        for msg in st.session_state.get("messages", []):
            role = msg.get("role")
            content = msg.get("content", "")
            if role == "assistant":
                with st.chat_message("assistant", avatar="🤖"):
                    st.markdown(content)
            elif role == "user":
                with st.chat_message("user", avatar="👤"):
                    st.markdown(content)
            elif role == "tool":
                st.markdown(
                    f"<div class='tool-card'>{content}</div>",
                    unsafe_allow_html=True,
                )

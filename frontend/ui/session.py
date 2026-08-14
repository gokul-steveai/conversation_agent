import streamlit as st

from .api_client import APIClient


class SessionManager:
    @staticmethod
    def get_current_user_id() -> str:
        if "user_id" not in st.session_state or not st.session_state.user_id:
            st.session_state.user_id = "default_user"
        return st.session_state.user_id

    @staticmethod
    def init_session() -> None:
        user_id = SessionManager.get_current_user_id()
        user_name = st.session_state.get("user_name", "")

        if "current_session_id" not in st.session_state:
            sessions = APIClient.list_sessions(user_id)
            if sessions:
                latest_id = sessions[0]["session_id"]
                detail = APIClient.load_session(latest_id, user_id)
                if detail:
                    st.session_state.current_session_id = detail["session_id"]
                    st.session_state.session_selector_widget = detail["session_id"]
                    state = detail.get("state", {})
                    state["user_id"] = user_id
                    if user_name and not state.get("name"):
                        state["name"] = user_name
                    st.session_state.state = state
                    st.session_state.messages = detail.get("messages", [])
                    st.session_state.history_messages = detail.get(
                        "history_messages", []
                    )
                    return

            detail = APIClient.create_session(user_id, title="New Chat Session")
            if detail:
                st.session_state.current_session_id = detail["session_id"]
                st.session_state.session_selector_widget = detail["session_id"]
                state = detail.get("state", {})
                state["user_id"] = user_id
                if user_name and not state.get("name"):
                    state["name"] = user_name
                st.session_state.state = state
                st.session_state.messages = detail.get("messages", [])
                st.session_state.history_messages = detail.get("history_messages", [])

    @staticmethod
    def create_new_session() -> None:
        user_id = SessionManager.get_current_user_id()
        user_name = st.session_state.get("user_name", "")
        detail = APIClient.create_session(user_id, title="New Chat Session")
        if detail:
            new_id = detail["session_id"]
            st.session_state.current_session_id = new_id
            st.session_state.session_selector_widget = new_id
            state = detail.get("state", {})
            state["user_id"] = user_id
            if user_name and not state.get("name"):
                state["name"] = user_name
            st.session_state.state = state
            st.session_state.messages = [
                {
                    "role": "assistant",
                    "content": f"Hello {user_name or 'there'}! How can I help you today?",
                }
            ]
            st.session_state.history_messages = []

    @staticmethod
    def switch_session(session_id: str) -> None:
        user_id = SessionManager.get_current_user_id()
        detail = APIClient.load_session(session_id, user_id)
        if detail:
            st.session_state.current_session_id = detail["session_id"]
            st.session_state.session_selector_widget = detail["session_id"]
            state = detail.get("state", {})
            state["user_id"] = user_id
            st.session_state.state = state
            st.session_state.messages = detail.get("messages", [])
            st.session_state.history_messages = detail.get("history_messages", [])

    @staticmethod
    def delete_current_session() -> None:
        user_id = SessionManager.get_current_user_id()
        if "current_session_id" in st.session_state:
            curr_id = st.session_state.current_session_id
            success = APIClient.delete_session(curr_id, user_id)
            if success:
                if "current_session_id" in st.session_state:
                    del st.session_state.current_session_id
                if "session_selector_widget" in st.session_state:
                    del st.session_state.session_selector_widget
                SessionManager.init_session()

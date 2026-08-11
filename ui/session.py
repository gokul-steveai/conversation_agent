import asyncio

import streamlit as st

from config.constants import NODE_ENGAGEMENT, NODE_PERSONAL_INFO, NODE_TOPIC_PREF
from services.session_service import SessionService


class SessionManager:
    """Streamlit Session State UI Adapter delegating all domain operations to Async SessionService."""

    @staticmethod
    def init_session() -> None:
        if "current_session_id" not in st.session_state:
            sessions = asyncio.run(SessionService.list_sessions())
            if sessions:
                latest_id = sessions[0]["session_id"]
                data = asyncio.run(SessionService.load_session(latest_id))
                if data:
                    st.session_state.current_session_id = latest_id
                    (
                        st.session_state.state,
                        st.session_state.messages,
                        st.session_state.history_messages,
                    ) = data
                    return

            (
                new_id,
                init_state,
                init_msgs,
                init_history,
            ) = asyncio.run(SessionService.create_session("New Session"))
            st.session_state.current_session_id = new_id
            st.session_state.state = init_state
            st.session_state.messages = init_msgs
            st.session_state.history_messages = init_history

    @staticmethod
    def save_current_session() -> None:
        if "current_session_id" in st.session_state:
            asyncio.run(
                SessionService.save_session(
                    st.session_state.current_session_id,
                    st.session_state.state,
                    st.session_state.messages,
                    st.session_state.history_messages,
                )
            )

    @staticmethod
    def create_new_session() -> None:
        (
            new_id,
            init_state,
            init_msgs,
            init_history,
        ) = asyncio.run(SessionService.create_session("New Session"))
        st.session_state.current_session_id = new_id
        st.session_state.state = init_state
        st.session_state.messages = init_msgs
        st.session_state.history_messages = init_history

    @staticmethod
    def switch_session(session_id: str) -> None:
        data = asyncio.run(SessionService.load_session(session_id))
        if data:
            st.session_state.current_session_id = session_id
            (
                st.session_state.state,
                st.session_state.messages,
                st.session_state.history_messages,
            ) = data

    @staticmethod
    def delete_current_session() -> None:
        if "current_session_id" in st.session_state:
            curr_id = st.session_state.current_session_id
            asyncio.run(SessionService.delete_session(curr_id))
            del st.session_state.current_session_id
            SessionManager.init_session()

    @staticmethod
    def get_progress() -> int:
        s = st.session_state.state
        if s["current_agent"] == NODE_PERSONAL_INFO:
            if s["name"] or s["location"]:
                return 25
            return 10
        elif s["current_agent"] == NODE_TOPIC_PREF:
            if s["topic_preferences"]:
                return 70
            return 50
        elif s["current_agent"] == NODE_ENGAGEMENT:
            return 100
        return 100

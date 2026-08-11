import streamlit as st

from config.constants import NODE_ENGAGEMENT, NODE_PERSONAL_INFO, NODE_TOPIC_PREF
from schemas.session import CreateSessionRequest, SaveSessionRequest
from services.session_service import SessionService
from utils.async_runner import run_async


class SessionManager:
    @staticmethod
    def get_current_user_id() -> str:
        if "user_id" not in st.session_state or not st.session_state.user_id:
            st.session_state.user_id = "default_user"
        return st.session_state.user_id

    @staticmethod
    def init_session() -> None:
        user_id = SessionManager.get_current_user_id()
        if "current_session_id" not in st.session_state:
            sessions = run_async(SessionService.list_sessions(user_id))
            if sessions:
                latest_id = sessions[0].session_id
                detail = run_async(SessionService.load_session(latest_id, user_id))
                if detail:
                    st.session_state.current_session_id = detail.session_id
                    st.session_state.state = detail.state
                    st.session_state.messages = detail.messages
                    st.session_state.history_messages = detail.history_messages
                    return

            create_req = CreateSessionRequest(user_id=user_id, title="New Session")
            detail = run_async(SessionService.create_session(create_req))
            st.session_state.current_session_id = detail.session_id
            st.session_state.state = detail.state
            st.session_state.messages = detail.messages
            st.session_state.history_messages = detail.history_messages

    @staticmethod
    def save_current_session() -> None:
        user_id = SessionManager.get_current_user_id()
        if "current_session_id" in st.session_state:
            save_req = SaveSessionRequest(
                session_id=st.session_state.current_session_id,
                user_id=user_id,
                state=st.session_state.state,
                messages=st.session_state.messages,
                history_messages=st.session_state.history_messages,
            )
            run_async(SessionService.save_session(save_req))

    @staticmethod
    def create_new_session() -> None:
        user_id = SessionManager.get_current_user_id()
        create_req = CreateSessionRequest(user_id=user_id, title="New Session")
        detail = run_async(SessionService.create_session(create_req))
        st.session_state.current_session_id = detail.session_id
        st.session_state.state = detail.state
        st.session_state.messages = detail.messages
        st.session_state.history_messages = detail.history_messages

    @staticmethod
    def switch_session(session_id: str) -> None:
        user_id = SessionManager.get_current_user_id()
        detail = run_async(SessionService.load_session(session_id, user_id))
        if detail:
            st.session_state.current_session_id = detail.session_id
            st.session_state.state = detail.state
            st.session_state.messages = detail.messages
            st.session_state.history_messages = detail.history_messages

    @staticmethod
    def delete_current_session() -> None:
        user_id = SessionManager.get_current_user_id()
        if "current_session_id" in st.session_state:
            curr_id = st.session_state.current_session_id
            run_async(SessionService.delete_session(curr_id, user_id))
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

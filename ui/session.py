import streamlit as st
from langchain_core.messages import AIMessage, SystemMessage

from config.constants import (
    DEFAULT_GREETING,
    NODE_ENGAGEMENT,
    NODE_PERSONAL_INFO,
    NODE_TOPIC_PREF,
    SYSTEM_PROMPT_PERSONAL_INFO,
)


class SessionManager:
    @staticmethod
    def init_session():
        if "messages" not in st.session_state:
            st.session_state.messages = [
                {"role": "assistant", "content": DEFAULT_GREETING}
            ]

        if "state" not in st.session_state:
            st.session_state.state = {
                "name": "",
                "location": "",
                "topic_preferences": [],
                "engagement_response": "",
                "current_agent": NODE_PERSONAL_INFO,
                "completed": False,
            }

        if "history_messages" not in st.session_state:
            st.session_state.history_messages = [
                SystemMessage(SYSTEM_PROMPT_PERSONAL_INFO),
                AIMessage(DEFAULT_GREETING),
            ]

    @staticmethod
    def reset_session():
        st.session_state.messages = [{"role": "assistant", "content": DEFAULT_GREETING}]
        st.session_state.state = {
            "name": "",
            "location": "",
            "topic_preferences": [],
            "engagement_response": "",
            "current_agent": NODE_PERSONAL_INFO,
            "completed": False,
        }
        st.session_state.history_messages = [
            SystemMessage(SYSTEM_PROMPT_PERSONAL_INFO),
            AIMessage(DEFAULT_GREETING),
        ]

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

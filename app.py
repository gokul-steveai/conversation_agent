import asyncio

import streamlit as st

from controllers.onboarding_controller import OnboardingController
from ui.components import UIComponents
from ui.session import SessionManager

# Page Configuration
st.set_page_config(
    page_title="AI Onboarding Assistant",
    page_icon="⚡",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Initialize Custom Theme & Session State
UIComponents.render_custom_styles()
SessionManager.init_session()

# Render Sidebar & Header Components
UIComponents.render_sidebar()
UIComponents.render_header()

# Render Quick Action Suggestions & Chat History
quick_prompt = UIComponents.render_quick_actions()
UIComponents.render_chat_messages()

# User Input & Orchestration Controller Execution
user_prompt = st.chat_input("Type your response here...") or quick_prompt

if user_prompt:
    st.session_state.messages.append({"role": "user", "content": user_prompt})

    with st.spinner("⚡ Agent reasoning & routing..."):
        agent_reply, tool_logs = asyncio.run(
            OnboardingController.process_step(
                user_text=user_prompt,
                state=st.session_state.state,
                history_messages=st.session_state.history_messages,
            )
        )

    for tool_log in tool_logs:
        st.session_state.messages.append(tool_log)

    st.session_state.messages.append({"role": "assistant", "content": agent_reply})
    st.rerun()

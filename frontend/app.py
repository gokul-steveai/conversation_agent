import html

import streamlit as st

try:
    from backend.config.constants import APP_TITLE
except ImportError:
    APP_TITLE = "AI Chat Assistant"

try:
    from frontend.ui import APIClient, AuthUI, SessionManager, UIComponents
except ImportError:
    from .ui import APIClient, AuthUI, SessionManager, UIComponents


# Page Configuration
st.set_page_config(
    page_title=APP_TITLE,
    page_icon="⚡",
    layout="wide",
    initial_sidebar_state="expanded",
)

UIComponents.render_custom_styles()

# Authentication Guard
if not AuthUI.is_authenticated():
    AuthUI.render_auth_page()
    st.stop()

SessionManager.init_session()

UIComponents.render_sidebar()
UIComponents.render_header()

# Render Quick Action Suggestions & Chat History
quick_prompt = UIComponents.render_quick_actions()
UIComponents.render_chat_messages()

# User Input & Orchestration Execution via FastAPI APIClient
user_prompt = (
    st.chat_input("Ask anything, search live web, or write code...") or quick_prompt
)

if user_prompt:
    prompt_str: str = user_prompt
    st.session_state.messages.append({"role": "user", "content": prompt_str})

    # Display user prompt in chat immediately
    with st.chat_message("user", avatar="👤"):
        st.markdown(prompt_str)

    with st.chat_message("assistant", avatar="🤖"):

        def generate_ui_stream():
            event_stream = APIClient.stream_chat_message(
                user_text=prompt_str,
                session_id=st.session_state.current_session_id,
                state=st.session_state.get("state", {}),
            )
            for chunk_item in event_stream:
                event_type = chunk_item.get("event")
                data_obj = chunk_item.get("data", {})
                if isinstance(data_obj, str):
                    data_obj = {"chunk": data_obj, "content": data_obj}

                if event_type == "tool":
                    content_str = data_obj.get("content", "")
                    escaped_content = html.escape(content_str)
                    st.markdown(
                        f"<div class='tool-card'>{escaped_content}</div>",
                        unsafe_allow_html=True,
                    )
                    st.session_state.messages.append(
                        {"role": "tool", "content": content_str}
                    )
                elif event_type == "state":
                    updated_state = data_obj.get("updated_state")
                    if updated_state and isinstance(updated_state, dict):
                        st.session_state.state = updated_state
                elif event_type == "error":
                    err_msg = data_obj.get(
                        "error", "An error occurred while streaming."
                    )
                    st.error(f"❌ {err_msg}")
                elif event_type == "message":
                    text_chunk = data_obj.get("chunk", "")
                    yield text_chunk

        full_response = st.write_stream(generate_ui_stream())

    st.session_state.messages.append({"role": "assistant", "content": full_response})
    st.rerun()

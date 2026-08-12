import streamlit as st
from pydantic import ValidationError

try:
    from backend.services.auth_service import AuthService
    from backend.utils.sanitizer import format_validation_error
except ImportError:
    AuthService = None

    def format_validation_error(e):
        return str(e)


from .api_client import APIClient


class AuthUI:
    @staticmethod
    def is_authenticated() -> bool:
        token = st.session_state.get("jwt_token")
        if not token:
            return False

        if AuthService:
            payload = AuthService.verify_access_token(token)
            if not payload:
                AuthUI.logout(rerun=False)
                return False

            st.session_state.user_id = payload.get("sub")
            st.session_state.user_name = payload.get("name")
            st.session_state.user_email = payload.get("email")
        return True

    @staticmethod
    def logout(rerun: bool = True) -> None:
        keys = [
            "jwt_token",
            "user_id",
            "user_name",
            "user_email",
            "current_session_id",
            "state",
            "messages",
            "history_messages",
        ]
        for key in keys:
            if key in st.session_state:
                del st.session_state[key]
        if rerun:
            st.rerun()

    @staticmethod
    def _store_auth_user(res: dict, success_msg: str) -> None:
        user = res.get("user", {})
        st.session_state.jwt_token = res.get("token")
        st.session_state.user_id = user.get("user_id")
        st.session_state.user_name = user.get("name")
        st.session_state.user_email = user.get("email")
        st.success(success_msg)
        st.rerun()

    @staticmethod
    def _render_login_tab() -> None:
        with st.form("login_form", clear_on_submit=False):
            email = st.text_input("📧 Email Address", placeholder="user@example.com")
            password = st.text_input(
                "🔒 Password", type="password", placeholder="••••••••"
            )
            if st.form_submit_button("Sign In", use_container_width=True):
                try:
                    res = APIClient.login(email, password)
                    if not res.get("success"):
                        st.error(f"❌ {res.get('error', 'Login failed')}")
                    else:
                        AuthUI._store_auth_user(
                            res, f"✨ Welcome back, {res.get('user', {}).get('name')}!"
                        )
                except ValidationError as val_err:
                    st.error(f"❌ {format_validation_error(val_err)}")
                except Exception as e:
                    st.error(f"❌ Error: {e}")

    @staticmethod
    def _render_register_tab() -> None:
        with st.form("register_form", clear_on_submit=False):
            name = st.text_input("👤 Full Name", placeholder="Ayush")
            email = st.text_input("📧 Email Address", placeholder="ayush@example.com")
            pass1 = st.text_input(
                "🔒 Password", type="password", placeholder="••••••••"
            )
            pass2 = st.text_input(
                "🔒 Confirm Password", type="password", placeholder="••••••••"
            )
            if st.form_submit_button("Register Account", use_container_width=True):
                if pass1 != pass2:
                    st.error("❌ Passwords do not match.")
                    return
                try:
                    res = APIClient.register(name, email, pass1)
                    if not res.get("success"):
                        st.error(f"❌ {res.get('error', 'Registration failed')}")
                    else:
                        AuthUI._store_auth_user(
                            res, "🎉 Registration successful! Logging in..."
                        )
                except ValidationError as val_err:
                    st.error(f"❌ {format_validation_error(val_err)}")
                except Exception as e:
                    st.error(f"❌ Error: {e}")

    @staticmethod
    def render_auth_page() -> None:
        st.markdown(
            """
            <style>
                .auth-card {
                    background: rgba(19, 27, 46, 0.75);
                    backdrop-filter: blur(20px);
                    border: 1px solid rgba(255, 255, 255, 0.12);
                    border-radius: 20px;
                    padding: 32px 40px;
                    box-shadow: 0 16px 48px rgba(0, 0, 0, 0.5);
                    max-width: 480px;
                    margin: 40px auto;
                }
                .auth-title {
                    font-size: 1.8rem; font-weight: 700; color: #f8fafc; margin-bottom: 8px; text-align: center;
                }
                .auth-subtitle {
                    font-size: 0.95rem; color: #94a3b8; margin-bottom: 24px; text-align: center;
                }
            </style>
            """,
            unsafe_allow_html=True,
        )
        _, col2, _ = st.columns([1, 2, 1])
        with col2:
            st.markdown(
                """
                <div class="auth-card">
                    <div class="auth-title">⚡ Conversation Agent</div>
                    <div class="auth-subtitle">Enterprise AI Assistant</div>

                </div>
                """,
                unsafe_allow_html=True,
            )
            tab_login, tab_register = st.tabs(["🔑 Sign In", "📝 Create Account"])
            with tab_login:
                AuthUI._render_login_tab()
            with tab_register:
                AuthUI._render_register_tab()

import streamlit as st
from pydantic import ValidationError

from schemas.auth import UserLoginRequest, UserRegisterRequest
from services.auth_service import AuthService
from utils.async_runner import run_async
from utils.sanitizer import format_validation_error


class AuthUI:
    @staticmethod
    def is_authenticated() -> bool:
        token = st.session_state.get("jwt_token")
        if not token:
            return False

        payload = AuthService.verify_access_token(token)
        if not payload:
            AuthUI.logout(rerun=False)
            return False

        # Refresh session user details from verified payload
        st.session_state.user_id = payload.get("sub")
        st.session_state.user_name = payload.get("name")
        st.session_state.user_email = payload.get("email")
        return True

    @staticmethod
    def logout(rerun: bool = True) -> None:
        keys_to_clear = [
            "jwt_token",
            "user_id",
            "user_name",
            "user_email",
            "current_session_id",
            "state",
            "messages",
            "history_messages",
        ]
        for key in keys_to_clear:
            if key in st.session_state:
                del st.session_state[key]
        if rerun:
            st.rerun()

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
                    font-size: 1.8rem;
                    font-weight: 700;
                    color: #f8fafc;
                    margin-bottom: 8px;
                    text-align: center;
                }
                .auth-subtitle {
                    font-size: 0.95rem;
                    color: #94a3b8;
                    margin-bottom: 24px;
                    text-align: center;
                }
            </style>
            """,
            unsafe_allow_html=True,
        )

        col1, col2, col3 = st.columns([1, 2, 1])

        with col2:
            st.markdown(
                """
                <div class="auth-card">
                    <div class="auth-title">⚡ Conversation Agent</div>
                    <div class="auth-subtitle">Enterprise JWT Authenticated Multi-Agent System</div>
                </div>
                """,
                unsafe_allow_html=True,
            )

            tab_login, tab_register = st.tabs(["🔑 Sign In", "📝 Create Account"])

            with tab_login:
                with st.form("login_form", clear_on_submit=False):
                    email = st.text_input(
                        "📧 Email Address", placeholder="user@example.com"
                    )
                    password = st.text_input(
                        "🔒 Password", type="password", placeholder="••••••••"
                    )
                    submit_login = st.form_submit_button(
                        "Sign In", use_container_width=True
                    )

                    if submit_login:
                        try:
                            req = UserLoginRequest(email=email, password=password)
                            response = run_async(AuthService.authenticate_user(req))
                            if not response.success:
                                st.error(f"❌ {response.error}")
                            elif response.user and response.token:
                                st.session_state.jwt_token = response.token
                                st.session_state.user_id = response.user.user_id
                                st.session_state.user_name = response.user.name
                                st.session_state.user_email = response.user.email
                                st.success(f"✨ Welcome back, {response.user.name}!")
                                st.rerun()
                        except ValidationError as val_err:
                            st.error(f"❌ {format_validation_error(val_err)}")
                        except Exception as e:
                            st.error(f"❌ Error: {e}")

            with tab_register:
                with st.form("register_form", clear_on_submit=False):
                    reg_name = st.text_input("👤 Full Name", placeholder="Gokul Panwar")
                    reg_email = st.text_input(
                        "📧 Email Address", placeholder="gokul@example.com"
                    )
                    reg_pass1 = st.text_input(
                        "🔒 Password", type="password", placeholder="••••••••"
                    )
                    reg_pass2 = st.text_input(
                        "🔒 Confirm Password", type="password", placeholder="••••••••"
                    )
                    submit_reg = st.form_submit_button(
                        "Register Account", use_container_width=True
                    )

                    if submit_reg:
                        if reg_pass1 != reg_pass2:
                            st.error("❌ Passwords do not match.")
                        else:
                            try:
                                reg_req = UserRegisterRequest(
                                    name=reg_name, email=reg_email, password=reg_pass1
                                )
                                response = run_async(AuthService.register_user(reg_req))
                                if not response.success:
                                    st.error(f"❌ {response.error}")
                                elif response.user and response.token:
                                    st.session_state.jwt_token = response.token
                                    st.session_state.user_id = response.user.user_id
                                    st.session_state.user_name = response.user.name
                                    st.session_state.user_email = response.user.email
                                    st.success(
                                        "🎉 Registration successful! Logging in..."
                                    )
                                    st.rerun()
                            except ValidationError as val_err:
                                st.error(f"❌ {format_validation_error(val_err)}")
                            except Exception as e:
                                st.error(f"❌ Error: {e}")

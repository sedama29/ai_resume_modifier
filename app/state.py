import sqlite3

import streamlit as st

import db.repository as repo
from app.auth import authz
from app.auth.admin_client import verify_id_token
from app.auth.firebase_login import firebase_login_widget
from db.connection import get_connection, init_db


def get_db() -> sqlite3.Connection:
    if "db_initialized" not in st.session_state:
        init_db()
        st.session_state["db_initialized"] = True
    return get_connection()


def get_current_user() -> dict | None:
    return st.session_state.get("user")


_HERO_HTML = """
<div style="text-align:center; padding: 64px 0 12px 0;">
  <div style="font-size: 40px; margin-bottom: 8px;">📄✨</div>
  <div style="font-size: 2.4em; font-weight: 800; letter-spacing: -0.03em;
              background: linear-gradient(135deg, #2563EB 0%, #4F46E5 60%, #7C3AED 100%);
              -webkit-background-clip: text; background-clip: text; color: transparent;">
    AI Resume Modifier
  </div>
  <div style="color: #64748B; font-size: 1.05em; margin-top: 6px;">
    Tailor your resume to any job — without ever inventing experience.
  </div>
</div>
"""


def require_user() -> dict:
    """Auth gate -- call at the top of every page. Blocks (st.stop()) until a
    signed-in AND authorized user is established in session_state."""
    user = get_current_user()
    if user is not None:
        return user

    st.markdown(_HERO_HTML, unsafe_allow_html=True)
    col1, col2, col3 = st.columns([1, 1.1, 1])
    with col2:
        result = firebase_login_widget(key="firebase_login")

    if result is None:
        with col2:
            st.markdown(
                "<div style='text-align:center;color:#94A3B8;font-size:0.9em;'>Checking session…</div>",
                unsafe_allow_html=True,
            )
        st.stop()

    if result["status"] == "error":
        with col2:
            st.error(result["message"])
        st.stop()

    if result["status"] == "signed_out":
        with col2:
            st.markdown(
                "<div style='text-align:center;color:#64748B;'>"
                "Sign in with your authorized Google account to continue.</div>",
                unsafe_allow_html=True,
            )
        st.stop()

    # status == "signed_in"
    try:
        claims = verify_id_token(result["token"])
    except Exception:
        st.error("Your session could not be verified. Please sign in again.")
        st.stop()

    email = claims.get("email")
    try:
        record = authz.get_authorization(email) if email else None
    except Exception as e:
        st.error(f"Could not reach the authorization database: {e}")
        col1, col2 = st.columns(2)
        if col1.button("Retry"):
            st.rerun()
        if col2.button("Sign out"):
            sign_out()
        st.stop()

    if record is None or not record.get("active"):
        st.title("Access Denied")
        st.error(
            f"{email} is not authorized to use this application. "
            "Contact the administrator if you believe this is a mistake."
        )
        st.stop()

    authz.record_login(email, claims["uid"])
    st.session_state["user"] = {"uid": claims["uid"], "email": email, "role": record["role"]}
    st.rerun()


def require_superuser(user: dict) -> None:
    """Re-fetches the role fresh from Firestore -- never trusts the
    session-cached role for admin actions, so a demotion/deactivation takes
    effect on the very next admin action, not just the next full sign-in."""
    try:
        record = authz.get_authorization(user["email"])
    except Exception as e:
        st.error(f"Could not reach the authorization database: {e}")
        render_user_badge(user)
        st.stop()
    if record is None or not record.get("active") or record.get("role") != "superuser":
        st.title("Access Denied")
        st.error("This page is restricted to the Super User.")
        st.stop()


def sign_out() -> None:
    firebase_login_widget(command="sign_out", key="firebase_login")
    st.session_state.pop("user", None)
    st.rerun()


def render_user_badge(user: dict) -> None:
    with st.sidebar:
        st.caption(f"Signed in as {user['email']}")
        if user["role"] == "superuser":
            st.caption("Role: Super User")
        if st.button("Sign out"):
            sign_out()


def get_active_application_id() -> int | None:
    return st.session_state.get("active_application_id")


def set_active_application_id(application_id: int) -> None:
    st.session_state["active_application_id"] = application_id


def require_active_application_id(conn: sqlite3.Connection, owner_uid: str) -> int:
    app_id = get_active_application_id()
    if app_id is None:
        st.warning("No active job application selected. Start from the Job Input page.")
        st.stop()
    if repo.get_job_application_for_owner(conn, app_id, owner_uid) is None:
        st.session_state.pop("active_application_id", None)
        st.error("That application is no longer available.")
        st.stop()
    return app_id

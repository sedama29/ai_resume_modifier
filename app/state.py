from google.cloud.firestore_v1 import Client

import streamlit as st

import db.repository as repo
from app.auth import authz
from app.auth.admin_client import get_firestore, verify_id_token
from app.auth.firebase_login import firebase_login_widget


def get_db() -> Client:
    return get_firestore()


def get_current_user() -> dict | None:
    return st.session_state.get("user")


_HERO_HTML = """
<div style="text-align:center; padding: 72px 0 20px 0;">
  <div style="font-size: 2rem; font-weight: 650; letter-spacing: -0.03em; color: #0B1220;">
    AI Resume Modifier
  </div>
  <div style="color: #667085; font-size: 1rem; margin-top: 8px;">
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
    st.session_state["user"] = {
        "uid": claims["uid"],
        "email": email,
        "role": record["role"],
        "name": claims.get("name"),
        "picture": claims.get("picture"),
    }
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
    """Compact account card pinned to the bottom of the sidebar -- avatar
    (Google profile photo if available, else initials), name, role, sign out.
    Integrated into the sidebar rather than a few bare caption lines."""
    from app.styling import initials  # local import: styling imports streamlit only, no cycle risk either way

    with st.sidebar:
        st.markdown('<div style="margin-top:20px;"></div>', unsafe_allow_html=True)

        with st.container(border=True):
            picture = user.get("picture")
            display_name = user.get("name") or user["email"].split("@")[0]
            short_email = user["email"] if len(user["email"]) <= 26 else user["email"][:23] + "…"

            col1, col2 = st.columns([1, 4], vertical_alignment="center")
            with col1:
                if picture:
                    st.image(picture, width=32)
                else:
                    st.markdown(
                        f'<div style="width:32px;height:32px;border-radius:50%;background:#5B5FC7;color:#fff;'
                        f'display:flex;align-items:center;justify-content:center;font-size:0.8rem;font-weight:600;">'
                        f'{initials(user.get("name"), user["email"])}</div>',
                        unsafe_allow_html=True,
                    )
            with col2:
                st.markdown(
                    f'<div style="font-weight:600;font-size:0.88rem;color:#18181B;line-height:1.2;">{display_name}</div>'
                    f'<div style="font-size:0.76rem;color:#71717A;">{short_email}</div>',
                    unsafe_allow_html=True,
                )
            if user["role"] == "superuser":
                st.markdown(
                    '<div style="margin-top:6px;">'
                    '<span style="background:#F1F1FB;color:#5B5FC7;border:1px solid #D6D6F5;padding:2px 8px;'
                    'border-radius:6px;font-weight:500;font-size:0.72rem;">Super User</span></div>',
                    unsafe_allow_html=True,
                )
            if st.button("Sign out", use_container_width=True, key="sign_out_btn"):
                sign_out()


def get_active_application_id() -> str | None:
    return st.session_state.get("active_application_id")


def set_active_application_id(application_id: str) -> None:
    st.session_state["active_application_id"] = application_id


def require_active_application_id(db: Client, owner_uid: str) -> str:
    app_id = get_active_application_id()
    if app_id is None:
        st.warning("No active job application selected. Start from the Job Input page.")
        st.stop()
    if repo.get_job_application(db, owner_uid, app_id) is None:
        st.session_state.pop("active_application_id", None)
        st.error("That application is no longer available.")
        st.stop()
    return app_id

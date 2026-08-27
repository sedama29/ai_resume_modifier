import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

import streamlit as st

from app.auth import authz
from app.state import get_db, render_user_badge, require_superuser, require_user


from app.styling import inject_custom_css, page_header, status_badge
inject_custom_css()

db = get_db()  # unused directly here, but keeps the require_user() page convention consistent
user = require_user()
require_superuser(user)
render_user_badge(user)

page_header("User Management", "Changes take effect immediately -- authorization is re-checked from Firestore on every page load.")

users = sorted(authz.list_users(), key=lambda u: u.get("email", ""))


@st.dialog("Remove user?")
def confirm_remove(email: str):
    st.write(f"Remove **{email}**? They will immediately lose access, and would need to be re-added to sign in again.")
    col1, col2 = st.columns(2)
    if col1.button("Cancel", use_container_width=True):
        st.rerun()
    if col2.button("Remove", type="primary", use_container_width=True):
        authz.delete_user(email)
        st.rerun()


st.caption(f"{len(users)} authorized user{'s' if len(users) != 1 else ''}")

if not users:
    st.info("No authorized users yet.")

header = st.columns([3, 1.5, 1.5, 2.5])
if users:
    header[0].caption("USER")
    header[1].caption("ROLE")
    header[2].caption("STATUS")
    header[3].caption("")

for u in users:
    with st.container(border=True):
        cols = st.columns([3, 1.5, 1.5, 2.5], vertical_alignment="center")
        cols[0].write(f"**{u['email']}**" + (" (you)" if u["email"] == user["email"] else ""))
        cols[1].markdown(
            status_badge("Super User", "gray") if u.get("role") == "superuser" else status_badge("User", "gray"),
            unsafe_allow_html=True,
        )
        cols[2].markdown(
            status_badge("Active", "green") if u.get("active") else status_badge("Inactive", "gray"),
            unsafe_allow_html=True,
        )

        if u["email"] == user["email"]:
            cols[3].caption("This is you")
            continue

        with cols[3]:
            btn_cols = st.columns(2)
            if u.get("active"):
                if btn_cols[0].button("Deactivate", key=f"deactivate_{u['email']}", use_container_width=True):
                    authz.set_user_active(u["email"], False)
                    st.rerun()
            else:
                if btn_cols[0].button("Reactivate", key=f"reactivate_{u['email']}", use_container_width=True):
                    authz.set_user_active(u["email"], True)
                    st.rerun()
            if btn_cols[1].button("Remove", key=f"remove_{u['email']}", use_container_width=True):
                confirm_remove(u["email"])

st.write("")
with st.container(border=True):
    st.markdown("**Add a user**")
    st.caption("No password required -- they'll sign in with Google using this email.")
    with st.form("add_user_form", clear_on_submit=True):
        new_email = st.text_input("Google Email", placeholder="friend@gmail.com")
        if st.form_submit_button("Add User", type="primary"):
            if not new_email or "@" not in new_email:
                st.error("Enter a valid email address.")
            else:
                authz.add_user(new_email.strip().lower(), added_by=user["email"])
                st.success(f"Added {new_email} as an authorized user (role: user).")
                st.rerun()

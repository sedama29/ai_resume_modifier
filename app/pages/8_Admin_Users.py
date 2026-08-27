import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

import streamlit as st

from app.auth import authz
from app.state import get_db, render_user_badge, require_superuser, require_user

st.set_page_config(page_title="Admin: Users", page_icon="🔐", layout="wide")

conn = get_db()  # unused directly here, but keeps the require_user() page convention consistent
user = require_user()
require_superuser(user)
render_user_badge(user)

st.title("Admin: User Management")
st.caption("Changes here take effect immediately -- authorization is re-checked from Firestore on every page load.")

users = sorted(authz.list_users(), key=lambda u: u.get("email", ""))

st.subheader("Authorized users")
if not users:
    st.info("No authorized users yet.")
for u in users:
    with st.container(border=True):
        cols = st.columns([3, 1, 1, 2])
        cols[0].write(f"**{u['email']}**" + (" (you)" if u["email"] == user["email"] else ""))
        cols[1].write(u.get("role", "user"))
        cols[2].write("🟢 active" if u.get("active") else "🔴 inactive")
        cols[3].write(f"added by {u.get('added_by', '?')} on {u.get('added_at', '?')[:10]}")

        if u["email"] == user["email"]:
            st.caption("You can't deactivate or remove your own account here.")
            continue

        btn_cols = st.columns(3)
        if u.get("active"):
            if btn_cols[0].button("Deactivate", key=f"deactivate_{u['email']}"):
                authz.set_user_active(u["email"], False)
                st.rerun()
        else:
            if btn_cols[0].button("Reactivate", key=f"reactivate_{u['email']}"):
                authz.set_user_active(u["email"], True)
                st.rerun()
        if btn_cols[1].button("Remove", key=f"remove_{u['email']}"):
            authz.delete_user(u["email"])
            st.rerun()

st.subheader("Add a user")
st.caption("No password required -- they'll sign in with Google using this email.")
with st.form("add_user_form", clear_on_submit=True):
    new_email = st.text_input("Google Email")
    if st.form_submit_button("Add User", type="primary"):
        if not new_email or "@" not in new_email:
            st.error("Enter a valid email address.")
        else:
            authz.add_user(new_email.strip().lower(), added_by=user["email"])
            st.success(f"Added {new_email} as an authorized user (role: user).")
            st.rerun()

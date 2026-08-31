"""Entrypoint. Streamlit Cloud's "Main file path" should point here (not at
Profile.py) -- this is what builds the grouped, role-aware sidebar navigation,
which also disables the classic pages/ auto-discovery (every page still lives
in pages/, just no longer auto-listed from there).

st.navigation() must be called on EVERY run, authenticated or not -- if this
script st.stop()'d before reaching it (e.g. inside a blocking auth gate),
Streamlit falls back to classic pages/ auto-discovery for that run instead,
which is exactly the flat, role-blind nav this file exists to replace. So
the actual auth gate stays where it already was: at the top of each
individual page (Profile.py, pages/*.py each still call require_user()
themselves). Here we only need get_current_user() (non-blocking) to decide
whether the Admin section should appear at all.

The nav is built with position="hidden" and rendered manually via
st.page_link so the brand mark can sit above it -- Streamlit's built-in
st.navigation() sidebar widget always renders itself first regardless of
code order, which pushed the brand mark below the page list."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import streamlit as st

from app.state import get_current_user

st.set_page_config(page_title="AI Resume Modifier", layout="wide")

from app.styling import inject_custom_css
inject_custom_css()

user = get_current_user()

profile_page = st.Page("Profile.py", title="Profile", url_path="profile", default=True)
new_application_page = st.Page("pages/1_Job_Input.py", title="New Application", url_path="new-application")
history_page = st.Page("pages/7_Application_History.py", title="Application History", url_path="history")
workspace_pages = [profile_page, new_application_page, history_page]

# Reached via the in-page progress stepper + Continue buttons, not offered as
# independent sidebar jump-to links -- still fully addressable via
# st.switch_page. Included in st.navigation()'s page set for routing, just
# never passed to st.page_link below.
flow_pages = [
    st.Page("pages/2_Eligibility.py", title="Eligibility", url_path="flow-eligibility"),
    st.Page("pages/3_Match_Summary.py", title="Match", url_path="flow-match"),
    st.Page("pages/4_Followup_Questions.py", title="Questions", url_path="flow-questions"),
    st.Page("pages/5_Review_Changes.py", title="Review", url_path="flow-review"),
    st.Page("pages/5b_ATS_Check.py", title="ATS Check", url_path="flow-ats-check"),
    st.Page("pages/6_Generate.py", title="Generate", url_path="flow-generate"),
]

admin_pages = []
if user is not None and user["role"] == "superuser":
    admin_pages = [
        st.Page("pages/8_Admin_Users.py", title="Users", url_path="admin-users"),
        st.Page("pages/9_API_Usage.py", title="API Usage", url_path="admin-api-usage"),
    ]

pages = {"Workspace": workspace_pages + flow_pages}
if admin_pages:
    pages["Admin"] = admin_pages

pg = st.navigation(pages, position="hidden")

_SECTION_LABEL_CSS = (
    "font-size:0.68rem;text-transform:uppercase;letter-spacing:0.07em;"
    "color:#A1A1AA;font-weight:600;margin:{top}px 0 4px 6px;"
)

with st.sidebar:
    st.markdown(
        '<div style="display:flex;align-items:center;gap:8px;padding:6px 4px 14px 4px;">'
        '<span style="color:#5B5FC7;font-size:1.1rem;">✦</span>'
        '<span style="font-weight:600;font-size:0.95rem;color:#18181B;">AI Resume Modifier</span>'
        "</div>",
        unsafe_allow_html=True,
    )
    st.markdown(f'<div style="{_SECTION_LABEL_CSS.format(top=2)}">Workspace</div>', unsafe_allow_html=True)
    for page in workspace_pages:
        st.page_link(page)
    if admin_pages:
        st.markdown(f'<div style="{_SECTION_LABEL_CSS.format(top=14)}">Admin</div>', unsafe_allow_html=True)
        for page in admin_pages:
            st.page_link(page)

pg.run()

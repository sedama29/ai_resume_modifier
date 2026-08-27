"""Entrypoint. Streamlit Cloud's "Main file path" should point here (not at
Profile.py) -- this is what builds the grouped, role-aware sidebar navigation
via st.navigation(), which also disables the classic pages/ auto-discovery
(every page still lives in pages/, just no longer auto-listed from there).

st.navigation() must be called on EVERY run, authenticated or not -- if this
script st.stop()'d before reaching it (e.g. inside a blocking auth gate),
Streamlit falls back to classic pages/ auto-discovery for that run instead,
which is exactly the flat, role-blind nav this file exists to replace. So
the actual auth gate stays where it already was: at the top of each
individual page (Profile.py, pages/*.py each still call require_user()
themselves). Here we only need get_current_user() (non-blocking) to decide
whether the Admin section should appear at all."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import streamlit as st

from app.state import get_current_user

st.set_page_config(page_title="AI Resume Modifier", layout="wide")

from app.styling import inject_custom_css
inject_custom_css()

user = get_current_user()

with st.sidebar:
    st.markdown(
        '<div style="display:flex;align-items:center;gap:8px;padding:6px 4px 14px 4px;">'
        '<span style="color:#5B5FC7;font-size:1.1rem;">✦</span>'
        '<span style="font-weight:600;font-size:0.95rem;color:#18181B;">AI Resume Modifier</span>'
        "</div>",
        unsafe_allow_html=True,
    )

workspace_pages = [
    st.Page("Profile.py", title="Profile", url_path="profile", default=True),
    st.Page("pages/1_Job_Input.py", title="New Application", url_path="new-application"),
    st.Page("pages/7_Application_History.py", title="Application History", url_path="history"),
]

# Reached via the in-page progress stepper + Continue buttons, not offered as
# independent sidebar jump-to links (CSS in styling.py hides url_path="flow-*"
# from the nav) -- still fully addressable via st.switch_page.
flow_pages = [
    st.Page("pages/2_Eligibility.py", title="Eligibility", url_path="flow-eligibility"),
    st.Page("pages/3_Match_Summary.py", title="Match", url_path="flow-match"),
    st.Page("pages/4_Followup_Questions.py", title="Questions", url_path="flow-questions"),
    st.Page("pages/5_Review_Changes.py", title="Review", url_path="flow-review"),
    st.Page("pages/6_Generate.py", title="Generate", url_path="flow-generate"),
]

pages = {"Workspace": workspace_pages + flow_pages}

if user is not None and user["role"] == "superuser":
    pages["Admin"] = [
        st.Page("pages/8_Admin_Users.py", title="Users", url_path="admin-users"),
        st.Page("pages/9_API_Usage.py", title="API Usage", url_path="admin-api-usage"),
    ]

pg = st.navigation(pages)
pg.run()

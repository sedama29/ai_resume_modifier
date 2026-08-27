import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

import streamlit as st

import db.repository as repo
from app.auth import storage_client
from app.state import get_db, render_user_badge, require_user, set_active_application_id

st.set_page_config(page_title="Application History", page_icon="📚", layout="wide")

from app.styling import inject_custom_css, page_header
inject_custom_css()

db = get_db()
user = require_user()
render_user_badge(user)

page_header("📚", "Application History")

applications = repo.list_job_applications(db, user["uid"])

if not applications:
    st.info("No applications yet -- start one from Job Input.")
    st.stop()

search = st.text_input("Search by company or job title")

for app in applications:
    label = f"{app['company'] or 'Unknown'} — {app['job_title'] or 'Unknown'}"
    if search and search.lower() not in label.lower():
        continue

    eligibility = repo.get_latest_eligibility_result(db, user["uid"], app["id"])
    match = repo.get_latest_match_result(db, user["uid"], app["id"])
    versions = repo.list_resume_versions(db, user["uid"], app["id"])

    with st.container(border=True):
        st.write(f"### {label}")
        st.caption(f"Status: {app['status']} · Analyzed: {app['created_at']}")
        if app["job_url"]:
            st.write(f"[Job posting]({app['job_url']})")
        if eligibility:
            st.write(f"**Eligibility:** {eligibility['overall_recommendation']} — {eligibility['work_auth_category']}")
        if match and match.get("match_score") is not None:
            st.write(f"**Match score:** {match['match_score']:.0f}%")
        if versions:
            st.write("**Resume versions:**")
            for v in versions:
                compiled = "✅" if v["compile_success"] else "❌" if v["compile_success"] is not None else "—"
                st.write(f"- {v['name']} {compiled}")
                if v["pdf_storage_path"] and storage_client.blob_exists(v["pdf_storage_path"]):
                    st.download_button(
                        f"Download {v['name']}.pdf", storage_client.download_bytes(v["pdf_storage_path"]),
                        file_name=f"{v['name']}.pdf", mime="application/pdf", key=f"dl_{v['id']}",
                    )
        if st.button("Resume this application", key=f"resume_{app['id']}"):
            set_active_application_id(app["id"])
            st.switch_page("pages/2_Eligibility.py")

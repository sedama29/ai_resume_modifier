import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

import streamlit as st

import db.repository as repo
from app.auth import storage_client
from app.state import get_db, render_user_badge, require_user, set_active_application_id
from app.styling import status_badge


from app.styling import inject_custom_css, page_header
inject_custom_css()

db = get_db()
user = require_user()
render_user_badge(user)

page_header("Application History", "Every job you’ve analyzed, with the resume versions you generated.")

applications = repo.list_job_applications(db, user["uid"])

if not applications:
    st.info("No applications yet -- start one from New Application.")
    st.stop()

search = st.text_input("Search by company or job title", label_visibility="collapsed", placeholder="Search by company or job title")

STATUS_TONE = {
    "generated": "green", "reviewed": "green", "matched": "gray", "eligibility_checked": "gray",
    "analyzed": "gray", "questions_pending": "gray", "not_pursuing": "red", "draft": "gray",
}

header = st.columns([2.6, 2.6, 1.6, 1.8, 1.8])
header[0].caption("COMPANY")
header[1].caption("POSITION")
header[2].caption("DATE")
header[3].caption("RESUME VERSION")
header[4].caption("STATUS")

for app in applications:
    label = f"{app['company'] or 'Unknown'} — {app['job_title'] or 'Unknown'}"
    if search and search.lower() not in label.lower():
        continue

    versions = repo.list_resume_versions(db, user["uid"], app["id"])
    latest_version_label = versions[-1]["name"] if versions else "—"

    row = st.columns([2.6, 2.6, 1.6, 1.8, 1.8], vertical_alignment="center")
    row[0].markdown(f"**{app['company'] or 'Unknown'}**")
    row[1].write(app["job_title"] or "Unknown")
    row[2].write(str(app["created_at"])[:10])
    row[3].write(latest_version_label)
    tone = STATUS_TONE.get(app["status"], "gray")
    row[4].markdown(status_badge(app["status"].replace("_", " ").title(), tone), unsafe_allow_html=True)

    with st.expander("Details"):
        eligibility = repo.get_latest_eligibility_result(db, user["uid"], app["id"])
        match = repo.get_latest_match_result(db, user["uid"], app["id"])

        if app["job_url"]:
            st.write(f"[Job posting]({app['job_url']})")
        if eligibility:
            st.write(f"**Eligibility:** {eligibility['overall_recommendation'].replace('_', ' ').title()} — {eligibility['work_auth_category'].replace('_', ' ')}")
        if match and match.get("match_score") is not None:
            st.write(f"**Match score:** {match['match_score']:.0f}%")
        if versions:
            st.write("**Resume versions:**")
            for v in versions:
                compiled = "compiled" if v["compile_success"] else "failed" if v["compile_success"] is not None else "not generated"
                st.write(f"- {v['name']} — {compiled}")
                if v["pdf_storage_path"] and storage_client.blob_exists(v["pdf_storage_path"]):
                    st.download_button(
                        f"Download {v['name']}.pdf", storage_client.download_bytes(v["pdf_storage_path"]),
                        file_name=f"{v['name']}.pdf", mime="application/pdf", key=f"dl_{v['id']}",
                    )
        if st.button("Resume this application", key=f"resume_{app['id']}"):
            set_active_application_id(app["id"])
            st.switch_page("pages/2_Eligibility.py")
    st.write("")

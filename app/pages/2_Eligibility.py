import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

import streamlit as st

import db.repository as repo
from app.state import get_db, render_user_badge, require_active_application_id, require_user
from llm.eligibility import check_eligibility

st.set_page_config(page_title="Eligibility", page_icon="🚦", layout="wide")

conn = get_db()
user = require_user()
render_user_badge(user)

st.title("Eligibility Check")

application_id = require_active_application_id(conn, user["uid"])
application = repo.get_job_application(conn, application_id)
job_analysis_row = repo.get_latest_job_analysis(conn, application_id)

if job_analysis_row is None:
    st.error("No job analysis found for this application. Go back to Job Input.")
    st.stop()

st.subheader(f"{application['company'] or 'Unknown company'} — {application['job_title'] or 'Unknown title'}")

eligibility_row = repo.get_latest_eligibility_result(conn, application_id)

if eligibility_row is None or st.button("Re-run eligibility check"):
    candidate_profile = repo.get_candidate_profile(conn, user["uid"]) or {}
    job_analysis = json.loads(job_analysis_row["raw_llm_response_json"])
    with st.spinner("Checking eligibility..."):
        try:
            eligibility = check_eligibility(job_analysis, candidate_profile, conn, user["uid"])
        except Exception as e:
            st.error(f"Eligibility check failed: {e}")
            st.stop()
    repo.save_eligibility_result(conn, application_id, eligibility)
    repo.update_job_application_status(conn, application_id, "eligibility_checked")
    eligibility_row = repo.get_latest_eligibility_result(conn, application_id)

RECOMMENDATION_DISPLAY = {
    "strong_fit": ("🟢", "Likely Eligible — Strong Fit"),
    "proceed": ("🟢", "Likely Eligible"),
    "proceed_with_caution": ("🟡", "Potential Issues"),
    "do_not_apply": ("🔴", "Likely Not Eligible"),
    "insufficient_information": ("🟡", "Insufficient Information"),
}
icon, label = RECOMMENDATION_DISPLAY.get(eligibility_row["overall_recommendation"], ("🟡", "Unclear"))
st.markdown(f"## {icon} {label}")
st.caption("This is not legal advice. Verify sponsorship/work-authorization specifics directly with the employer.")

st.write("**Why:**", eligibility_row["work_auth_reasoning"])
if eligibility_row.get("experience_gap_assessment"):
    st.write("**Experience:**", eligibility_row["experience_gap_assessment"])
st.write("**Education match:**", eligibility_row["education_match"])

WORK_AUTH_DISPLAY = {
    "explicitly_compatible": "🟢 Employer indicates sponsorship/work authorization is compatible.",
    "potentially_compatible": "🟡 No explicit restriction found — verify the employer's sponsorship policy.",
    "potential_issue": "🟡 Posting requires authorization without sponsorship — potential H-1B issue.",
    "explicit_restriction": "🔴 Posting explicitly restricts eligibility (e.g. citizenship/PR required, or sponsorship unavailable).",
    "not_mentioned": "⚪ Work authorization not mentioned in the posting.",
    "needs_verification": "🟡 Ambiguous or contradictory language — needs verification.",
}
st.info(WORK_AUTH_DISPLAY.get(eligibility_row["work_auth_category"], eligibility_row["work_auth_category"]))

evidence = json.loads(eligibility_row["work_auth_evidence_json"] or "[]")
if evidence:
    with st.expander("Evidence quoted from the posting"):
        for q in evidence:
            st.write(f"> {q}")

col1, col2 = st.columns(2)
with col1:
    if st.button("Proceed to Match Summary →", type="primary"):
        st.switch_page("pages/3_Match_Summary.py")
with col2:
    if st.button("Not pursuing this one"):
        repo.update_job_application_status(conn, application_id, "not_pursuing")
        st.switch_page("pages/7_Application_History.py")

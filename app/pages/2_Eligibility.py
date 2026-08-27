import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

import streamlit as st

import db.repository as repo
from app.state import get_db, render_user_badge, require_active_application_id, require_user
from app.styling import status_badge, status_card
from llm.eligibility import check_eligibility


from app.styling import inject_custom_css, page_header, progress_stepper
inject_custom_css()

db = get_db()
user = require_user()
render_user_badge(user)

page_header("Eligibility Check")
progress_stepper("eligibility")

application_id = require_active_application_id(db, user["uid"])
application = repo.get_job_application(db, user["uid"], application_id)
job_analysis = repo.get_latest_job_analysis(db, user["uid"], application_id)

if job_analysis is None:
    st.error("No job analysis found for this application. Go back to Job Input.")
    st.stop()

st.caption(f"{application['company'] or 'Unknown company'} — {application['job_title'] or 'Unknown title'}")

eligibility = repo.get_latest_eligibility_result(db, user["uid"], application_id)

if eligibility is None or st.button("Re-run eligibility check"):
    candidate_profile = repo.get_candidate_profile(db, user["uid"]) or {}
    with st.spinner("Checking eligibility..."):
        try:
            eligibility = check_eligibility(job_analysis, candidate_profile, db, user["uid"])
        except Exception as e:
            st.error(f"Eligibility check failed: {e}")
            st.stop()
    repo.save_eligibility_result(db, user["uid"], application_id, eligibility)
    repo.update_job_application_status(db, user["uid"], application_id, "eligibility_checked")

RECOMMENDATION_DISPLAY = {
    "strong_fit": ("green", "Likely Eligible — Strong Fit"),
    "proceed": ("green", "Likely Eligible"),
    "proceed_with_caution": ("yellow", "Potential Issues"),
    "do_not_apply": ("red", "Likely Not Eligible"),
    "insufficient_information": ("yellow", "Insufficient Information"),
}
tone, label = RECOMMENDATION_DISPLAY.get(eligibility["overall_recommendation"], ("gray", "Unclear"))

description_parts = [eligibility["work_auth_reasoning"]]
if eligibility.get("experience_gap_assessment"):
    description_parts.append(eligibility["experience_gap_assessment"])
description_parts.append(f"Education: {eligibility['education_match']}.")
status_card(label, " ".join(p for p in description_parts if p), tone)
st.caption("This is not legal advice. Verify sponsorship/work-authorization specifics directly with the employer.")

WORK_AUTH_DISPLAY = {
    "explicitly_compatible": ("green", "Sponsorship/work authorization compatible"),
    "potentially_compatible": ("yellow", "No explicit restriction found — verify with the employer"),
    "potential_issue": ("yellow", "Requires authorization without sponsorship"),
    "explicit_restriction": ("red", "Explicit eligibility restriction"),
    "not_mentioned": ("gray", "Work authorization not mentioned"),
    "needs_verification": ("yellow", "Ambiguous language — needs verification"),
}
wa_tone, wa_label = WORK_AUTH_DISPLAY.get(eligibility["work_auth_category"], ("gray", eligibility["work_auth_category"]))
st.write("")
st.markdown(status_badge(wa_label, wa_tone), unsafe_allow_html=True)

evidence = eligibility.get("work_auth_evidence_quotes") or []
if evidence:
    with st.expander("Evidence quoted from the posting"):
        for q in evidence:
            st.write(f"> {q}")

st.write("")
col1, col2 = st.columns(2)
with col1:
    if st.button("Continue to Match Summary →", type="primary", use_container_width=True):
        st.switch_page("pages/3_Match_Summary.py")
with col2:
    if st.button("Not pursuing this one", use_container_width=True):
        repo.update_job_application_status(db, user["uid"], application_id, "not_pursuing")
        st.switch_page("pages/7_Application_History.py")

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

import streamlit as st

import db.repository as repo
from app.state import get_db, render_user_badge, require_active_application_id, require_user
from app.styling import requirement_row, status_card
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

# Never show a fabricated placeholder like "Unknown company" -- only show
# what's actually known, in whatever combination is available.
title_bits = [b for b in [application.get("company"), application.get("job_title")] if b]
if title_bits:
    st.caption(" — ".join(title_bits))

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

CATEGORY_ORDER = [
    "experience", "education", "required_skills", "work_authorization",
    "h1b_sponsorship", "citizenship_residency", "security_clearance",
]
CATEGORY_LABELS = {
    "experience": "Experience",
    "education": "Education",
    "required_skills": "Required Skills",
    "work_authorization": "Work Authorization",
    "h1b_sponsorship": "H-1B / Sponsorship",
    "citizenship_residency": "Citizenship / Residency",
    "security_clearance": "Security Clearance",
    "other": "Other Requirement",
}
# The auth-family categories that, when ALL unmentioned, collapse into one
# plain-English sentence instead of listing each one only to say "not
# mentioned" four separate times.
AUTH_CATEGORIES = ["work_authorization", "h1b_sponsorship", "citizenship_residency", "security_clearance"]
AUTH_PHRASES = {
    "work_authorization": "work authorization", "h1b_sponsorship": "sponsorship",
    "citizenship_residency": "citizenship, residency", "security_clearance": "security-clearance",
}

requirement_checks = eligibility.get("requirement_checks") or []
checks_by_category = {c["category"]: c for c in requirement_checks if c["category"] != "other"}
other_checks = [c for c in requirement_checks if c["category"] == "other"]


def _short_explanation() -> str:
    """A concise, scannable summary built entirely from the already-computed
    requirement statuses -- no new judgment, just plain-English phrasing of
    what the checks below already say."""
    sentences = []

    auth_statuses = {cat: checks_by_category.get(cat, {}).get("status") for cat in AUTH_CATEGORIES}
    if all(s == "not_mentioned" for s in auth_statuses.values()):
        sentences.append(
            "No work authorization, sponsorship, citizenship, residency, or security-clearance "
            "requirements were identified in the job description."
        )
    elif any(s in ("does_not_meet", "potential_issue", "needs_verification") for s in auth_statuses.values()):
        sentences.append("Some work authorization or eligibility requirements need your attention -- see the summary below.")
    else:
        unmentioned = [AUTH_PHRASES[c] for c, s in auth_statuses.items() if s == "not_mentioned"]
        if unmentioned:
            sentences.append(f"No {', '.join(unmentioned)} requirements were identified in the job description.")

    exp_status = checks_by_category.get("experience", {}).get("status")
    if exp_status == "not_mentioned":
        sentences.append("No minimum years of experience were specified.")
    elif exp_status == "meets":
        sentences.append("Your experience meets the stated requirement.")
    elif exp_status in ("does_not_meet", "potential_issue", "needs_verification"):
        sentences.append("Your experience may need a closer look against the stated requirement.")

    return " ".join(sentences) or "See the requirement summary below for details."


status_card(label, _short_explanation(), tone)
st.caption("This is not legal advice. Verify sponsorship/work-authorization specifics directly with the employer.")

st.write("")
if requirement_checks:
    st.markdown("**Requirement Summary**")
    with st.container(border=True):
        for cat in CATEGORY_ORDER:
            check = checks_by_category.get(cat)
            if cat == "required_skills":
                # The eligibility check only has the posting text, not the
                # candidate's actual resume -- real skill matching happens
                # on the next step, so don't let the model editorialize here.
                status = check["status"] if check else "not_mentioned"
                requirement_row(CATEGORY_LABELS[cat], status, "Skills will be evaluated against your profile on the next step.")
            elif check:
                requirement_row(CATEGORY_LABELS[cat], check["status"], check["detail"])
            else:
                requirement_row(CATEGORY_LABELS[cat], "not_mentioned", "Not addressed in this check.")
        for c in other_checks:
            requirement_row(c.get("label") or CATEGORY_LABELS["other"], c["status"], c["detail"])
else:
    st.caption('A detailed requirement summary isn\'t available for this result -- click "Re-run eligibility check" above to generate one.')

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

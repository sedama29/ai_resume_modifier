import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

import streamlit as st

import db.repository as repo
from app.state import get_db, render_user_badge, require_user, set_active_application_id
from jd.extract import extract_main_text
from jd.fetch import fetch_job_description
from llm.job_analysis import analyze_job_description


from app.styling import inject_custom_css, page_header, progress_stepper
inject_custom_css()

db = get_db()
user = require_user()
render_user_badge(user)

page_header("Start a New Application", "Add a job posting and we'll evaluate the opportunity before modifying your resume.")
progress_stepper("job_input")

master_resume = repo.get_master_resume(db, user["uid"])
if master_resume is None:
    st.warning("Upload a master resume on the Profile page first.")
    if st.button("Go to Profile"):
        st.switch_page("Profile.py")
    st.stop()


def _analyze_and_advance(jd_text: str, jd_source: str, job_url: str | None) -> None:
    with st.spinner("Analyzing job description..."):
        try:
            analysis = analyze_job_description(jd_text, db, user["uid"])
        except Exception as e:
            st.error(f"Job analysis failed: {e}")
            return

    application_id = repo.create_job_application(
        db,
        user["uid"],
        jd_text=jd_text,
        jd_source=jd_source,
        job_url=job_url,
        company=analysis.get("company"),
        job_title=analysis.get("job_title"),
    )
    repo.save_job_analysis_result(db, user["uid"], application_id, analysis)
    repo.update_job_application_status(db, user["uid"], application_id, "analyzed")
    set_active_application_id(application_id)
    st.success(f"Analyzed: {analysis.get('company')} — {analysis.get('job_title')}")
    st.switch_page("pages/2_Eligibility.py")


st.markdown("**How would you like to provide the job?**")
tab_paste, tab_url = st.tabs(["Paste Description", "Job Posting URL"])

with tab_paste:
    pasted = st.text_area(
        "Paste the job description below.", key="paste_input", height=220,
    )
    if st.button("Analyze Job", type="primary", disabled=not pasted.strip(), key="analyze_pasted"):
        _analyze_and_advance(pasted, "pasted", None)

with tab_url:
    job_url = st.text_input(
        "Job posting URL", key="job_url_input", placeholder="https://...",
    )
    if st.button("Fetch & Analyze Job", type="primary", disabled=not job_url, key="fetch_analyze"):
        with st.spinner("Fetching job posting..."):
            try:
                html = fetch_job_description(job_url)
                extracted = extract_main_text(html)
            except Exception as e:
                st.error(f"Couldn't fetch that URL: {e}. Try the Paste Description tab instead.")
                extracted = None
        if extracted:
            _analyze_and_advance(extracted, "url", job_url)
        else:
            st.warning("Couldn't cleanly extract the posting text -- use the Paste Description tab instead.")

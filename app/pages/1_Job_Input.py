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

st.markdown("**How would you like to provide the job?**")
tab_paste, tab_url = st.tabs(["Paste Description", "Job Posting URL"])

job_url = None
jd_source = st.session_state.get("jd_source", "pasted")

with tab_paste:
    st.caption("Paste the full job posting text below.")
    pasted = st.text_area("Paste text", key="paste_input", label_visibility="collapsed", height=180)
    if pasted:
        st.session_state["jd_text_draft"] = pasted
        jd_source = "pasted"

with tab_url:
    st.caption("Enter a link and we'll try to extract the posting text.")
    job_url = st.text_input("Job posting URL", key="job_url_input", label_visibility="collapsed", placeholder="https://...")
    if st.button("Fetch job description") and job_url:
        try:
            html = fetch_job_description(job_url)
            extracted = extract_main_text(html)
        except Exception as e:
            st.error(f"Couldn't fetch that URL: {e}. Paste the job description text in the other tab instead.")
            extracted = None
        if extracted:
            st.session_state["jd_text_draft"] = extracted
            jd_source = "url"
        else:
            st.warning("Couldn't cleanly extract the posting text -- use the Paste tab instead.")

st.session_state["jd_source"] = jd_source

st.write("")
jd_text = st.text_area(
    "Job description text (edit as needed)",
    value=st.session_state.get("jd_text_draft", jd_text),
    height=300,
    key="jd_text_area",
)

if st.button("Analyze Job", type="primary", disabled=not jd_text.strip()):
    with st.spinner("Analyzing job description..."):
        try:
            analysis = analyze_job_description(jd_text, db, user["uid"])
        except Exception as e:
            st.error(f"Job analysis failed: {e}")
            st.stop()

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
    st.session_state.pop("jd_text_draft", None)
    st.success(f"Analyzed: {analysis.get('company')} — {analysis.get('job_title')}")
    st.switch_page("pages/2_Eligibility.py")

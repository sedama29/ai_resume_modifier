import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

import streamlit as st

import db.repository as repo
from app.state import get_db, render_user_badge, require_user, set_active_application_id
from jd.extract import extract_main_text
from jd.fetch import fetch_job_description
from llm.job_analysis import analyze_job_description

st.set_page_config(page_title="Job Input", layout="wide")

from app.styling import inject_custom_css, page_header, progress_stepper
inject_custom_css()

db = get_db()
user = require_user()
render_user_badge(user)

page_header("Job Input", "Paste a posting or link to it -- we'll analyze it before touching your resume.")
progress_stepper("job_input")

master_resume = repo.get_master_resume(db, user["uid"])
if master_resume is None:
    st.warning("Upload a master resume on the Profile page first.")
    if st.button("Go to Profile"):
        st.switch_page("Profile.py")
    st.stop()

source = st.radio("How do you want to provide the job description?", ["Paste text", "Job URL"])

jd_text = st.session_state.get("jd_text_draft", "")
jd_source = "pasted"
job_url = None

if source == "Job URL":
    job_url = st.text_input("Job posting URL")
    if st.button("Fetch job description") and job_url:
        try:
            html = fetch_job_description(job_url)
            extracted = extract_main_text(html)
        except Exception as e:
            st.error(f"Couldn't fetch that URL: {e}. Paste the job description text below instead.")
            extracted = None
        if extracted:
            st.session_state["jd_text_draft"] = extracted
            jd_text = extracted
        else:
            st.warning("Couldn't cleanly extract the posting text -- paste it manually below.")
    jd_source = "url"

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

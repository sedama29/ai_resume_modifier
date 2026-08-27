import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

import streamlit as st

import db.repository as repo
from app.state import get_db, render_user_badge, require_active_application_id, require_user
from core.resume_model import ContentModel
from llm.skill_match import match_resume_to_job

st.set_page_config(page_title="Match Summary", page_icon="📊", layout="wide")

from app.styling import inject_custom_css
inject_custom_css()

db = get_db()
user = require_user()
render_user_badge(user)

st.title("Match Summary")

application_id = require_active_application_id(db, user["uid"])
application = repo.get_job_application(db, user["uid"], application_id)
job_analysis = repo.get_latest_job_analysis(db, user["uid"], application_id)
master_resume = repo.get_master_resume(db, user["uid"])

if job_analysis is None or master_resume is None:
    st.error("Missing job analysis or master resume. Go back and complete earlier steps.")
    st.stop()

match = repo.get_latest_match_result(db, user["uid"], application_id)

if match is None or st.button("Re-run match analysis"):
    content_model = ContentModel.model_validate(master_resume["content_model"])
    candidate_profile = repo.get_candidate_profile(db, user["uid"]) or {}
    with st.spinner("Comparing your resume against this job..."):
        try:
            match = match_resume_to_job(content_model, job_analysis, candidate_profile, db, user["uid"])
        except Exception as e:
            st.error(f"Match analysis failed: {e}")
            st.stop()
    repo.save_match_result(db, user["uid"], application_id, match)
    repo.update_job_application_status(db, user["uid"], application_id, "matched")

present = match.get("present") or []
missing = match.get("missing") or []
implied = match.get("potentially_implied") or []

st.metric("Overall Match", f"{match['match_score']:.0f}%" if match.get("match_score") is not None else "N/A")
st.caption("This score is only an estimate.")

col1, col2 = st.columns(2)
with col1:
    st.write("**✅ Present on your resume**")
    for p in present:
        st.write(f"- {p['skill']}" + (f" — _{p.get('evidence', '')}_" if p.get("evidence") else ""))
with col2:
    st.write("**❌ Missing**")
    for m in missing:
        st.write(f"- {m['skill']} ({m.get('importance', 'unspecified')})")

if implied:
    st.write("**❓ Potentially implied — needs your confirmation**")
    for i in implied:
        st.write(f"- {i['skill']}: _{i.get('reasoning', '')}_")

if st.button("Continue to Follow-up Questions →", type="primary"):
    st.switch_page("pages/4_Followup_Questions.py")

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

import streamlit as st

import db.repository as repo
from app.state import get_db, render_user_badge, require_active_application_id, require_user
from core.evidence import TIER_LABELS, build_evidence_rows
from core.resume_model import ContentModel
from llm.skill_match import match_resume_to_job


from app.styling import inject_custom_css, page_header, progress_stepper, status_badge
inject_custom_css()

db = get_db()
user = require_user()
render_user_badge(user)

page_header("Match Summary")
progress_stepper("match")

application_id = require_active_application_id(db, user["uid"])
application = repo.get_job_application(db, user["uid"], application_id)
job_analysis = repo.get_latest_job_analysis(db, user["uid"], application_id)
master_resume = repo.get_master_resume(db, user["uid"])
eligibility = repo.get_latest_eligibility_result(db, user["uid"], application_id)

if job_analysis is None or master_resume is None:
    st.error("Missing job analysis or master resume. Go back and complete earlier steps.")
    st.stop()

match = repo.get_latest_match_result(db, user["uid"], application_id)
candidate_profile = repo.get_candidate_profile(db, user["uid"]) or {}

if match is None or st.button("Re-run match analysis"):
    content_model = ContentModel.model_validate(master_resume["content_model"])
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
present_names = {p["skill"] for p in present}
required_skills = job_analysis.get("required_skills") or []
preferred_skills = job_analysis.get("preferred_skills") or []
required_hit = sum(1 for s in required_skills if s in present_names)
preferred_hit = sum(1 for s in preferred_skills if s in present_names)

score = match.get("match_score")
with st.container(border=True):
    st.markdown(
        f'<div style="font-size:2.4rem;font-weight:700;color:#18181B;line-height:1;">'
        f'{f"{score:.0f}%" if score is not None else "N/A"}</div>'
        '<div style="color:#71717A;font-size:0.9rem;margin-top:2px;">Overall match (estimate only)</div>',
        unsafe_allow_html=True,
    )
    st.write("")
    c1, c2, c3 = st.columns(3)
    c1.metric("Required skills", f"{required_hit}/{len(required_skills)}" if required_skills else "—")
    c2.metric("Preferred skills", f"{preferred_hit}/{len(preferred_skills)}" if preferred_skills else "—")
    c3.metric("Education", (eligibility or {}).get("education_match", "—").title())

st.write("")
col1, col2 = st.columns(2)
with col1:
    st.markdown("**Strong Matches**")
    if present:
        for p in present:
            st.write(f"✓ {p['skill']}" + (f" — _{p.get('evidence', '')}_" if p.get("evidence") else ""))
    else:
        st.caption("None identified.")
with col2:
    st.markdown("**Missing / Needs Confirmation**")
    if missing:
        for m in missing:
            st.write(f"○ {m['skill']} ({m.get('importance', 'unspecified')})")
    else:
        st.caption("Nothing missing.")

if implied:
    st.write("")
    st.markdown("**Potentially matching — not currently listed on your resume**")
    for i in implied:
        st.write(f"! {i['skill']}: _{i.get('reasoning', '')}_")

evidence_rows = build_evidence_rows(job_analysis, match, candidate_profile)
if evidence_rows:
    st.write("")
    st.markdown("**Evidence Hierarchy**")
    st.caption(
        "Combines your master resume with confirmed GitHub/learning experience and unconfirmed "
        "discoveries -- nothing here is added to your resume until you confirm it on the next step."
    )
    _TIER_TONE = {
        "professional": "green", "research": "green", "project": "green", "academic": "green",
        "github_project": "yellow", "coursework": "yellow", "none": "gray",
    }
    header = st.columns([3, 3, 1.6, 2.2])
    header[0].caption("TECHNOLOGY")
    header[1].caption("FOUND IN")
    header[2].caption("IMPORTANCE")
    header[3].caption("STATUS")
    for row in evidence_rows:
        cols = st.columns([3, 3, 1.6, 2.2], vertical_alignment="center")
        cols[0].write(row.skill)
        cols[1].write(row.found_in)
        cols[2].write(row.importance.title())
        label = TIER_LABELS.get(row.tier, row.tier)
        if not row.confirmed and row.tier != "none":
            label += " (unconfirmed)"
        cols[3].markdown(status_badge(label, _TIER_TONE.get(row.tier, "gray")), unsafe_allow_html=True)

st.write("")
if st.button("Continue to Follow-up Questions →", type="primary"):
    st.switch_page("pages/4_Followup_Questions.py")

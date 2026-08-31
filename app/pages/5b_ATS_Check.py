import sys
import tempfile
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

import streamlit as st

import db.repository as repo
from app.auth import storage_client
from app.state import get_db, render_user_badge, require_active_application_id, require_user
from core.ats_check import run_ats_check
from core.evidence import TIER_LABELS
from core.parser import parse_master_tex_from_string
from core.renderer import render_tex
from core.resume_model import ContentModel, SkillLine
from latex.compiler import compile_tex


from app.styling import ats_category_row, inject_custom_css, page_header, progress_stepper, status_card
inject_custom_css()

db = get_db()
user = require_user()
render_user_badge(user)

page_header(
    "ATS Compatibility Check",
    "A quick, honest read on how well your customized resume is likely to parse -- not a guarantee of any "
    "specific applicant tracking system's result.",
)
progress_stepper("ats_check")

application_id = require_active_application_id(db, user["uid"])
master_resume = repo.get_master_resume(db, user["uid"])
job_analysis = repo.get_latest_job_analysis(db, user["uid"], application_id)
match_result = repo.get_latest_match_result(db, user["uid"], application_id) or {}
candidate_profile = repo.get_candidate_profile(db, user["uid"]) or {}

if master_resume is None or job_analysis is None:
    st.error("Missing master resume or job analysis.")
    st.stop()

final_content_model = st.session_state.get(f"final_content_model_{application_id}")
if final_content_model is None:
    review_state = st.session_state.get(f"review_{application_id}")
    if review_state:
        final_content_model = review_state["merged"]
    else:
        final_content_model = ContentModel.model_validate(master_resume["content_model"])
        st.warning("No reviewed changes found -- checking the unmodified master resume.")

# A PREVIEW compile only -- never saved as a resume version (that's what
# Generate does, later). This lets the check run against the actual
# rendered document, not just the LaTeX source, without touching Storage
# or creating a resume_versions entry before the user has even seen it.
compile_cache_key = f"ats_compile_{application_id}"
if compile_cache_key not in st.session_state or st.button("Re-run ATS check"):
    master_tex_text = storage_client.download_text(master_resume["source_storage_path"])
    parsed_master = parse_master_tex_from_string(master_tex_text)
    tex_content = render_tex(parsed_master, final_content_model)
    with st.spinner("Compiling a preview and running the ATS check..."):
        with tempfile.TemporaryDirectory() as scratch:
            result = compile_tex(tex_content, Path(scratch) / "_ats_preview")
            pdf_bytes = Path(result.pdf_path).read_bytes() if result.success else None
    st.session_state[compile_cache_key] = {
        "tex_content": tex_content, "pdf_bytes": pdf_bytes,
        "compile_success": result.success, "compile_log": result.log_text or result.error_summary,
    }

cached = st.session_state[compile_cache_key]

if not cached["compile_success"]:
    st.error("The customized resume couldn't be compiled to a PDF for this check -- see the log below.")
    with st.expander("Compile log"):
        st.code(cached["compile_log"] or "(no log captured)")
    st.caption("The checks below still run against the LaTeX source where possible.")

confirmed_followup_skills = {
    q["related_skill"].strip().lower()
    for q in repo.list_followup_questions(db, user["uid"], application_id)
    if q.get("answer_bool") is True and q.get("related_skill")
}
ats = run_ats_check(
    cached["tex_content"], cached["pdf_bytes"], final_content_model,
    job_analysis, match_result, candidate_profile, confirmed_followup_skills,
)

TONE_LABELS = {"green": "🟢 Good", "yellow": "🟡 Needs Improvement", "red": "🔴 Potential Issues"}
status_card(
    TONE_LABELS.get(ats.overall_tone, "⚪ Not Checked"),
    "This is a heuristic check based on this app's own analysis -- different ATS systems behave "
    "differently, and this is not a guarantee your resume will pass any specific one.",
    ats.overall_tone,
)

st.write("")
st.markdown("**ATS Compatibility Summary**")
with st.container(border=True):
    for c in ats.categories:
        ats_category_row(c.label, c.tone, c.summary)

if ats.issues:
    st.write("")
    st.markdown("**Potential Issues**")
    with st.container(border=True):
        for issue in ats.issues:
            st.write(f"• {issue.message}")

if ats.safe_improvements:
    st.write("")
    st.markdown("**Safe Improvements**")
    st.caption("Each of these is already confirmed experience -- applying one only adds it to Skills, phrased plainly.")
    for imp in ats.safe_improvements:
        with st.container(border=True):
            col1, col2 = st.columns([3, 1], vertical_alignment="center")
            with col1:
                st.markdown(f'**Add:** "{imp.skill}"')
                st.caption(f"Evidence: {TIER_LABELS.get(imp.tier, imp.tier)} — {imp.evidence}")
            with col2:
                if st.button("Apply Safe Improvement", key=f"apply_{imp.skill}", use_container_width=True):
                    final_content_model.skills.append(
                        SkillLine(
                            item_id=f"ats_{uuid.uuid4().hex[:8]}",
                            text=f"Experience with {imp.skill}.",
                            change="added",
                            source_answer_id=f"ats_confirmed:{imp.skill}",
                        )
                    )
                    st.session_state[f"final_content_model_{application_id}"] = final_content_model
                    st.session_state.pop(compile_cache_key, None)  # force a fresh recompile + recheck
                    st.success(f'Added "{imp.skill}" to Skills.')
                    st.rerun()

with st.expander("Details"):
    st.write(f"**Overall tone:** {ats.overall_tone}")
    st.write("**Extracted PDF text** (first 3000 characters):")
    st.code(ats.extracted_text[:3000] or "(no text extracted)")

st.write("")
if st.button("Continue to Generate →", type="primary"):
    st.switch_page("pages/6_Generate.py")

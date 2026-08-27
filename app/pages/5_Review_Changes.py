import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

import streamlit as st

import db.repository as repo
from app.state import get_db, render_user_badge, require_active_application_id, require_user
from core.diff import compute_diff
from core.resume_model import Bullet, ContentModel, SkillLine
from core.validators import validate_and_merge
from llm.resume_rewrite import rewrite_resume

st.set_page_config(page_title="Review Changes", layout="wide")

from app.styling import inject_custom_css, page_header, progress_stepper
inject_custom_css()


def _split_ref(ref: str):
    entry_id, item_id = ref.split(":", 1)
    return entry_id, item_id


def _revert_text(cm: ContentModel, ref: str, original_text: str):
    entry_id, item_id = _split_ref(ref)
    if entry_id == "skills":
        for s in cm.skills:
            if s.item_id == item_id:
                s.text = original_text
        return
    for e in cm.experience:
        if e.entry_id == entry_id:
            for b in e.bullets:
                if b.bullet_id == item_id:
                    b.text = original_text


def _remove_item(cm: ContentModel, ref: str):
    entry_id, item_id = _split_ref(ref)
    if entry_id == "skills":
        cm.skills = [s for s in cm.skills if s.item_id != item_id]
        return
    for e in cm.experience:
        if e.entry_id == entry_id:
            e.bullets = [b for b in e.bullets if b.bullet_id != item_id]


def _restore_item(cm: ContentModel, ref: str, original_item):
    entry_id, item_id = _split_ref(ref)
    if entry_id == "skills":
        if not any(s.item_id == item_id for s in cm.skills):
            cm.skills.append(SkillLine(item_id=item_id, text=original_item.text))
        return
    for e in cm.experience:
        if e.entry_id == entry_id:
            if not any(b.bullet_id == item_id for b in e.bullets):
                e.bullets.append(Bullet(bullet_id=item_id, text=original_item.text))


db = get_db()
user = require_user()
render_user_badge(user)
page_header("Review Changes")
progress_stepper("review")

application_id = require_active_application_id(db, user["uid"])
master_resume = repo.get_master_resume(db, user["uid"])
job_analysis = repo.get_latest_job_analysis(db, user["uid"], application_id)

if master_resume is None or job_analysis is None:
    st.error("Missing master resume or job analysis.")
    st.stop()

original = ContentModel.model_validate(master_resume["content_model"])
session_key = f"review_{application_id}"

if session_key not in st.session_state or st.button("Regenerate proposed changes"):
    confirmed_answers = repo.list_confirmed_answers_with_question_text(db, user["uid"], application_id)
    confirmed_answer_ids = {a["question_id"] for a in confirmed_answers}
    candidate_profile = repo.get_candidate_profile(db, user["uid"]) or {}

    with st.spinner("Generating tailored content..."):
        try:
            llm_output = rewrite_resume(original, job_analysis, confirmed_answers, candidate_profile, db, user["uid"])
        except Exception as e:
            st.error(f"Resume rewrite failed: {e}")
            st.stop()

    merged, warnings = validate_and_merge(original, llm_output, confirmed_answer_ids)
    diff = compute_diff(original, merged)
    st.session_state[session_key] = {"merged": merged, "diff": diff, "warnings": warnings}

state = st.session_state[session_key]
merged: ContentModel = state["merged"]
diff = state["diff"]
warnings = state["warnings"]

warnings_by_ref = {}
for w in warnings:
    warnings_by_ref.setdefault(w.ref, []).append(w)

if diff.reordered_sections:
    st.info(f"Reordered: {', '.join(diff.reordered_sections)}")

if not diff.changes:
    st.success("No content changes proposed.")
else:
    decisions = {}  # ref -> bool accept
    for change in diff.changes:
        item_warnings = warnings_by_ref.get(change.ref, [])
        has_fidelity_flag = any(w.kind in ("numeric_mismatch", "unverified_new_term") for w in item_warnings)
        default = not has_fidelity_flag  # numeric/new-term-flagged items default to unaccepted

        if change.change_type == "added":
            label = f"**Added** ({change.ref}): {change.new_text}"
        elif change.change_type == "reworded":
            label = f"**Reworded** ({change.ref})"
        else:  # removed
            label = f"**Remove** ({change.ref}): {change.old_text}"
            default = False  # default to keeping the original content

        with st.container(border=True):
            st.markdown(label)
            if change.change_type == "reworded":
                st.write("Was:", change.old_text)
                st.write("Now:", change.new_text)
            for w in item_warnings:
                st.markdown(f":red[{w.message}]")
            accept_label = "Remove this bullet" if change.change_type == "removed" else "Accept this change"
            decisions[change.ref] = st.checkbox(accept_label, value=default, key=f"decision_{change.ref}")

    not_added = [w for w in warnings if w.kind in ("missing_source_answer", "unknown_id")]
    if not_added:
        with st.expander("Not added (discarded automatically)"):
            for w in not_added:
                st.write(f"- {w.ref}: {w.message}")

    if st.button("Approve & Continue →", type="primary"):
        final = merged.model_copy(deep=True)
        original_bullets_by_ref = {
            f"{e.entry_id}:{b.bullet_id}": b for e in original.experience for b in e.bullets
        }
        original_skills_by_ref = {f"skills:{s.item_id}": s for s in original.skills}

        for change in diff.changes:
            accepted = decisions.get(change.ref, True)
            if change.change_type == "reworded" and not accepted:
                orig = original_bullets_by_ref.get(change.ref) or original_skills_by_ref.get(change.ref)
                if orig:
                    _revert_text(final, change.ref, orig.text)
            elif change.change_type == "added" and not accepted:
                _remove_item(final, change.ref)
            elif change.change_type == "removed" and not accepted:
                orig = original_bullets_by_ref.get(change.ref) or original_skills_by_ref.get(change.ref)
                if orig:
                    _restore_item(final, change.ref, orig)

        st.session_state[f"final_content_model_{application_id}"] = final
        repo.update_job_application_status(db, user["uid"], application_id, "reviewed")
        st.switch_page("pages/6_Generate.py")

import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

import streamlit as st

import db.repository as repo
from app.state import get_db, render_user_badge, require_active_application_id, require_user
from core.evidence import build_evidence_rows, unconfirmed_discoveries
from llm.followup_questions import generate_followup_questions


from app.styling import inject_custom_css, page_header, progress_stepper
inject_custom_css()

db = get_db()
user = require_user()
render_user_badge(user)

page_header(
    "A few quick questions",
    "Your resume may not mention every technology you've actually used -- answer honestly, "
    "only confirmed 'Yes' answers can ever be added.",
)
progress_stepper("questions")

application_id = require_active_application_id(db, user["uid"])
match = repo.get_latest_match_result(db, user["uid"], application_id)
if match is None:
    st.error("No match result found. Go back to Match Summary first.")
    st.stop()

questions = repo.list_followup_questions(db, user["uid"], application_id)
if not questions:
    with st.spinner("Generating targeted questions..."):
        match_for_questions = {
            "missing": match.get("missing") or [],
            "potentially_implied": match.get("potentially_implied") or [],
        }
        try:
            result = generate_followup_questions(match_for_questions, db, user["uid"])
        except Exception as e:
            st.error(f"Couldn't generate follow-up questions: {e}")
            st.stop()
    if result.get("questions"):
        repo.save_followup_questions(db, user["uid"], application_id, result["questions"])
        questions = repo.list_followup_questions(db, user["uid"], application_id)
    else:
        st.success("No follow-up questions needed -- your resume already covers this job's key skills.")

WHERE_OPTIONS = ["Work", "Research", "Academic project", "Personal project", "Internship", "Other"]

idx_key = f"followup_idx_{application_id}"
answers_key = f"followup_answers_{application_id}"
ev_idx_key = f"evidence_idx_{application_id}"
phase1_done_key = f"followup_phase1_done_{application_id}"

phase1_total = len(questions)
phase1_done = st.session_state.get(phase1_done_key, False)
if phase1_total and not phase1_done:
    st.session_state.setdefault(idx_key, 0)
    st.session_state.setdefault(answers_key, {})
phase1_idx = st.session_state.get(idx_key, phase1_total) if not phase1_done else phase1_total

# --- Phase 1: the LLM-generated missing/implied-skill questions --------------
if phase1_idx < phase1_total:
    q = questions[phase1_idx]
    st.caption(f"Question {phase1_idx + 1} of {phase1_total}")
    with st.container(border=True):
        st.markdown(f"**{q['question_text']}**")
        level = st.radio(
            "Your experience level", ["Yes", "No", "Limited exposure", "Not sure"],
            key=f"level_{q['question_id']}_{phase1_idx}", label_visibility="collapsed",
        )
        detail = None
        if level in ("Yes", "Limited exposure"):
            where = st.selectbox("Where did you use it?", WHERE_OPTIONS, key=f"where_{q['question_id']}_{phase1_idx}")
            what_for = st.text_input("What did you use it for?", key=f"what_{q['question_id']}_{phase1_idx}")
            prefix = "(Limited exposure) " if level == "Limited exposure" else ""
            detail = f"{prefix}{where}: {what_for}".strip() or None

        st.write("")
        _, btn_col = st.columns([3, 1])
        with btn_col:
            label = "Finish →" if phase1_idx == phase1_total - 1 else "Continue →"
            if st.button(label, type="primary", use_container_width=True, key=f"next_{phase1_idx}"):
                st.session_state[answers_key][q["question_id"]] = (level in ("Yes", "Limited exposure"), detail)
                st.session_state[idx_key] += 1
                st.rerun()
    st.stop()

# Phase 1 -> phase 2 transition, runs exactly once, gated on phase1_done_key
# (not on idx_key's mere presence -- that gets popped right below, and without
# a dedicated "done" flag every later phase-2 rerun would see idx_key absent
# and setdefault() it back to 0, re-entering phase 1 forever).
if phase1_total and not phase1_done:
    repo.save_followup_answers(db, user["uid"], application_id, st.session_state.get(answers_key, {}))
    st.session_state[phase1_done_key] = True
    st.session_state.pop(idx_key, None)
    st.session_state.pop(answers_key, None)

# --- Phase 2: GitHub / current-learning discoveries not already covered above ---
job_analysis = repo.get_latest_job_analysis(db, user["uid"], application_id)
candidate_profile = repo.get_candidate_profile(db, user["uid"]) or {}

# Snapshotted once per session and frozen for the rest of this wizard --
# confirming a discovery removes it from unconfirmed_discoveries() on the
# NEXT read (it becomes "confirmed"), which would otherwise shift the list
# out from under ev_idx mid-walkthrough and silently skip the next item.
discoveries_key = f"discoveries_{application_id}"
if discoveries_key not in st.session_state:
    asked_skills = {q.get("related_skill", "").strip().lower() for q in questions if q.get("related_skill")}
    snapshot = []
    if job_analysis:
        evidence_rows = build_evidence_rows(job_analysis, match, candidate_profile)
        snapshot = [r for r in unconfirmed_discoveries(evidence_rows) if r.skill.strip().lower() not in asked_skills]
    st.session_state[discoveries_key] = snapshot
discoveries = st.session_state[discoveries_key]

st.session_state.setdefault(ev_idx_key, 0)
ev_idx = st.session_state[ev_idx_key]


def _persist(tier: str, decision: str, detail_text: str | None, question_text: str, include_now: bool, row) -> None:
    existing = candidate_profile.get("confirmed_experiences") or []
    existing = existing + [
        {
            "technology": row.skill,
            "tier": tier,
            "source": "github" if row.tier == "github_project" else "learning",
            "source_detail": row.found_in,
            "evidence": row.detail.get("evidence") or detail_text or "",
            "decision": decision,
            "detail_text": detail_text,
            "confirmed_at": datetime.now(timezone.utc).isoformat(),
        }
    ]
    repo.upsert_candidate_profile(db, user["uid"], confirmed_experiences=existing)
    if include_now:
        repo.add_confirmed_followup_entry(
            db, user["uid"], application_id,
            {
                "question_id": f"evidence_{ev_idx}_{row.skill.replace(' ', '_')}",
                "question_text": question_text,
                "answer_bool": True,
                "answer_detail_text": detail_text,
                "experience_tier": tier,
            },
        )


if discoveries and ev_idx < len(discoveries):
    row = discoveries[ev_idx]
    st.caption(f"Discovered experience {ev_idx + 1} of {len(discoveries)}")

    if row.tier == "github_project":
        with st.container(border=True):
            st.markdown("**Potential GitHub experience found**")
            st.write(f"**Technology:** {row.skill}")
            st.write(f"**Repository:** {row.detail.get('repo', row.found_in)}")
            if row.detail.get("evidence"):
                st.caption(f"Evidence: {row.detail['evidence']}")

            confirm = st.radio(
                f"Have you actually worked with {row.skill} in this project?",
                ["Yes", "No", "Limited exposure", "I need to review this"],
                key=f"gh_confirm_{ev_idx}",
            )
            include_choice = None
            if confirm in ("Yes", "Limited exposure"):
                include_choice = st.radio(
                    "Would you like to include this experience in your resume?",
                    ["Yes, add to Projects", "Yes, add to Skills", "No", "Keep for future applications only"],
                    key=f"gh_include_{ev_idx}",
                )

            st.write("")
            _, btn_col = st.columns([3, 1])
            with btn_col:
                if st.button("Continue →", type="primary", use_container_width=True, key=f"gh_next_{ev_idx}"):
                    repo_label = row.detail.get("repo", row.found_in)
                    question_text = f"Have you worked with {row.skill} in the {repo_label} project?"
                    prefix = "(Limited exposure) " if confirm == "Limited exposure" else ""
                    evidence_detail = f"{prefix}Repository: {repo_label}. {row.detail.get('evidence', '')}".strip()
                    if confirm in ("Yes", "Limited exposure") and include_choice in ("Yes, add to Projects", "Yes, add to Skills"):
                        decision = "add_projects" if include_choice == "Yes, add to Projects" else "add_skills"
                        _persist("github_project", decision, evidence_detail, question_text, True, row)
                    elif confirm in ("Yes", "Limited exposure") and include_choice == "Keep for future applications only":
                        _persist("github_project", "keep_future", evidence_detail, question_text, False, row)
                    # "No" or "I need to review this" -- nothing stored, it can resurface later.
                    st.session_state[ev_idx_key] += 1
                    st.rerun()

    else:  # row.tier == "coursework"
        with st.container(border=True):
            st.markdown("**Learning experience found**")
            st.write(f"You indicated you're currently learning **{row.skill}** through {row.found_in}.")

            outside = st.radio(
                f"Have you used {row.skill} outside of the course?",
                [
                    "Yes, professionally", "Yes, in a research/work project",
                    "Yes, in a personal/GitHub project", "Only through coursework", "No",
                ],
                key=f"learn_outside_{ev_idx}",
            )

            where = what_for = None
            research_include = project_choice = coursework_choice = None

            if outside == "Yes, professionally":
                where = st.selectbox("Where did you use it?", WHERE_OPTIONS, key=f"learn_where_{ev_idx}")
                what_for = st.text_input("What did you use it for?", key=f"learn_what_{ev_idx}")
            elif outside == "Yes, in a research/work project":
                research_include = st.radio("Would you like to include this?", ["Yes", "No"], key=f"learn_research_{ev_idx}")
            elif outside == "Yes, in a personal/GitHub project":
                project_choice = st.radio(
                    "Would you like to include this project or technology in your resume?",
                    ["Add to Projects", "Add to Skills", "Keep for future applications", "Don't include"],
                    key=f"learn_project_{ev_idx}",
                )
            elif outside == "Only through coursework":
                st.info(
                    "You are currently learning this technology through your course, but we did not find "
                    "confirmed professional or project experience."
                )
                coursework_choice = st.radio(
                    "Would you like to include it in your Skills section as a technology you are "
                    "currently developing experience with?",
                    ["Yes", "No", "Keep for future applications"],
                    key=f"learn_coursework_{ev_idx}",
                )

            st.write("")
            _, btn_col = st.columns([3, 1])
            with btn_col:
                if st.button("Continue →", type="primary", use_container_width=True, key=f"learn_next_{ev_idx}"):
                    if outside == "Yes, professionally":
                        detail_text = f"{where}: {what_for}".strip(": ") or None
                        _persist(
                            "professional", "add_skills", detail_text,
                            f"Have you used {row.skill} professionally?", True, row,
                        )
                    elif outside == "Yes, in a research/work project" and research_include == "Yes":
                        _persist(
                            "research", "add_skills", f"Used in a research/work project ({row.found_in}).",
                            f"Have you used {row.skill} in a research/work project?", True, row,
                        )
                    elif outside == "Yes, in a personal/GitHub project" and project_choice in ("Add to Projects", "Add to Skills"):
                        decision = "add_projects" if project_choice == "Add to Projects" else "add_skills"
                        _persist(
                            "github_project", decision, f"Personal/GitHub project experience ({row.found_in}).",
                            f"Have you used {row.skill} in a personal/GitHub project?", True, row,
                        )
                    elif outside == "Yes, in a personal/GitHub project" and project_choice == "Keep for future applications":
                        _persist(
                            "github_project", "keep_future", f"Personal/GitHub project experience ({row.found_in}).",
                            f"Have you used {row.skill} in a personal/GitHub project?", False, row,
                        )
                    elif outside == "Only through coursework" and coursework_choice == "Yes":
                        _persist(
                            "coursework", "add_skills", f"Currently developing experience through {row.found_in}.",
                            f"Are you currently developing experience with {row.skill} through coursework?", True, row,
                        )
                    elif outside == "Only through coursework" and coursework_choice == "Keep for future applications":
                        _persist(
                            "coursework", "keep_future", f"Currently developing experience through {row.found_in}.",
                            f"Are you currently developing experience with {row.skill} through coursework?", False, row,
                        )
                    # every other combination (No / Don't include / research No) -- nothing stored.
                    st.session_state[ev_idx_key] += 1
                    st.rerun()
    st.stop()

# Both phases complete (or there was nothing to ask at all).
if phase1_total or discoveries:
    repo.update_job_application_status(db, user["uid"], application_id, "questions_pending")
    st.session_state.pop(ev_idx_key, None)
    st.session_state.pop(discoveries_key, None)
    st.session_state.pop(phase1_done_key, None)
    st.switch_page("pages/5_Review_Changes.py")
else:
    if st.button("Continue to Review Changes →", type="primary"):
        repo.update_job_application_status(db, user["uid"], application_id, "questions_pending")
        st.switch_page("pages/5_Review_Changes.py")

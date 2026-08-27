import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

import streamlit as st

import db.repository as repo
from app.state import get_db, render_user_badge, require_active_application_id, require_user
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

if questions:
    idx_key = f"followup_idx_{application_id}"
    answers_key = f"followup_answers_{application_id}"
    st.session_state.setdefault(idx_key, 0)
    st.session_state.setdefault(answers_key, {})

    idx = st.session_state[idx_key]
    total = len(questions)

    if idx >= total:
        # Every question answered -- persist the whole batch in one write and move on.
        repo.save_followup_answers(db, user["uid"], application_id, st.session_state[answers_key])
        repo.update_job_application_status(db, user["uid"], application_id, "questions_pending")
        st.session_state.pop(idx_key, None)
        st.session_state.pop(answers_key, None)
        st.switch_page("pages/5_Review_Changes.py")

    q = questions[idx]
    st.caption(f"Question {idx + 1} of {total}")
    with st.container(border=True):
        st.markdown(f"**{q['question_text']}**")
        level = st.radio(
            "Your experience level", ["Yes", "Limited exposure", "No", "Not sure"],
            key=f"level_{q['question_id']}_{idx}", label_visibility="collapsed",
        )
        detail = None
        if level in ("Yes", "Limited exposure"):
            where = st.selectbox("Where did you use it?", WHERE_OPTIONS, key=f"where_{q['question_id']}_{idx}")
            what_for = st.text_input("What did you use it for?", key=f"what_{q['question_id']}_{idx}")
            prefix = "(Limited exposure) " if level == "Limited exposure" else ""
            detail = f"{prefix}{where}: {what_for}".strip() or None

        st.write("")
        _, btn_col = st.columns([3, 1])
        with btn_col:
            label = "Finish →" if idx == total - 1 else "Continue →"
            if st.button(label, type="primary", use_container_width=True, key=f"next_{idx}"):
                st.session_state[answers_key][q["question_id"]] = (level in ("Yes", "Limited exposure"), detail)
                st.session_state[idx_key] += 1
                st.rerun()
else:
    if st.button("Continue to Review Changes →", type="primary"):
        st.switch_page("pages/5_Review_Changes.py")

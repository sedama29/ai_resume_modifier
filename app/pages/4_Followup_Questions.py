import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

import streamlit as st

import db.repository as repo
from app.state import get_db, render_user_badge, require_active_application_id, require_user
from llm.followup_questions import generate_followup_questions

st.set_page_config(page_title="Follow-up Questions", page_icon="❓", layout="wide")

from app.styling import inject_custom_css, page_header, progress_stepper
inject_custom_css()

db = get_db()
user = require_user()
render_user_badge(user)

page_header(
    "❓", "Follow-up Questions",
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
    with st.form("followup_form"):
        answers = {}
        for q in questions:
            st.write(f"**{q['question_text']}**")
            level = st.radio(
                "Your experience level", ["No", "Not sure", "Limited exposure", "Yes"],
                key=f"level_{q['question_id']}", horizontal=True, label_visibility="collapsed",
            )
            detail = ""
            if level in ("Yes", "Limited exposure"):
                where = st.selectbox("Where did you use it?", WHERE_OPTIONS, key=f"where_{q['question_id']}")
                what_for = st.text_input("What did you use it for?", key=f"what_{q['question_id']}")
                prefix = "(Limited exposure) " if level == "Limited exposure" else ""
                detail = f"{prefix}{where}: {what_for}".strip()
            answers[q["question_id"]] = (level in ("Yes", "Limited exposure"), detail or None)
            st.divider()

        if st.form_submit_button("Submit Answers", type="primary"):
            # One read + one write for the whole batch, not one write per question.
            repo.save_followup_answers(db, user["uid"], application_id, answers)
            repo.update_job_application_status(db, user["uid"], application_id, "questions_pending")
            st.switch_page("pages/5_Review_Changes.py")
else:
    if st.button("Continue to Review Changes →", type="primary"):
        st.switch_page("pages/5_Review_Changes.py")

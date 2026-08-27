import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

import streamlit as st

import db.repository as repo
from app.state import get_db, render_user_badge, require_active_application_id, require_user
from llm.followup_questions import generate_followup_questions

st.set_page_config(page_title="Follow-up Questions", page_icon="❓", layout="wide")

conn = get_db()
user = require_user()
render_user_badge(user)

st.title("Follow-up Questions")
st.caption(
    "Your resume may not mention every technology you've actually used. "
    "Answer honestly -- only confirmed 'Yes' answers can ever be added to your resume."
)

application_id = require_active_application_id(conn, user["uid"])
match_row = repo.get_latest_match_result(conn, application_id)
if match_row is None:
    st.error("No match result found. Go back to Match Summary first.")
    st.stop()

questions = repo.list_followup_questions(conn, application_id)
if not questions:
    with st.spinner("Generating targeted questions..."):
        import json

        match = {
            "missing": json.loads(match_row["skills_missing_json"] or "[]"),
            "potentially_implied": json.loads(match_row["skills_implied_json"] or "[]"),
        }
        try:
            result = generate_followup_questions(match, conn, user["uid"])
        except Exception as e:
            st.error(f"Couldn't generate follow-up questions: {e}")
            st.stop()
    if result.get("questions"):
        repo.save_followup_questions(conn, application_id, result["questions"])
        questions = repo.list_followup_questions(conn, application_id)
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
                key=f"level_{q['id']}", horizontal=True, label_visibility="collapsed",
            )
            detail = ""
            if level in ("Yes", "Limited exposure"):
                where = st.selectbox("Where did you use it?", WHERE_OPTIONS, key=f"where_{q['id']}")
                what_for = st.text_input("What did you use it for?", key=f"what_{q['id']}")
                prefix = "(Limited exposure) " if level == "Limited exposure" else ""
                detail = f"{prefix}{where}: {what_for}".strip()
            answers[q["id"]] = (level in ("Yes", "Limited exposure"), detail)
            st.divider()

        if st.form_submit_button("Submit Answers", type="primary"):
            for question_id, (confirmed, detail) in answers.items():
                repo.save_followup_answer(conn, question_id, application_id, confirmed, detail or None)
            repo.update_job_application_status(conn, application_id, "questions_pending")
            st.switch_page("pages/5_Review_Changes.py")
else:
    if st.button("Continue to Review Changes →", type="primary"):
        st.switch_page("pages/5_Review_Changes.py")

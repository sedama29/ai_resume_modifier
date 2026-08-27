import hashlib
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import streamlit as st

import db.repository as repo
from app.state import get_db, render_user_badge, require_user
from config import MASTER_RESUME_PATH, STORAGE_DIR
from core.parser import extract_header_fields, parse_master_tex

st.set_page_config(page_title="AI Resume Modifier", page_icon="📄", layout="wide")

from app.styling import inject_custom_css
inject_custom_css()

conn = get_db()
user = require_user()
render_user_badge(user)

st.title("AI Resume Modifier")
st.caption(
    "Job description → Eligibility check → Experience questions → Resume "
    "customization → Review → PDF → Application history."
)

st.header("1. Master Resume")
active = repo.get_active_master_resume_version(conn, user["uid"])

uploaded = st.file_uploader("Upload your master resume (.tex)", type=["tex"])
use_default = st.button("Use existing file at Resources/main.tex", disabled=not Path(MASTER_RESUME_PATH).exists())

resume_path_to_parse = None
if uploaded is not None:
    # Per-user destination -- MASTER_RESUME_PATH is a shared seed template,
    # never a per-user upload target (two users uploading would otherwise
    # silently overwrite the same file on disk).
    dest = STORAGE_DIR / "masters" / user["uid"] / "main.tex"
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_bytes(uploaded.getvalue())
    resume_path_to_parse = str(dest)
elif use_default:
    resume_path_to_parse = MASTER_RESUME_PATH

if resume_path_to_parse:
    try:
        parsed = parse_master_tex(resume_path_to_parse)
    except Exception as e:
        st.error(f"Couldn't parse this resume: {e}")
    else:
        skeleton_hash = hashlib.sha256(parsed.original_text.encode()).hexdigest()
        repo.create_master_resume_version(conn, user["uid"], resume_path_to_parse, parsed.content_model, skeleton_hash)
        st.success("Master resume parsed and saved as the active version.")

        header_fields = extract_header_fields(parsed.original_text)
        existing_profile = repo.get_candidate_profile(conn, user["uid"]) or {}
        repo.upsert_candidate_profile(
            conn,
            user["uid"],
            name=existing_profile.get("name") or header_fields.get("name"),
            phone=existing_profile.get("phone") or header_fields.get("phone"),
            email=existing_profile.get("email") or header_fields.get("email") or user["email"],
            github=existing_profile.get("github") or header_fields.get("github"),
            location=existing_profile.get("location") or header_fields.get("location"),
            years_experience=existing_profile.get("years_experience"),
            education_summary=existing_profile.get("education_summary"),
            visa_status_text=existing_profile.get("visa_status_text"),
        )
        active = repo.get_active_master_resume_version(conn, user["uid"])

if active:
    from core.resume_model import ContentModel

    cm = ContentModel.model_validate_json(active["content_model_json"])
    with st.expander("Preview parsed content", expanded=False):
        st.write("**Summary**")
        st.write(cm.summary.text)
        st.write("**Experience**")
        for e in cm.experience:
            st.write(f"- {e.org_label} ({len(e.bullets)} bullets)")
        st.write("**Skills**")
        for s in cm.skills:
            st.write(f"- {s.text}")
else:
    st.info("Upload your master resume .tex to get started.")

st.header("2. Candidate Profile")
st.caption("Used to give the LLM accurate context for eligibility and matching. Edit freely.")
profile = repo.get_candidate_profile(conn, user["uid"]) or {}

with st.form("profile_form"):
    name = st.text_input("Name", value=profile.get("name") or "")
    phone = st.text_input("Phone", value=profile.get("phone") or "")
    email = st.text_input("Email", value=profile.get("email") or user["email"])
    github = st.text_input("GitHub", value=profile.get("github") or "")
    location = st.text_input("Location", value=profile.get("location") or "")
    years_experience = st.number_input(
        "Approximate years of professional experience", min_value=0.0, step=0.5,
        value=float(profile.get("years_experience") or 0),
    )
    education_summary = st.text_area(
        "Education summary", value=profile.get("education_summary") or "",
        placeholder="e.g. M.S. Computer Science, Texas A&M University-Corpus Christi",
    )
    visa_status_text = st.text_area(
        "Work authorization status", value=profile.get("visa_status_text") or "",
        placeholder="e.g. H-1B, sponsored by a nonprofit research institute",
    )
    if st.form_submit_button("Save profile"):
        repo.upsert_candidate_profile(
            conn, user["uid"], name=name, phone=phone, email=email, github=github, location=location,
            years_experience=years_experience, education_summary=education_summary,
            visa_status_text=visa_status_text,
        )
        st.success("Profile saved.")

st.header("3. Start a New Application")
if st.button("Go to Job Input →", disabled=active is None):
    st.switch_page("pages/1_Job_Input.py")

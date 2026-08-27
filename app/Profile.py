import hashlib
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import streamlit as st

import db.repository as repo
from app.auth import storage_client
from app.state import get_db, render_user_badge, require_user
from config import MASTER_RESUME_PATH
from core.parser import extract_header_fields, parse_master_tex_from_string

st.set_page_config(page_title="Profile · AI Resume Modifier", layout="wide")

from app.styling import inject_custom_css, page_header
inject_custom_css()

db = get_db()
user = require_user()
render_user_badge(user)

page_header(
    "Profile",
    "Your master resume and candidate details. These are used for every "
    "application you tailor.",
)


def render_setup_section(master_resume, profile):
    st.subheader("Master Resume")
    uploaded = st.file_uploader("Upload your master resume (.tex)", type=["tex"])
    use_default = st.button(
        "Use existing file at Resources/main.tex", disabled=not Path(MASTER_RESUME_PATH).exists()
    )

    tex_text = None
    if uploaded is not None:
        tex_text = uploaded.getvalue().decode("utf-8")
    elif use_default:
        tex_text = Path(MASTER_RESUME_PATH).read_text()

    if tex_text is not None:
        try:
            parsed = parse_master_tex_from_string(tex_text)
        except Exception as e:
            st.error(f"Couldn't parse this resume: {e}")
        else:
            # Per-user Storage path -- overwritten on every (re-)upload, including
            # when using the shared template, so later pages always re-fetch from
            # one uniform path rather than special-casing template users.
            storage_path = f"masters/{user['uid']}/main.tex"
            storage_client.upload_text(storage_path, tex_text)
            skeleton_hash = hashlib.sha256(tex_text.encode()).hexdigest()
            repo.set_master_resume(db, user["uid"], storage_path, parsed.content_model, skeleton_hash)
            st.success("Master resume parsed and saved as the active version.")

            header_fields = extract_header_fields(parsed.original_text)
            repo.upsert_candidate_profile(
                db,
                user["uid"],
                name=profile.get("name") or header_fields.get("name"),
                phone=profile.get("phone") or header_fields.get("phone"),
                email=profile.get("email") or header_fields.get("email") or user["email"],
                github=profile.get("github") or header_fields.get("github"),
                location=profile.get("location") or header_fields.get("location"),
                years_experience=profile.get("years_experience"),
                education_summary=profile.get("education_summary"),
                visa_status_text=profile.get("visa_status_text"),
            )
            master_resume = repo.get_master_resume(db, user["uid"])
            profile = repo.get_candidate_profile(db, user["uid"]) or {}

    if master_resume:
        from core.resume_model import ContentModel

        cm = ContentModel.model_validate(master_resume["content_model"])
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

    st.subheader("Candidate Details")
    st.caption("Used to give the LLM accurate context for eligibility and matching.")

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
                db, user["uid"], name=name, phone=phone, email=email, github=github, location=location,
                years_experience=years_experience, education_summary=education_summary,
                visa_status_text=visa_status_text,
            )
            st.success("Profile saved.")

    return repo.get_master_resume(db, user["uid"])


master_resume = repo.get_master_resume(db, user["uid"])
profile = repo.get_candidate_profile(db, user["uid"]) or {}
setup_complete = master_resume is not None and bool(profile.get("name"))

if setup_complete:
    if st.button("Start a new application", type="primary"):
        st.switch_page("pages/1_Job_Input.py")

    with st.expander("Master resume and candidate details"):
        master_resume = render_setup_section(master_resume, profile)
else:
    st.info("Upload your master resume and fill in your details to get started. You can edit both anytime.")
    master_resume = render_setup_section(master_resume, profile)
    st.divider()
    if st.button("Start a new application", type="primary", disabled=master_resume is None):
        st.switch_page("pages/1_Job_Input.py")

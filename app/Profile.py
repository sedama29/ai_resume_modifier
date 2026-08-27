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


from app.styling import inject_custom_css, page_header
inject_custom_css()

db = get_db()
user = require_user()
render_user_badge(user)

page_header(
    "Your resume profile",
    "Manage your master resume and candidate information -- used for every application you tailor.",
)


def _handle_upload(tex_text: str, profile: dict) -> None:
    try:
        parsed = parse_master_tex_from_string(tex_text)
    except Exception as e:
        st.error(f"Couldn't parse this resume: {e}")
        return
    # Per-user Storage path -- overwritten on every (re-)upload, including when
    # using the shared template, so later pages always re-fetch from one
    # uniform path rather than special-casing template users.
    storage_path = f"masters/{user['uid']}/main.tex"
    storage_client.upload_text(storage_path, tex_text)
    skeleton_hash = hashlib.sha256(tex_text.encode()).hexdigest()
    repo.set_master_resume(db, user["uid"], storage_path, parsed.content_model, skeleton_hash)
    st.success("Master resume parsed and saved as the active version.")

    header_fields = extract_header_fields(parsed.original_text)
    repo.upsert_candidate_profile(
        db, user["uid"],
        name=profile.get("name") or header_fields.get("name"),
        phone=profile.get("phone") or header_fields.get("phone"),
        email=profile.get("email") or header_fields.get("email") or user["email"],
        github=profile.get("github") or header_fields.get("github"),
        location=profile.get("location") or header_fields.get("location"),
        years_experience=profile.get("years_experience"),
        education_summary=profile.get("education_summary"),
        visa_status_text=profile.get("visa_status_text"),
    )
    st.rerun()


def render_upload_form(profile: dict) -> None:
    uploaded = st.file_uploader("Upload your master resume (.tex)", type=["tex"])
    use_default = st.button(
        "Use existing file at Resources/main.tex", disabled=not Path(MASTER_RESUME_PATH).exists()
    )
    if uploaded is not None:
        _handle_upload(uploaded.getvalue().decode("utf-8"), profile)
    elif use_default:
        _handle_upload(Path(MASTER_RESUME_PATH).read_text(), profile)


master_resume = repo.get_master_resume(db, user["uid"])
profile = repo.get_candidate_profile(db, user["uid"]) or {}
setup_complete = master_resume is not None and bool(profile.get("name"))

if setup_complete:
    if st.button("Start a new application", type="primary"):
        st.switch_page("pages/1_Job_Input.py")
    st.write("")

st.subheader("Master Resume")
if master_resume:
    from core.resume_model import ContentModel

    with st.container(border=True):
        st.markdown(f"**{Path(master_resume['source_storage_path']).name}**")
        st.caption(f"Last updated: {str(master_resume.get('uploaded_at', ''))[:10]}")
        cm = ContentModel.model_validate(master_resume["content_model"])
        st.caption(f"{len(cm.experience)} experience entries · {len(cm.skills)} skill lines")
        with st.expander("View parsed content"):
            st.write("**Summary**")
            st.write(cm.summary.text)
            st.write("**Experience**")
            for e in cm.experience:
                st.write(f"- {e.org_label} ({len(e.bullets)} bullets)")
            st.write("**Skills**")
            for s in cm.skills:
                st.write(f"- {s.text}")
        with st.expander("Replace master resume"):
            render_upload_form(profile)
else:
    st.info("Upload your master resume .tex to get started.")
    with st.container(border=True):
        render_upload_form(profile)

st.write("")
st.subheader("Candidate Information")
st.caption("Used to give the LLM accurate context for eligibility and matching.")

if profile.get("name"):
    with st.container(border=True):
        c1, c2 = st.columns(2)
        c1.write(f"**Name**  \n{profile.get('name') or '—'}")
        c1.write(f"**Location**  \n{profile.get('location') or '—'}")
        c1.write(f"**Experience**  \n{profile.get('years_experience') or 0} years")
        c2.write(f"**Email**  \n{profile.get('email') or '—'}")
        c2.write(f"**GitHub**  \n{profile.get('github') or '—'}")
        c2.write(f"**Work authorization**  \n{profile.get('visa_status_text') or '—'}")

with (st.expander("Edit candidate information") if profile.get("name") else st.container()):
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
        if st.form_submit_button("Save profile", type="primary"):
            repo.upsert_candidate_profile(
                db, user["uid"], name=name, phone=phone, email=email, github=github, location=location,
                years_experience=years_experience, education_summary=education_summary,
                visa_status_text=visa_status_text,
            )
            st.success("Profile saved.")
            st.rerun()

if not setup_complete:
    st.write("")
    if st.button("Start a new application", type="primary", disabled=master_resume is None):
        st.switch_page("pages/1_Job_Input.py")

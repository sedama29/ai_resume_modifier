import hashlib
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import requests
import streamlit as st

import db.repository as repo
from app.auth import storage_client
from app.state import get_db, render_user_badge, require_user
from config import MASTER_RESUME_PATH
from core.evidence import TIER_LABELS
from core.parser import extract_header_fields, parse_master_tex_from_string
from integrations.github_client import parse_github_username
from llm.github_analysis import analyze_github_profile


from app.styling import initials, inject_custom_css, page_header
inject_custom_css()

db = get_db()
user = require_user()
render_user_badge(user)

page_header("Profile", "Your candidate information and master resume.")


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
        professional_title=profile.get("professional_title"),
        linkedin=profile.get("linkedin"),
        website=profile.get("website"),
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

# --- Candidate Profile -------------------------------------------------------
st.subheader("Candidate Profile")
st.session_state.setdefault("profile_editing", False)
editing = st.session_state["profile_editing"] or not profile.get("name")

if profile.get("name") and not editing:
    with st.container(border=True):
        col_avatar, col_info = st.columns([1, 7], vertical_alignment="top")
        with col_avatar:
            picture = user.get("picture")
            if picture:
                st.image(picture, width=56)
            else:
                st.markdown(
                    f'<div style="width:56px;height:56px;border-radius:50%;background:#5B5FC7;color:#fff;'
                    f'display:flex;align-items:center;justify-content:center;font-size:1.1rem;font-weight:600;">'
                    f'{initials(profile.get("name"), user["email"])}</div>',
                    unsafe_allow_html=True,
                )
        with col_info:
            title_html = (
                f'<div style="color:var(--muted);font-size:0.9rem;margin-top:2px;">{profile["professional_title"]}</div>'
                if profile.get("professional_title") else ""
            )
            st.markdown(
                f'<div style="font-size:1.15rem;font-weight:650;color:var(--ink);">{profile["name"]}</div>{title_html}',
                unsafe_allow_html=True,
            )
            contact_bits = [b for b in [profile.get("email"), profile.get("location")] if b]
            if contact_bits:
                st.markdown(
                    f'<div style="color:var(--muted);font-size:0.88rem;margin-top:10px;">{"  ·  ".join(contact_bits)}</div>',
                    unsafe_allow_html=True,
                )
            links = []
            if profile.get("linkedin"):
                links.append(f'<a href="{profile["linkedin"]}" target="_blank">LinkedIn</a>')
            if profile.get("github"):
                links.append(f'<a href="{profile["github"]}" target="_blank">GitHub</a>')
            if profile.get("website"):
                links.append(f'<a href="{profile["website"]}" target="_blank">Portfolio</a>')
            if links:
                st.markdown(
                    f'<div style="font-size:0.88rem;margin-top:4px;">{"  ·  ".join(links)}</div>',
                    unsafe_allow_html=True,
                )
        _, col_btn = st.columns([5, 1.4])
        with col_btn:
            if st.button("Edit Profile", use_container_width=True, key="edit_profile_btn"):
                st.session_state["profile_editing"] = True
                st.rerun()
else:
    with st.container(border=True):
        with st.form("profile_form"):
            col1, col2 = st.columns(2)
            with col1:
                name = st.text_input("Full Name", value=profile.get("name") or "")
                email = st.text_input("Email", value=profile.get("email") or user["email"])
                location = st.text_input("Location", value=profile.get("location") or "")
                linkedin = st.text_input("LinkedIn", value=profile.get("linkedin") or "", placeholder="https://linkedin.com/in/...")
            with col2:
                professional_title = st.text_input("Professional Title", value=profile.get("professional_title") or "")
                phone = st.text_input("Phone", value=profile.get("phone") or "")
                github = st.text_input("GitHub", value=profile.get("github") or "")
                website = st.text_input("Portfolio / Website", value=profile.get("website") or "")

            st.markdown("**Additional details**")
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

            col_cancel, col_save = st.columns(2)
            cancel = col_cancel.form_submit_button("Cancel", use_container_width=True, disabled=not profile.get("name"))
            save = col_save.form_submit_button("Save Profile", type="primary", use_container_width=True)

            if save:
                repo.upsert_candidate_profile(
                    db, user["uid"], name=name, phone=phone, email=email, github=github, location=location,
                    years_experience=years_experience, education_summary=education_summary,
                    visa_status_text=visa_status_text, professional_title=professional_title,
                    linkedin=linkedin, website=website,
                )
                st.session_state["profile_editing"] = False
                st.success("Profile saved.")
                st.rerun()
            if cancel:
                st.session_state["profile_editing"] = False
                st.rerun()

st.write("")

# --- Master Resume -----------------------------------------------------------
st.subheader("Master Resume")

if master_resume:
    from core.resume_model import ContentModel

    cm = ContentModel.model_validate(master_resume["content_model"])

    @st.dialog("Resume Preview")
    def _view_resume_dialog(cm=cm) -> None:
        st.write("**Summary**")
        st.write(cm.summary.text)
        st.write("**Experience**")
        for e in cm.experience:
            st.write(f"- {e.org_label} ({len(e.bullets)} bullets)")
        st.write("**Skills**")
        for s in cm.skills:
            st.write(f"- {s.text}")

    @st.dialog("Replace Master Resume")
    def _replace_resume_dialog(profile=profile) -> None:
        render_upload_form(profile)

    with st.container(border=True):
        col1, col2 = st.columns([3, 2], vertical_alignment="center")
        with col1:
            st.markdown(f"**{Path(master_resume['source_storage_path']).name}**")
            st.caption(f"LaTeX source · {len(cm.experience)} experience entries · {len(cm.skills)} skill lines")
        with col2:
            st.caption(f"Last updated: {str(master_resume.get('uploaded_at', ''))[:10]}")
        st.write("")
        b1, b2 = st.columns(2)
        with b1:
            if st.button("View Resume", use_container_width=True):
                _view_resume_dialog()
        with b2:
            if st.button("Replace Resume", use_container_width=True):
                _replace_resume_dialog()
else:
    st.info("Upload your master resume .tex to get started.")
    with st.container(border=True):
        render_upload_form(profile)

st.write("")

# --- GitHub / Project Experience ---------------------------------------------
st.subheader("GitHub / Project Experience")
st.caption(
    "Optional -- helps discover relevant projects that aren't written into your resume. "
    "Never assumed to be professional experience; you'll always be asked to confirm anything found."
)

with st.container(border=True):
    github_url = st.text_input(
        "GitHub profile URL", value=profile.get("github_url") or "",
        placeholder="https://github.com/username", key="github_url_input",
    )
    if st.button("Analyze GitHub", disabled=not github_url.strip()):
        username = parse_github_username(github_url)
        try:
            with st.spinner(f"Analyzing {username}'s public repositories..."):
                analysis = analyze_github_profile(username, db, user["uid"])
        except requests.HTTPError as e:
            status = e.response.status_code if e.response is not None else None
            if status == 404:
                st.error(f"Couldn't find a public GitHub profile for \"{username}\".")
            elif status == 403:
                st.error("GitHub's public API rate limit was hit (it's unauthenticated, ~60 requests/hour). Wait a few minutes and try again.")
            else:
                st.error(f"GitHub API error ({status}) while analyzing \"{username}\".")
        except Exception as e:
            st.error(f"GitHub analysis failed: {e}")
        else:
            analysis["analyzed_at"] = datetime.now(timezone.utc).isoformat()
            repo.upsert_candidate_profile(db, user["uid"], github_url=github_url, github_analysis=analysis)
            st.success(f"Analyzed {len(analysis.get('repos', []))} public repositories.")
            st.rerun()

    github_analysis = profile.get("github_analysis")
    if github_analysis and github_analysis.get("repos"):
        st.caption(
            f"Last analyzed: {str(github_analysis.get('analyzed_at', ''))[:10]} · "
            f"{len(github_analysis['repos'])} repositories"
        )
        with st.expander("View discovered technologies"):
            for r in github_analysis["repos"]:
                label = f"**{r['name']}**" + (f" — _{r['summary']}_" if r.get("summary") else "")
                st.markdown(label)
                techs = ", ".join(t["name"] for t in r.get("technologies", []))
                st.caption(techs or "No technologies identified.")

st.write("")

# --- Current Learning ---------------------------------------------------------
st.subheader("Current Learning")
st.caption(
    "Courses, bootcamps, or technologies you're currently working on -- shown as "
    "\"currently learning,\" never represented as professional experience."
)

current_learning = profile.get("current_learning") or []
with st.container(border=True):
    if current_learning:
        for i, item in enumerate(current_learning):
            c1, c2 = st.columns([5, 1], vertical_alignment="center")
            with c1:
                st.markdown(f"**{item.get('title') or ', '.join(item.get('technologies', []))}**")
                meta_bits = [b for b in [item.get("status"), ", ".join(item.get("technologies", []) or [])] if b]
                if item.get("course_url"):
                    meta_bits.append(f"[Course link]({item['course_url']})")
                if meta_bits:
                    st.caption(" · ".join(meta_bits))
            with c2:
                if st.button("Remove", key=f"remove_learning_{i}", use_container_width=True):
                    updated = [x for j, x in enumerate(current_learning) if j != i]
                    repo.upsert_candidate_profile(db, user["uid"], current_learning=updated)
                    st.rerun()
        st.write("")

    with st.expander("Add learning item"):
        with st.form("add_learning_form", clear_on_submit=True):
            title = st.text_input("Course / bootcamp name (optional)", placeholder="e.g. AI Engineering Bootcamp -- Codebasics, Cohort 3")
            course_url = st.text_input("Course URL (optional)")
            status = st.selectbox("Status", ["Currently enrolled", "Self-study", "Completed"])
            technologies_text = st.text_input(
                "Technologies / topics (comma-separated)", placeholder="e.g. LLMs, RAG, Qdrant, LangChain",
            )
            if st.form_submit_button("Add", type="primary"):
                technologies = [t.strip() for t in technologies_text.split(",") if t.strip()]
                if not title and not technologies:
                    st.error("Enter at least a course name or one technology.")
                else:
                    new_item = {
                        "title": title or None, "course_url": course_url or None,
                        "status": status, "technologies": technologies,
                    }
                    repo.upsert_candidate_profile(db, user["uid"], current_learning=current_learning + [new_item])
                    st.success("Added.")
                    st.rerun()

# --- Saved Experiences (confirmed from GitHub/learning discoveries) ----------
confirmed_experiences = profile.get("confirmed_experiences") or []
if confirmed_experiences:
    st.write("")
    st.subheader("Saved Experiences")
    st.caption("Technologies confirmed from GitHub or learning discoveries, kept in mind for future applications.")
    with st.container(border=True):
        for i, exp in enumerate(confirmed_experiences):
            c1, c2 = st.columns([5, 1], vertical_alignment="center")
            with c1:
                st.markdown(f"**{exp['technology']}** — {TIER_LABELS.get(exp['tier'], exp['tier'])}")
                st.caption(f"{exp.get('source_detail', '')} · {(exp.get('evidence') or '')[:140]}")
            with c2:
                if st.button("Remove", key=f"remove_confirmed_{i}", use_container_width=True):
                    updated = [x for j, x in enumerate(confirmed_experiences) if j != i]
                    repo.upsert_candidate_profile(db, user["uid"], confirmed_experiences=updated)
                    st.rerun()

if not setup_complete:
    st.write("")
    if st.button("Start a new application", type="primary", disabled=master_resume is None):
        st.switch_page("pages/1_Job_Input.py")

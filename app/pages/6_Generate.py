import sys
import tempfile
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

import streamlit as st

import db.repository as repo
from app.auth import storage_client
from app.state import get_db, render_user_badge, require_active_application_id, require_user
from core.naming import next_version_number, resume_name
from core.parser import parse_master_tex_from_string
from core.renderer import render_tex
from core.resume_model import ContentModel
from latex.compiler import compile_tex


from app.styling import inject_custom_css, page_header, progress_stepper
inject_custom_css()

db = get_db()
user = require_user()
render_user_badge(user)

page_header("Generate Resume")
progress_stepper("generate")

application_id = require_active_application_id(db, user["uid"])
application = repo.get_job_application(db, user["uid"], application_id)
master_resume = repo.get_master_resume(db, user["uid"])

final_content_model = st.session_state.get(f"final_content_model_{application_id}")
if final_content_model is None:
    review_state = st.session_state.get(f"review_{application_id}")
    if review_state:
        final_content_model = review_state["merged"]
    else:
        final_content_model = ContentModel.model_validate(master_resume["content_model"])
        st.warning("No reviewed changes found -- generating from the unmodified master resume.")

latest_version = repo.get_latest_resume_version(db, user["uid"], application_id)

with st.container(border=True):
    st.markdown("**Your resume is ready**")
    st.write("✓ Master format preserved")
    st.write("✓ Job-specific customization complete")
    st.write("✓ Changes reviewed" if f"final_content_model_{application_id}" in st.session_state else "○ Using unmodified master resume")

st.write("")
st.markdown("**How would you like to save this resume?**")

mode_key = f"generate_mode_{application_id}"
st.session_state.setdefault(mode_key, "new")

col1, col2 = st.columns(2)
with col1:
    with st.container(border=True):
        st.markdown("**Create New Resume**")
        st.caption("Recommended — keeps master intact.")
        if st.button(
            "Select" if st.session_state[mode_key] != "new" else "Selected ✓",
            key="select_new", use_container_width=True,
            type="primary" if st.session_state[mode_key] == "new" else "secondary",
        ):
            st.session_state[mode_key] = "new"
            st.rerun()
with col2:
    with st.container(border=True):
        st.markdown("**Overwrite Existing Resume**")
        st.caption("Updates the current version's files in place.")
        if st.button(
            "Select" if st.session_state[mode_key] != "overwrite" else "Selected ✓",
            key="select_overwrite", use_container_width=True, disabled=latest_version is None,
            type="primary" if st.session_state[mode_key] == "overwrite" else "secondary",
        ):
            st.session_state[mode_key] = "overwrite"
            st.rerun()

overwrite = st.session_state[mode_key] == "overwrite"
st.write("")

if st.button("Generate", type="primary"):
    version_number = next_version_number(
        latest_version["version_number"] if latest_version else None, overwrite
    )
    year_month = datetime.now().strftime("%Y-%m")
    name = resume_name(
        application["company"] or "Company", application["job_title"] or "Role", year_month, version_number
    )

    resume_version_id = repo.create_resume_version(
        db, user["uid"], application_id, version_number, name, final_content_model,
        is_overwrite_of=latest_version["id"] if (overwrite and latest_version) else None,
    )

    master_tex_text = storage_client.download_text(master_resume["source_storage_path"])
    parsed_master = parse_master_tex_from_string(master_tex_text)
    tex_content = render_tex(parsed_master, final_content_model)

    with st.spinner("Compiling PDF..."):
        with tempfile.TemporaryDirectory() as scratch:
            result = compile_tex(tex_content, Path(scratch) / f"_compile_{name}")

            # uid-prefixed so ownership is derivable from the path alone (see
            # firestore.rules / storage.rules) -- not just from the secrecy
            # of the Firestore-generated application_id.
            tex_storage_path = f"applications/{user['uid']}/{application_id}/{name}.tex"
            storage_client.upload_text(tex_storage_path, tex_content)

            pdf_storage_path = None
            pdf_bytes = None
            if result.success:
                pdf_bytes = Path(result.pdf_path).read_bytes()
                pdf_storage_path = f"applications/{user['uid']}/{application_id}/{name}.pdf"
                storage_client.upload_bytes(pdf_storage_path, pdf_bytes, "application/pdf")

    repo.update_resume_version_compile_result(
        db, user["uid"], application_id, resume_version_id, tex_storage_path,
        pdf_storage_path, result.success, result.log_text,
    )
    repo.update_job_application_status(db, user["uid"], application_id, "generated")

    if result.success:
        st.success(f"Generated {name}.pdf")
        st.download_button("Download PDF", pdf_bytes, file_name=f"{name}.pdf", mime="application/pdf")
        st.download_button("Download .tex", tex_content, file_name=f"{name}.tex", mime="text/plain")
    else:
        st.error(result.error_summary or "Compilation failed.")
        with st.expander("Full compile log"):
            st.code(result.log_text or "(no log captured)")
        st.download_button("Download .tex (fix manually)", tex_content, file_name=f"{name}.tex", mime="text/plain")

st.write("")
versions = repo.list_resume_versions(db, user["uid"], application_id)
if versions:
    st.subheader("Versions for this application")
    for v in versions:
        status = "compiled" if v["compile_success"] else ("failed" if v["compile_success"] is not None else "not yet generated")
        st.write(f"- **{v['name']}** ({status})")

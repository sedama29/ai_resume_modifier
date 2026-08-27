import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

import streamlit as st

import db.repository as repo
from app.state import get_db, render_user_badge, require_active_application_id, require_user
from config import STORAGE_DIR
from core.naming import next_version_number, resume_name
from core.parser import parse_master_tex
from core.renderer import render_tex
from core.resume_model import ContentModel
from latex.compiler import compile_tex

st.set_page_config(page_title="Generate", page_icon="📄", layout="wide")

from app.styling import inject_custom_css
inject_custom_css()

conn = get_db()
user = require_user()
render_user_badge(user)

st.title("Generate Resume")

application_id = require_active_application_id(conn, user["uid"])
application = repo.get_job_application(conn, application_id)
active_master = repo.get_active_master_resume_version(conn, user["uid"])

final_content_model = st.session_state.get(f"final_content_model_{application_id}")
if final_content_model is None:
    review_state = st.session_state.get(f"review_{application_id}")
    if review_state:
        final_content_model = review_state["merged"]
    else:
        final_content_model = ContentModel.model_validate_json(active_master["content_model_json"])
        st.warning("No reviewed changes found -- generating from the unmodified master resume.")

latest_version = repo.get_latest_resume_version(conn, application_id)

mode = st.radio(
    "What do you want to do?",
    ["Create New Resume", "Overwrite Existing Resume"],
    disabled=latest_version is None,
    help="Overwrite regenerates the current version's files in place. Create New always adds a new version.",
)
overwrite = mode == "Overwrite Existing Resume"

if st.button("Generate", type="primary"):
    version_number = next_version_number(
        latest_version["version_number"] if latest_version else None, overwrite
    )
    year_month = datetime.now().strftime("%Y-%m")
    name = resume_name(
        application["company"] or "Company", application["job_title"] or "Role", year_month, version_number
    )

    resume_version_id = repo.create_resume_version(
        conn, application_id, version_number, name, final_content_model,
        is_overwrite_of=latest_version["id"] if (overwrite and latest_version) else None,
    )

    parsed_master = parse_master_tex(active_master["source_file_path"])
    tex_content = render_tex(parsed_master, final_content_model)

    app_dir = STORAGE_DIR / f"application_{application_id}"
    app_dir.mkdir(parents=True, exist_ok=True)
    tex_path = app_dir / f"{name}.tex"
    tex_path.write_text(tex_content)

    with st.spinner("Compiling PDF..."):
        result = compile_tex(tex_content, app_dir / f"_compile_{name}")

    repo.update_resume_version_compile_result(
        conn, resume_version_id, str(tex_path),
        result.pdf_path, result.success, result.log_text,
    )
    repo.update_job_application_status(conn, application_id, "generated")

    if result.success:
        st.success(f"Generated {name}.pdf")
        pdf_bytes = Path(result.pdf_path).read_bytes()
        st.download_button("Download PDF", pdf_bytes, file_name=f"{name}.pdf", mime="application/pdf")
        st.download_button("Download .tex", tex_content, file_name=f"{name}.tex", mime="text/plain")
    else:
        st.error(result.error_summary or "Compilation failed.")
        with st.expander("Full compile log"):
            st.code(result.log_text or "(no log captured)")
        st.download_button("Download .tex (fix manually)", tex_content, file_name=f"{name}.tex", mime="text/plain")

st.divider()
versions = repo.list_resume_versions(conn, application_id)
if versions:
    st.subheader("Versions for this application")
    for v in versions:
        status = "✅ compiled" if v["compile_success"] else ("❌ failed" if v["compile_success"] is not None else "not yet generated")
        st.write(f"- **{v['name']}** ({status})")

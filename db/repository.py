"""Typed CRUD helpers over the SQLite schema. Thin by design -- callers own
business logic (e.g. version-number computation lives in core/naming.py)."""
import json
from datetime import datetime, timezone
from sqlite3 import Connection

from core.resume_model import ContentModel


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


# --- master_resume_versions -------------------------------------------------

def create_master_resume_version(
    conn: Connection, owner_uid: str, source_file_path: str, content_model: ContentModel, skeleton_hash: str
) -> int:
    # Scoped by owner_uid -- without this WHERE, one user uploading a resume
    # would silently deactivate every other user's active master resume.
    conn.execute("UPDATE master_resume_versions SET is_active = 0 WHERE owner_uid = ?", (owner_uid,))
    cur = conn.execute(
        "INSERT INTO master_resume_versions (owner_uid, uploaded_at, source_file_path, content_model_json, skeleton_hash, is_active)"
        " VALUES (?, ?, ?, ?, ?, 1)",
        (owner_uid, _now(), source_file_path, content_model.model_dump_json(), skeleton_hash),
    )
    conn.commit()
    return cur.lastrowid


def get_active_master_resume_version(conn: Connection, owner_uid: str) -> dict | None:
    row = conn.execute(
        "SELECT * FROM master_resume_versions WHERE owner_uid = ? AND is_active = 1 ORDER BY id DESC LIMIT 1",
        (owner_uid,),
    ).fetchone()
    return dict(row) if row else None


# --- candidate_profile -------------------------------------------------------

def upsert_candidate_profile(conn: Connection, owner_uid: str, **fields) -> int:
    existing = conn.execute(
        "SELECT id FROM candidate_profile WHERE owner_uid = ? ORDER BY id DESC LIMIT 1", (owner_uid,)
    ).fetchone()
    fields["updated_at"] = _now()
    if existing:
        set_clause = ", ".join(f"{k} = ?" for k in fields)
        conn.execute(
            f"UPDATE candidate_profile SET {set_clause} WHERE id = ?",
            (*fields.values(), existing["id"]),
        )
        conn.commit()
        return existing["id"]
    fields["owner_uid"] = owner_uid
    cols = ", ".join(fields.keys())
    placeholders = ", ".join("?" for _ in fields)
    cur = conn.execute(
        f"INSERT INTO candidate_profile ({cols}) VALUES ({placeholders})", tuple(fields.values())
    )
    conn.commit()
    return cur.lastrowid


def get_candidate_profile(conn: Connection, owner_uid: str) -> dict | None:
    row = conn.execute(
        "SELECT * FROM candidate_profile WHERE owner_uid = ? ORDER BY id DESC LIMIT 1", (owner_uid,)
    ).fetchone()
    return dict(row) if row else None


# --- job_applications ---------------------------------------------------------

def create_job_application(
    conn: Connection,
    owner_uid: str,
    master_resume_version_id: int,
    jd_text: str,
    jd_source: str,
    job_url: str | None = None,
    company: str | None = None,
    job_title: str | None = None,
) -> int:
    cur = conn.execute(
        "INSERT INTO job_applications"
        " (owner_uid, master_resume_version_id, company, job_title, job_url, jd_text, jd_source, status, created_at)"
        " VALUES (?, ?, ?, ?, ?, ?, ?, 'draft', ?)",
        (owner_uid, master_resume_version_id, company, job_title, job_url, jd_text, jd_source, _now()),
    )
    conn.commit()
    return cur.lastrowid


def update_job_application_status(conn: Connection, application_id: int, status: str) -> None:
    conn.execute("UPDATE job_applications SET status = ? WHERE id = ?", (status, application_id))
    conn.commit()


def update_job_application_company_title(
    conn: Connection, application_id: int, company: str, job_title: str
) -> None:
    conn.execute(
        "UPDATE job_applications SET company = ?, job_title = ? WHERE id = ?",
        (company, job_title, application_id),
    )
    conn.commit()


def get_job_application(conn: Connection, application_id: int) -> dict | None:
    row = conn.execute("SELECT * FROM job_applications WHERE id = ?", (application_id,)).fetchone()
    return dict(row) if row else None


def get_job_application_for_owner(conn: Connection, application_id: int, owner_uid: str) -> dict | None:
    """The ownership-assertion primitive: used wherever an application_id
    crosses a trust boundary (e.g. out of st.session_state) to confirm it
    actually belongs to the current user before any child-table query runs."""
    row = conn.execute(
        "SELECT * FROM job_applications WHERE id = ? AND owner_uid = ?", (application_id, owner_uid)
    ).fetchone()
    return dict(row) if row else None


def list_job_applications(conn: Connection, owner_uid: str) -> list[dict]:
    rows = conn.execute(
        "SELECT * FROM job_applications WHERE owner_uid = ? ORDER BY created_at DESC", (owner_uid,)
    ).fetchall()
    return [dict(r) for r in rows]


# --- job_analysis_results ------------------------------------------------------

def save_job_analysis_result(conn: Connection, application_id: int, analysis: dict) -> int:
    cur = conn.execute(
        "INSERT INTO job_analysis_results"
        " (application_id, required_skills_json, preferred_skills_json, key_responsibilities_json,"
        "  required_experience_years, required_education, work_auth_excerpts_json, raw_llm_response_json, created_at)"
        " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (
            application_id,
            json.dumps(analysis.get("required_skills", [])),
            json.dumps(analysis.get("preferred_skills", [])),
            json.dumps(analysis.get("key_responsibilities", [])),
            analysis.get("required_experience_years"),
            analysis.get("required_education"),
            json.dumps(analysis.get("work_authorization_text_excerpts", [])),
            json.dumps(analysis),
            _now(),
        ),
    )
    conn.commit()
    return cur.lastrowid


def get_latest_job_analysis(conn: Connection, application_id: int) -> dict | None:
    row = conn.execute(
        "SELECT * FROM job_analysis_results WHERE application_id = ? ORDER BY id DESC LIMIT 1",
        (application_id,),
    ).fetchone()
    return dict(row) if row else None


# --- eligibility_results --------------------------------------------------------

def save_eligibility_result(conn: Connection, application_id: int, eligibility: dict) -> int:
    cur = conn.execute(
        "INSERT INTO eligibility_results"
        " (application_id, work_auth_category, work_auth_reasoning, work_auth_evidence_json,"
        "  experience_gap_years, experience_gap_assessment, education_match, overall_recommendation,"
        "  raw_llm_response_json, created_at)"
        " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (
            application_id,
            eligibility["work_auth_category"],
            eligibility.get("work_auth_reasoning"),
            json.dumps(eligibility.get("work_auth_evidence_quotes", [])),
            eligibility.get("experience_gap_years"),
            eligibility.get("experience_gap_assessment"),
            eligibility.get("education_match"),
            eligibility.get("overall_recommendation"),
            json.dumps(eligibility),
            _now(),
        ),
    )
    conn.commit()
    return cur.lastrowid


def get_latest_eligibility_result(conn: Connection, application_id: int) -> dict | None:
    row = conn.execute(
        "SELECT * FROM eligibility_results WHERE application_id = ? ORDER BY id DESC LIMIT 1",
        (application_id,),
    ).fetchone()
    return dict(row) if row else None


# --- match_results -----------------------------------------------------------

def save_match_result(conn: Connection, application_id: int, match: dict) -> int:
    cur = conn.execute(
        "INSERT INTO match_results"
        " (application_id, skills_present_json, skills_missing_json, skills_implied_json, match_score, raw_llm_response_json, created_at)"
        " VALUES (?, ?, ?, ?, ?, ?, ?)",
        (
            application_id,
            json.dumps(match.get("present", [])),
            json.dumps(match.get("missing", [])),
            json.dumps(match.get("potentially_implied", [])),
            match.get("match_score"),
            json.dumps(match),
            _now(),
        ),
    )
    conn.commit()
    return cur.lastrowid


def get_latest_match_result(conn: Connection, application_id: int) -> dict | None:
    row = conn.execute(
        "SELECT * FROM match_results WHERE application_id = ? ORDER BY id DESC LIMIT 1",
        (application_id,),
    ).fetchone()
    return dict(row) if row else None


# --- followup_questions / followup_answers --------------------------------------

def save_followup_questions(conn: Connection, application_id: int, questions: list[dict]) -> list[int]:
    ids = []
    for idx, q in enumerate(questions):
        cur = conn.execute(
            "INSERT INTO followup_questions (application_id, question_text, related_skill, importance, order_index, created_at)"
            " VALUES (?, ?, ?, ?, ?, ?)",
            (application_id, q["question_text"], q.get("skill"), q.get("importance"), idx, _now()),
        )
        ids.append(cur.lastrowid)
    conn.commit()
    return ids


def list_followup_questions(conn: Connection, application_id: int) -> list[dict]:
    rows = conn.execute(
        "SELECT * FROM followup_questions WHERE application_id = ? ORDER BY order_index",
        (application_id,),
    ).fetchall()
    return [dict(r) for r in rows]


def save_followup_answer(
    conn: Connection,
    question_id: int,
    application_id: int,
    answer_bool: bool | None,
    answer_detail_text: str | None,
) -> int:
    cur = conn.execute(
        "INSERT INTO followup_answers (question_id, application_id, answer_bool, answer_detail_text, answered_at)"
        " VALUES (?, ?, ?, ?, ?)",
        (question_id, application_id, int(answer_bool) if answer_bool is not None else None, answer_detail_text, _now()),
    )
    conn.commit()
    return cur.lastrowid


def list_confirmed_answers(conn: Connection, application_id: int) -> list[dict]:
    """Answers where answer_bool == true -- the only valid source_answer_id targets
    for anything the resume rewrite marks as 'added' (see core/validators.py)."""
    rows = conn.execute(
        "SELECT * FROM followup_answers WHERE application_id = ? AND answer_bool = 1",
        (application_id,),
    ).fetchall()
    return [dict(r) for r in rows]


def list_confirmed_answers_with_question_text(conn: Connection, application_id: int) -> list[dict]:
    """Same as list_confirmed_answers but joined with the question text, in the
    shape llm/resume_rewrite.py expects (id, question_text, answer_detail_text)."""
    rows = conn.execute(
        "SELECT fa.id AS id, fq.question_text AS question_text, fa.answer_detail_text AS answer_detail_text"
        " FROM followup_answers fa JOIN followup_questions fq ON fa.question_id = fq.id"
        " WHERE fa.application_id = ? AND fa.answer_bool = 1",
        (application_id,),
    ).fetchall()
    return [dict(r) for r in rows]


# --- resume_versions -----------------------------------------------------------

def get_latest_resume_version(conn: Connection, application_id: int) -> dict | None:
    row = conn.execute(
        "SELECT * FROM resume_versions WHERE application_id = ? ORDER BY version_number DESC LIMIT 1",
        (application_id,),
    ).fetchone()
    return dict(row) if row else None


def create_resume_version(
    conn: Connection,
    application_id: int,
    version_number: int,
    name: str,
    content_model: ContentModel,
    is_overwrite_of: int | None = None,
) -> int:
    cur = conn.execute(
        "INSERT INTO resume_versions"
        " (application_id, version_number, name, content_model_json, is_overwrite_of, created_at)"
        " VALUES (?, ?, ?, ?, ?, ?)",
        (application_id, version_number, name, content_model.model_dump_json(), is_overwrite_of, _now()),
    )
    conn.commit()
    return cur.lastrowid


def update_resume_version_compile_result(
    conn: Connection,
    resume_version_id: int,
    tex_file_path: str,
    pdf_file_path: str | None,
    compile_success: bool,
    compile_log_text: str,
) -> None:
    conn.execute(
        "UPDATE resume_versions SET tex_file_path = ?, pdf_file_path = ?, compile_success = ?, compile_log_text = ? WHERE id = ?",
        (tex_file_path, pdf_file_path, int(compile_success), compile_log_text, resume_version_id),
    )
    conn.commit()


def list_resume_versions(conn: Connection, application_id: int) -> list[dict]:
    rows = conn.execute(
        "SELECT * FROM resume_versions WHERE application_id = ? ORDER BY version_number",
        (application_id,),
    ).fetchall()
    return [dict(r) for r in rows]


# --- generated_changes -----------------------------------------------------------

def save_generated_change(
    conn: Connection,
    resume_version_id: int,
    region: str,
    entry_ref: str | None,
    change_type: str,
    accepted: bool,
    old_text: str | None,
    new_text: str | None,
    source_answer_id: int | None = None,
) -> int:
    cur = conn.execute(
        "INSERT INTO generated_changes"
        " (resume_version_id, region, entry_ref, change_type, source_answer_id, accepted, old_text, new_text)"
        " VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        (resume_version_id, region, entry_ref, change_type, source_answer_id, int(accepted), old_text, new_text),
    )
    conn.commit()
    return cur.lastrowid


def list_generated_changes(conn: Connection, resume_version_id: int) -> list[dict]:
    rows = conn.execute(
        "SELECT * FROM generated_changes WHERE resume_version_id = ?", (resume_version_id,)
    ).fetchall()
    return [dict(r) for r in rows]


# --- overleaf_sync -----------------------------------------------------------

def upsert_overleaf_sync(
    conn: Connection, resume_version_id: int, overleaf_project_url: str | None, sync_status: str, error_text: str | None = None
) -> int:
    existing = conn.execute(
        "SELECT id FROM overleaf_sync WHERE resume_version_id = ?", (resume_version_id,)
    ).fetchone()
    if existing:
        conn.execute(
            "UPDATE overleaf_sync SET overleaf_project_url = ?, sync_status = ?, last_synced_at = ?, error_text = ? WHERE id = ?",
            (overleaf_project_url, sync_status, _now(), error_text, existing["id"]),
        )
        conn.commit()
        return existing["id"]
    cur = conn.execute(
        "INSERT INTO overleaf_sync (resume_version_id, overleaf_project_url, sync_status, last_synced_at, error_text)"
        " VALUES (?, ?, ?, ?, ?)",
        (resume_version_id, overleaf_project_url, sync_status, _now(), error_text),
    )
    conn.commit()
    return cur.lastrowid


# --- api_usage_log (admin-only) -----------------------------------------------

def log_api_usage(
    conn: Connection, owner_uid: str, schema_name: str, model: str,
    prompt_tokens: int | None, completion_tokens: int | None, total_tokens: int | None,
) -> int:
    cur = conn.execute(
        "INSERT INTO api_usage_log (owner_uid, schema_name, model, prompt_tokens, completion_tokens, total_tokens, created_at)"
        " VALUES (?, ?, ?, ?, ?, ?, ?)",
        (owner_uid, schema_name, model, prompt_tokens, completion_tokens, total_tokens, _now()),
    )
    conn.commit()
    return cur.lastrowid


def list_api_usage(conn: Connection) -> list[dict]:
    """Unscoped by design -- only ever called from the superuser-gated API
    Usage admin page."""
    rows = conn.execute("SELECT * FROM api_usage_log ORDER BY created_at DESC").fetchall()
    return [dict(r) for r in rows]

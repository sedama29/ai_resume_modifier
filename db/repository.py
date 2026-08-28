"""Typed CRUD helpers over Firestore. Thin by design -- callers own business
logic (e.g. version-number computation lives in core/naming.py).

Schema:
  users/{uid}                                       candidate_profile map, master_resume map
  users/{uid}/job_applications/{appId}               fields + job_analysis/eligibility/match maps
                                                      (latest-wins, just overwritten) + followup_questions array
  users/{uid}/job_applications/{appId}/resume_versions/{versionId}
                                                      real version history (v1, v2, v3...)
  users/{uid}/api_usage_log/{logId}                  admin-only, read across ALL users via collection_group

Firestore stores nested dicts/lists natively -- content models are stored as
maps directly (content_model.model_dump(mode="json")), never as JSON strings.
"""
from datetime import datetime, timezone

from google.cloud.firestore_v1 import Client, DocumentReference

from core.resume_model import ContentModel


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _snap_to_dict(doc) -> dict:
    return {**doc.to_dict(), "id": doc.id}


def _user_ref(db: Client, owner_uid: str) -> DocumentReference:
    return db.collection("users").document(owner_uid)


def _app_ref(db: Client, owner_uid: str, application_id: str) -> DocumentReference:
    return _user_ref(db, owner_uid).collection("job_applications").document(application_id)


def _resume_version_ref(db: Client, owner_uid: str, application_id: str, resume_version_id: str) -> DocumentReference:
    return _app_ref(db, owner_uid, application_id).collection("resume_versions").document(resume_version_id)


# --- master_resume (users/{uid}.master_resume) --------------------------------

def set_master_resume(
    db: Client, owner_uid: str, source_storage_path: str, content_model: ContentModel, skeleton_hash: str,
    pdf_storage_path: str | None = None, compile_success: bool | None = None, compile_log_text: str | None = None,
    original_filename: str | None = None, asset_storage_paths: list[str] | None = None,
) -> None:
    compilation_status = "ready" if compile_success else ("failed" if compile_success is False else "not_compiled")
    _user_ref(db, owner_uid).set(
        {
            "master_resume": {
                "content_model": content_model.model_dump(mode="json"),
                "source_storage_path": source_storage_path,
                "skeleton_hash": skeleton_hash,
                "uploaded_at": _now(),
                "pdf_storage_path": pdf_storage_path,
                "compile_success": compile_success,
                "compile_log_text": compile_log_text,
                "compilation_status": compilation_status,
                "original_filename": original_filename,
                "asset_storage_paths": asset_storage_paths or [],
            }
        },
        merge=True,
    )


def get_master_resume(db: Client, owner_uid: str) -> dict | None:
    doc = _user_ref(db, owner_uid).get()
    if not doc.exists:
        return None
    return doc.to_dict().get("master_resume")


# --- candidate_profile (users/{uid}.candidate_profile) -------------------------

def upsert_candidate_profile(db: Client, owner_uid: str, **fields) -> None:
    fields["updated_at"] = _now()
    _user_ref(db, owner_uid).set({"candidate_profile": fields}, merge=True)


def get_candidate_profile(db: Client, owner_uid: str) -> dict | None:
    doc = _user_ref(db, owner_uid).get()
    if not doc.exists:
        return None
    return doc.to_dict().get("candidate_profile")


# --- job_applications ---------------------------------------------------------

def create_job_application(
    db: Client,
    owner_uid: str,
    jd_text: str,
    jd_source: str,
    job_url: str | None = None,
    company: str | None = None,
    job_title: str | None = None,
) -> str:
    ref = _user_ref(db, owner_uid).collection("job_applications").document()
    ref.set(
        {
            "company": company, "job_title": job_title, "job_url": job_url,
            "jd_text": jd_text, "jd_source": jd_source, "status": "draft",
            "created_at": _now(),
        }
    )
    return ref.id


def update_job_application_status(db: Client, owner_uid: str, application_id: str, status: str) -> None:
    _app_ref(db, owner_uid, application_id).update({"status": status})


def update_job_application_company_title(
    db: Client, owner_uid: str, application_id: str, company: str, job_title: str
) -> None:
    _app_ref(db, owner_uid, application_id).update({"company": company, "job_title": job_title})


def get_job_application(db: Client, owner_uid: str, application_id: str) -> dict | None:
    """A subcollection path (users/{uid}/job_applications/{appId}) makes an
    owner-less lookup structurally impossible -- this is always owner-scoped,
    the single ownership-assertion primitive for whenever an application_id
    crosses a trust boundary (e.g. out of st.session_state)."""
    doc = _app_ref(db, owner_uid, application_id).get()
    return _snap_to_dict(doc) if doc.exists else None


def list_job_applications(db: Client, owner_uid: str) -> list[dict]:
    docs = (
        _user_ref(db, owner_uid).collection("job_applications")
        .order_by("created_at", direction="DESCENDING").stream()
    )
    return [_snap_to_dict(d) for d in docs]


# --- job_analysis / eligibility / match (latest-wins maps on the application) --

def save_job_analysis_result(db: Client, owner_uid: str, application_id: str, analysis: dict) -> None:
    _app_ref(db, owner_uid, application_id).update({"job_analysis": analysis})


def get_latest_job_analysis(db: Client, owner_uid: str, application_id: str) -> dict | None:
    doc = _app_ref(db, owner_uid, application_id).get()
    return doc.to_dict().get("job_analysis") if doc.exists else None


def save_eligibility_result(db: Client, owner_uid: str, application_id: str, eligibility: dict) -> None:
    _app_ref(db, owner_uid, application_id).update({"eligibility": eligibility})


def get_latest_eligibility_result(db: Client, owner_uid: str, application_id: str) -> dict | None:
    doc = _app_ref(db, owner_uid, application_id).get()
    return doc.to_dict().get("eligibility") if doc.exists else None


def save_match_result(db: Client, owner_uid: str, application_id: str, match: dict) -> None:
    _app_ref(db, owner_uid, application_id).update({"match": match})


def get_latest_match_result(db: Client, owner_uid: str, application_id: str) -> dict | None:
    doc = _app_ref(db, owner_uid, application_id).get()
    return doc.to_dict().get("match") if doc.exists else None


# --- followup_questions (array of maps, combines what were 2 SQL tables) ------

def save_followup_questions(db: Client, owner_uid: str, application_id: str, questions: list[dict]) -> None:
    entries = [
        {
            "question_id": q["question_id"],
            "question_text": q["question_text"],
            "related_skill": q.get("skill"),
            "importance": q.get("importance"),
            "order_index": idx,
            "answer_bool": None,
            "answer_detail_text": None,
            "answered_at": None,
        }
        for idx, q in enumerate(questions)
    ]
    _app_ref(db, owner_uid, application_id).update({"followup_questions": entries})


def list_followup_questions(db: Client, owner_uid: str, application_id: str) -> list[dict]:
    doc = _app_ref(db, owner_uid, application_id).get()
    if not doc.exists:
        return []
    return sorted(doc.to_dict().get("followup_questions", []), key=lambda q: q.get("order_index", 0))


def save_followup_answers(
    db: Client, owner_uid: str, application_id: str, answers: dict[str, tuple[bool | None, str | None]]
) -> None:
    """answers: question_id -> (confirmed, detail_text). One read + one write
    for the whole batch, not one write per question -- Firestore has no
    "update the array element matching this key" op, so a per-item loop would
    otherwise mean N wasteful read-modify-writes of the same document."""
    ref = _app_ref(db, owner_uid, application_id)
    doc = ref.get()
    questions = doc.to_dict().get("followup_questions", []) if doc.exists else []
    now = _now()
    for q in questions:
        if q["question_id"] in answers:
            confirmed, detail = answers[q["question_id"]]
            q["answer_bool"] = confirmed
            q["answer_detail_text"] = detail
            q["answered_at"] = now
    ref.update({"followup_questions": questions})


def add_confirmed_followup_entry(db: Client, owner_uid: str, application_id: str, entry: dict) -> None:
    """Appends an already-answered entry directly into the followup_questions
    array -- used for GitHub/learning discoveries confirmed on the Follow-up
    Questions page's second phase, which aren't part of the LLM-generated
    question set. Reusing the same array means list_confirmed_answers_with_
    question_text() (and resume_rewrite downstream of it) picks these up with
    no further plumbing. `entry` must include question_id, question_text,
    answer_bool=True, answer_detail_text, and experience_tier."""
    ref = _app_ref(db, owner_uid, application_id)
    doc = ref.get()
    questions = doc.to_dict().get("followup_questions", []) if doc.exists else []
    questions.append({"order_index": len(questions), "answered_at": _now(), **entry})
    ref.update({"followup_questions": questions})


def list_confirmed_answers_with_question_text(db: Client, owner_uid: str, application_id: str) -> list[dict]:
    """Answers where answer_bool == true -- the only valid source_answer_id
    targets for anything the resume rewrite marks as 'added'. A question and
    its answer are the same array entry, so this is a plain filter, no
    query/join needed."""
    questions = list_followup_questions(db, owner_uid, application_id)
    return [
        {
            "question_id": q["question_id"],
            "question_text": q["question_text"],
            "answer_detail_text": q.get("answer_detail_text"),
            "experience_tier": q.get("experience_tier"),
        }
        for q in questions
        if q.get("answer_bool") is True
    ]


# --- resume_versions (subcollection -- real history: v1, v2, v3...) -----------

def get_latest_resume_version(db: Client, owner_uid: str, application_id: str) -> dict | None:
    docs = list(
        _app_ref(db, owner_uid, application_id).collection("resume_versions")
        .order_by("version_number", direction="DESCENDING").limit(1).stream()
    )
    return _snap_to_dict(docs[0]) if docs else None


def create_resume_version(
    db: Client,
    owner_uid: str,
    application_id: str,
    version_number: int,
    name: str,
    content_model: ContentModel,
    is_overwrite_of: str | None = None,
) -> str:
    ref = _app_ref(db, owner_uid, application_id).collection("resume_versions").document()
    ref.set(
        {
            "version_number": version_number,
            "name": name,
            "content_model": content_model.model_dump(mode="json"),
            "tex_storage_path": None,
            "pdf_storage_path": None,
            "compile_success": None,
            "compile_log_text": None,
            "is_overwrite_of": is_overwrite_of,
            "created_at": _now(),
        }
    )
    return ref.id


def update_resume_version_compile_result(
    db: Client,
    owner_uid: str,
    application_id: str,
    resume_version_id: str,
    tex_storage_path: str | None,
    pdf_storage_path: str | None,
    compile_success: bool,
    compile_log_text: str,
) -> None:
    _resume_version_ref(db, owner_uid, application_id, resume_version_id).update(
        {
            "tex_storage_path": tex_storage_path,
            "pdf_storage_path": pdf_storage_path,
            "compile_success": compile_success,
            "compile_log_text": compile_log_text,
        }
    )


def list_resume_versions(db: Client, owner_uid: str, application_id: str) -> list[dict]:
    docs = (
        _app_ref(db, owner_uid, application_id).collection("resume_versions")
        .order_by("version_number").stream()
    )
    return [_snap_to_dict(d) for d in docs]


# --- generated_changes (embedded on the resume_version) -----------------------

def save_generated_changes(
    db: Client, owner_uid: str, application_id: str, resume_version_id: str, changes: list[dict]
) -> None:
    _resume_version_ref(db, owner_uid, application_id, resume_version_id).update({"generated_changes": changes})


def list_generated_changes(db: Client, owner_uid: str, application_id: str, resume_version_id: str) -> list[dict]:
    doc = _resume_version_ref(db, owner_uid, application_id, resume_version_id).get()
    return doc.to_dict().get("generated_changes", []) if doc.exists else []


# --- api_usage_log (admin-only, cross-user) ------------------------------------

def log_api_usage(
    db: Client, owner_uid: str, schema_name: str, model: str,
    prompt_tokens: int | None, completion_tokens: int | None, total_tokens: int | None,
) -> None:
    _user_ref(db, owner_uid).collection("api_usage_log").document().set(
        {
            "owner_uid": owner_uid,
            "schema_name": schema_name,
            "model": model,
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "total_tokens": total_tokens,
            "created_at": _now(),
        }
    )


def list_api_usage(db: Client) -> list[dict]:
    """Unscoped by design -- only ever called from the superuser-gated API
    Usage admin page. Reads across every user's api_usage_log subcollection
    via collection_group. IMPORTANT: keep this unordered/unfiltered -- adding
    .order_by()/.where() here requires creating a collection-group index in
    the Firestore console first, or it fails with FAILED_PRECONDITION. Sorting/
    aggregation happens in pandas after fetching (see app/pages/9_API_Usage.py)."""
    docs = db.collection_group("api_usage_log").stream()
    return [d.to_dict() for d in docs]

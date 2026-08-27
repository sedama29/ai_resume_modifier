PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS master_resume_versions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    owner_uid TEXT NOT NULL,
    uploaded_at TEXT NOT NULL,
    source_file_path TEXT NOT NULL,
    content_model_json TEXT NOT NULL,
    skeleton_hash TEXT NOT NULL,
    is_active INTEGER NOT NULL DEFAULT 1
);

CREATE TABLE IF NOT EXISTS candidate_profile (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    owner_uid TEXT NOT NULL,
    name TEXT NOT NULL,
    phone TEXT,
    email TEXT,
    github TEXT,
    location TEXT,
    years_experience REAL,
    education_summary TEXT,
    visa_status_text TEXT,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS job_applications (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    owner_uid TEXT NOT NULL,
    master_resume_version_id INTEGER NOT NULL REFERENCES master_resume_versions(id),
    company TEXT,
    job_title TEXT,
    job_url TEXT,
    jd_text TEXT NOT NULL,
    jd_source TEXT NOT NULL CHECK (jd_source IN ('url', 'pasted')),
    status TEXT NOT NULL DEFAULT 'draft' CHECK (
        status IN (
            'draft', 'analyzed', 'eligibility_checked', 'matched',
            'questions_pending', 'reviewed', 'generated', 'not_pursuing'
        )
    ),
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS job_analysis_results (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    application_id INTEGER NOT NULL REFERENCES job_applications(id),
    required_skills_json TEXT,
    preferred_skills_json TEXT,
    key_responsibilities_json TEXT,
    required_experience_years REAL,
    required_education TEXT,
    work_auth_excerpts_json TEXT,
    raw_llm_response_json TEXT,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS eligibility_results (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    application_id INTEGER NOT NULL REFERENCES job_applications(id),
    work_auth_category TEXT NOT NULL CHECK (
        work_auth_category IN (
            'explicitly_compatible', 'potentially_compatible', 'potential_issue',
            'explicit_restriction', 'not_mentioned', 'needs_verification'
        )
    ),
    work_auth_reasoning TEXT,
    work_auth_evidence_json TEXT,
    experience_gap_years REAL,
    experience_gap_assessment TEXT,
    education_match TEXT CHECK (education_match IN ('meets', 'exceeds', 'below', 'unclear')),
    overall_recommendation TEXT CHECK (
        overall_recommendation IN (
            'strong_fit', 'proceed', 'proceed_with_caution',
            'do_not_apply', 'insufficient_information'
        )
    ),
    raw_llm_response_json TEXT,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS match_results (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    application_id INTEGER NOT NULL REFERENCES job_applications(id),
    skills_present_json TEXT,
    skills_missing_json TEXT,
    skills_implied_json TEXT,
    match_score REAL,
    raw_llm_response_json TEXT,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS followup_questions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    application_id INTEGER NOT NULL REFERENCES job_applications(id),
    question_text TEXT NOT NULL,
    related_skill TEXT,
    importance TEXT CHECK (importance IN ('required', 'preferred')),
    order_index INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS followup_answers (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    question_id INTEGER NOT NULL REFERENCES followup_questions(id),
    application_id INTEGER NOT NULL REFERENCES job_applications(id),
    answer_bool INTEGER,
    answer_detail_text TEXT,
    answered_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS resume_versions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    application_id INTEGER NOT NULL REFERENCES job_applications(id),
    version_number INTEGER NOT NULL,
    name TEXT NOT NULL,
    content_model_json TEXT NOT NULL,
    tex_file_path TEXT,
    pdf_file_path TEXT,
    compile_success INTEGER,
    compile_log_text TEXT,
    is_overwrite_of INTEGER REFERENCES resume_versions(id),
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS generated_changes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    resume_version_id INTEGER NOT NULL REFERENCES resume_versions(id),
    region TEXT NOT NULL CHECK (region IN ('summary', 'experience', 'skills')),
    entry_ref TEXT,
    change_type TEXT NOT NULL CHECK (
        change_type IN ('unchanged', 'reworded', 'reordered', 'added', 'removed')
    ),
    source_answer_id INTEGER REFERENCES followup_answers(id),
    accepted INTEGER NOT NULL DEFAULT 0,
    old_text TEXT,
    new_text TEXT
);

CREATE TABLE IF NOT EXISTS overleaf_sync (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    resume_version_id INTEGER NOT NULL REFERENCES resume_versions(id),
    overleaf_project_url TEXT,
    sync_status TEXT NOT NULL DEFAULT 'not_synced' CHECK (
        sync_status IN ('not_synced', 'pending', 'synced', 'failed')
    ),
    last_synced_at TEXT,
    error_text TEXT
);

CREATE TABLE IF NOT EXISTS api_usage_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    owner_uid TEXT NOT NULL,
    schema_name TEXT NOT NULL,
    model TEXT NOT NULL,
    prompt_tokens INTEGER,
    completion_tokens INTEGER,
    total_tokens INTEGER,
    created_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_job_applications_status ON job_applications(status);
CREATE INDEX IF NOT EXISTS idx_resume_versions_application ON resume_versions(application_id);
CREATE INDEX IF NOT EXISTS idx_followup_answers_application ON followup_answers(application_id);
CREATE INDEX IF NOT EXISTS idx_master_resume_versions_owner ON master_resume_versions(owner_uid);
CREATE UNIQUE INDEX IF NOT EXISTS idx_candidate_profile_owner ON candidate_profile(owner_uid);
CREATE INDEX IF NOT EXISTS idx_job_applications_owner ON job_applications(owner_uid);
CREATE INDEX IF NOT EXISTS idx_api_usage_owner ON api_usage_log(owner_uid);
CREATE INDEX IF NOT EXISTS idx_api_usage_created_at ON api_usage_log(created_at);

"""JSON Schemas for the 5 Groq structured-output calls. Kept as plain dicts
(not Pydantic) since they're passed straight to both the Groq API and
jsonschema.validate()."""

JOB_ANALYSIS_SCHEMA = {
    "type": "object",
    "properties": {
        "company": {"type": "string"},
        "job_title": {"type": "string"},
        "location": {"type": "string"},
        "employment_type": {"type": "string"},
        "required_experience_years": {"type": ["number", "null"]},
        "required_experience_summary": {"type": "string"},
        "required_education": {"type": "string"},
        "required_skills": {"type": "array", "items": {"type": "string"}},
        "preferred_skills": {"type": "array", "items": {"type": "string"}},
        "key_responsibilities": {"type": "array", "items": {"type": "string"}},
        "work_authorization_text_excerpts": {"type": "array", "items": {"type": "string"}},
    },
    "required": [
        "company", "job_title", "required_skills", "preferred_skills",
        "key_responsibilities", "work_authorization_text_excerpts",
    ],
}

ELIGIBILITY_SCHEMA = {
    "type": "object",
    "properties": {
        "work_auth_category": {
            "type": "string",
            "enum": [
                "explicitly_compatible", "potentially_compatible", "potential_issue",
                "explicit_restriction", "not_mentioned", "needs_verification",
            ],
        },
        "work_auth_reasoning": {"type": "string"},
        "work_auth_evidence_quotes": {"type": "array", "items": {"type": "string"}},
        "experience_gap_years": {"type": ["number", "null"]},
        "experience_gap_assessment": {"type": "string"},
        "education_match": {"type": "string", "enum": ["meets", "exceeds", "below", "unclear"]},
        "overall_recommendation": {
            "type": "string",
            "enum": ["strong_fit", "proceed", "proceed_with_caution", "do_not_apply", "insufficient_information"],
        },
        "recommendation_reasoning": {"type": "string"},
        "requirement_checks": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "category": {
                        "type": "string",
                        "enum": [
                            "experience", "education", "required_skills", "work_authorization",
                            "h1b_sponsorship", "citizenship_residency", "security_clearance", "other",
                        ],
                    },
                    "label": {"type": "string"},
                    "status": {
                        "type": "string",
                        "enum": ["meets", "does_not_meet", "potential_issue", "not_mentioned", "needs_verification"],
                    },
                    "detail": {"type": "string"},
                },
                "required": ["category", "status", "detail"],
            },
        },
    },
    "required": [
        "work_auth_category", "work_auth_reasoning", "education_match",
        "overall_recommendation", "recommendation_reasoning", "requirement_checks",
    ],
}

SKILL_MATCH_SCHEMA = {
    "type": "object",
    "properties": {
        "present": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {"skill": {"type": "string"}, "evidence": {"type": "string"}},
                "required": ["skill"],
            },
        },
        "missing": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {"skill": {"type": "string"}, "importance": {"type": "string", "enum": ["required", "preferred"]}},
                "required": ["skill"],
            },
        },
        "potentially_implied": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "skill": {"type": "string"},
                    "reasoning": {"type": "string"},
                    "importance": {"type": "string", "enum": ["required", "preferred"]},
                },
                "required": ["skill", "reasoning"],
            },
        },
        "match_score": {"type": "number"},
    },
    "required": ["present", "missing", "potentially_implied", "match_score"],
}

FOLLOWUP_QUESTIONS_SCHEMA = {
    "type": "object",
    "properties": {
        "questions": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "question_id": {"type": "string"},
                    "skill": {"type": "string"},
                    "question_text": {"type": "string"},
                    "importance": {"type": "string", "enum": ["required", "preferred"]},
                },
                "required": ["question_id", "skill", "question_text"],
            },
        }
    },
    "required": ["questions"],
}

_CHANGE_TYPE_ENUM = {"type": "string", "enum": ["unchanged", "reworded", "reordered", "added", "removed"]}

RESUME_REWRITE_SCHEMA = {
    "type": "object",
    "properties": {
        "summary": {
            "type": "object",
            "properties": {"text": {"type": "string"}, "change": _CHANGE_TYPE_ENUM},
            "required": ["text", "change"],
        },
        "experience": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "entry_id": {"type": "string"},
                    "bullets": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "bullet_id": {"type": "string"},
                                "text": {"type": "string"},
                                "change": _CHANGE_TYPE_ENUM,
                                "source_answer_id": {"type": ["string", "null"]},
                            },
                            "required": ["bullet_id", "text", "change"],
                        },
                    },
                },
                "required": ["entry_id", "bullets"],
            },
        },
        "skills": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "item_id": {"type": "string"},
                    "text": {"type": "string"},
                    "change": _CHANGE_TYPE_ENUM,
                    "source_answer_id": {"type": ["string", "null"]},
                },
                "required": ["item_id", "text", "change"],
            },
        },
    },
    "required": ["summary", "experience", "skills"],
}

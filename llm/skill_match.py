import json
from sqlite3 import Connection

from core.resume_model import ContentModel
from llm.groq_client import call_structured
from llm.prompts import build_candidate_context, skill_match_system_prompt
from llm.schemas import SKILL_MATCH_SCHEMA


def match_resume_to_job(
    content_model: ContentModel, job_analysis: dict, candidate_profile: dict,
    conn: Connection, owner_uid: str,
) -> dict:
    candidate_context = build_candidate_context(candidate_profile)
    resume_summary_for_matching = {
        "summary": content_model.summary.text,
        "experience_bullets": [b.text for e in content_model.experience for b in e.bullets],
        "skills": [s.text for s in content_model.skills],
    }
    user_prompt = (
        "Resume content:\n"
        f"{json.dumps(resume_summary_for_matching, indent=2)}\n\n"
        "Job's required and preferred skills:\n"
        f"required_skills: {job_analysis.get('required_skills', [])}\n"
        f"preferred_skills: {job_analysis.get('preferred_skills', [])}\n"
    )
    return call_structured(
        system_prompt=skill_match_system_prompt(candidate_context),
        user_prompt=user_prompt,
        schema=SKILL_MATCH_SCHEMA,
        schema_name="skill_match",
        conn=conn,
        owner_uid=owner_uid,
    )

import json
from sqlite3 import Connection

from llm.groq_client import call_structured
from llm.prompts import build_candidate_context, eligibility_system_prompt
from llm.schemas import ELIGIBILITY_SCHEMA


def check_eligibility(job_analysis: dict, candidate_profile: dict, conn: Connection, owner_uid: str) -> dict:
    candidate_context = build_candidate_context(candidate_profile)
    user_prompt = (
        "Job analysis (structured):\n"
        f"{json.dumps(job_analysis, indent=2)}\n\n"
        "Assess the candidate's eligibility for this role."
    )
    return call_structured(
        system_prompt=eligibility_system_prompt(candidate_context),
        user_prompt=user_prompt,
        schema=ELIGIBILITY_SCHEMA,
        schema_name="eligibility",
        conn=conn,
        owner_uid=owner_uid,
    )

from sqlite3 import Connection

from llm.groq_client import call_structured
from llm.prompts import job_analysis_system_prompt
from llm.schemas import JOB_ANALYSIS_SCHEMA


def analyze_job_description(jd_text: str, conn: Connection, owner_uid: str) -> dict:
    return call_structured(
        system_prompt=job_analysis_system_prompt(),
        user_prompt=f"Job posting text:\n\n{jd_text}",
        schema=JOB_ANALYSIS_SCHEMA,
        schema_name="job_analysis",
        conn=conn,
        owner_uid=owner_uid,
    )

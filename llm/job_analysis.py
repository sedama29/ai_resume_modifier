from google.cloud.firestore_v1 import Client

from llm.groq_client import call_structured
from llm.prompts import job_analysis_system_prompt
from llm.schemas import JOB_ANALYSIS_SCHEMA


def analyze_job_description(jd_text: str, db: Client, owner_uid: str) -> dict:
    return call_structured(
        system_prompt=job_analysis_system_prompt(),
        user_prompt=f"Job posting text:\n\n{jd_text}",
        schema=JOB_ANALYSIS_SCHEMA,
        schema_name="job_analysis",
        db=db,
        owner_uid=owner_uid,
    )

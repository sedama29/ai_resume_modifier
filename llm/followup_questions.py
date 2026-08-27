import json
from sqlite3 import Connection

from llm.groq_client import call_structured
from llm.prompts import followup_questions_system_prompt
from llm.schemas import FOLLOWUP_QUESTIONS_SCHEMA


def generate_followup_questions(match_result: dict, conn: Connection, owner_uid: str) -> dict:
    candidates = match_result.get("missing", []) + match_result.get("potentially_implied", [])
    user_prompt = f"Skills that may need a follow-up question:\n{json.dumps(candidates, indent=2)}"
    return call_structured(
        system_prompt=followup_questions_system_prompt(),
        user_prompt=user_prompt,
        schema=FOLLOWUP_QUESTIONS_SCHEMA,
        schema_name="followup_questions",
        conn=conn,
        owner_uid=owner_uid,
    )

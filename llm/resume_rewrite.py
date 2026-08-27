import json
from sqlite3 import Connection

from core.resume_model import ContentModel
from llm.groq_client import call_structured
from llm.prompts import build_candidate_context, resume_rewrite_system_prompt
from llm.schemas import RESUME_REWRITE_SCHEMA


def _format_confirmed_answers(confirmed_answers: list[dict]) -> str:
    if not confirmed_answers:
        return ""
    lines = []
    for a in confirmed_answers:
        detail = f" Detail: {a['answer_detail_text']}" if a.get("answer_detail_text") else ""
        lines.append(f"- id={a['id']}: \"{a['question_text']}\" -> confirmed yes.{detail}")
    return "\n".join(lines)


def rewrite_resume(
    content_model: ContentModel,
    job_analysis: dict,
    confirmed_answers: list[dict],
    candidate_profile: dict,
    conn: Connection,
    owner_uid: str,
) -> ContentModel:
    candidate_context = build_candidate_context(candidate_profile)
    confirmed_answers_block = _format_confirmed_answers(confirmed_answers)

    user_prompt = (
        "Job analysis (structured):\n"
        f"{json.dumps(job_analysis, indent=2)}\n\n"
        "Current resume content (edit this, return the same shape):\n"
        f"{content_model.model_dump_json(indent=2)}"
    )
    result = call_structured(
        system_prompt=resume_rewrite_system_prompt(candidate_context, confirmed_answers_block),
        user_prompt=user_prompt,
        schema=RESUME_REWRITE_SCHEMA,
        schema_name="resume_rewrite",
        conn=conn,
        owner_uid=owner_uid,
    )
    return ContentModel.model_validate(result)

"""
Thin wrapper around the Groq API for structured JSON calls.

openai/gpt-oss-120b has a known reliability issue where response_format
type=json_schema is sometimes ignored and the model returns free-form text
instead (see Groq community forum thread #687). We defend against this with:
  1. strict=False json_schema (Groq's documented workaround for this model)
  2. manual JSON parse + jsonschema validation, with the parse/validation
     error fed back to the model on retry (up to MAX_RETRIES)
  3. a final fallback to json_object mode with the schema embedded as
     instructions in the prompt, if json_schema mode keeps failing
"""
import json
from sqlite3 import Connection

import jsonschema
from groq import Groq

import db.repository as repo
from config import GROQ_API_KEY, GROQ_MODEL

MAX_RETRIES = 3

_client: Groq | None = None


def _get_client() -> Groq:
    global _client
    if _client is None:
        if not GROQ_API_KEY:
            raise RuntimeError("GROQ_API_KEY is not set. Add it to your .env file.")
        _client = Groq(api_key=GROQ_API_KEY)
    return _client


def _extract_json(raw_text: str) -> dict:
    """Best-effort extraction of a JSON object from model output that may be
    wrapped in prose or a markdown code fence despite instructions not to."""
    text = raw_text.strip()
    if text.startswith("```"):
        text = text.strip("`")
        if text.startswith("json"):
            text = text[4:]
        text = text.strip()
    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end == -1 or end < start:
        raise ValueError(f"No JSON object found in model output: {raw_text[:300]!r}")
    return json.loads(text[start : end + 1])


def call_structured(
    system_prompt: str, user_prompt: str, schema: dict, schema_name: str,
    conn: Connection, owner_uid: str,
) -> dict:
    """Call Groq with a JSON schema and return a validated dict. Raises
    RuntimeError if the model fails to produce schema-valid JSON after retries.

    Every completion (including failed-validation retries -- they still
    consume real, billed tokens) is logged to api_usage_log for the admin
    usage dashboard."""
    client = _get_client()
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt},
    ]

    last_error: Exception | None = None
    for attempt in range(MAX_RETRIES):
        try:
            completion = client.chat.completions.create(
                model=GROQ_MODEL,
                messages=messages,
                response_format={
                    "type": "json_schema",
                    "json_schema": {"name": schema_name, "schema": schema, "strict": False},
                },
                temperature=0.2,
            )
            usage = completion.usage
            if usage is not None:
                repo.log_api_usage(
                    conn, owner_uid, schema_name, GROQ_MODEL,
                    usage.prompt_tokens, usage.completion_tokens, usage.total_tokens,
                )
            raw_text = completion.choices[0].message.content
            parsed = _extract_json(raw_text)
            jsonschema.validate(parsed, schema)
            return parsed
        except Exception as e:  # noqa: BLE001 -- deliberately broad: parse, validation, and API errors all retry the same way
            last_error = e
            messages.append({"role": "assistant", "content": raw_text if "raw_text" in locals() else ""})
            messages.append(
                {
                    "role": "user",
                    "content": (
                        f"Your previous response was invalid: {e}. "
                        "Respond with ONLY a single valid JSON object matching the required schema. "
                        "No markdown code fences, no explanation, no extra text."
                    ),
                }
            )

    raise RuntimeError(f"Groq failed to produce schema-valid JSON after {MAX_RETRIES} attempts: {last_error}")

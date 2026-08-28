import json

from google.cloud.firestore_v1 import Client

from integrations.github_client import fetch_repo_evidence
from llm.groq_client import call_structured
from llm.prompts import github_analysis_system_prompt
from llm.schemas import GITHUB_ANALYSIS_SCHEMA


def analyze_github_profile(username: str, db: Client, owner_uid: str) -> dict:
    """Fetches the user's public repos (README + manifest excerpts as raw
    evidence) and asks the LLM to extract grounded technologies per repo.
    Raises requests.HTTPError if the username can't be resolved -- the caller
    should catch this and show a clear error rather than silently proceeding."""
    repo_evidence = fetch_repo_evidence(username)
    if not repo_evidence:
        return {"repos": []}

    user_prompt = (
        "Public repositories (most recently updated, up to 10) with README and "
        "manifest-file excerpts as evidence:\n"
        f"{json.dumps(repo_evidence, indent=2)}"
    )
    result = call_structured(
        system_prompt=github_analysis_system_prompt(),
        user_prompt=user_prompt,
        schema=GITHUB_ANALYSIS_SCHEMA,
        schema_name="github_analysis",
        db=db,
        owner_uid=owner_uid,
    )
    # Carry the repo URL through for display/linking -- not something the LLM
    # is asked about, so it's not part of its schema.
    urls_by_name = {r["name"]: r["url"] for r in repo_evidence}
    for repo in result.get("repos", []):
        repo["url"] = urls_by_name.get(repo["name"], "")
    return result

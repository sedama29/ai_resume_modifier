"""Thin, unauthenticated client for the public GitHub REST API. Fetches a
user's public repos plus README and common dependency-manifest excerpts as
raw evidence -- technology extraction from that evidence is the LLM's job
(llm/github_analysis.py), never done here."""
import re

import requests

_HEADERS = {"Accept": "application/vnd.github+json", "User-Agent": "ai-resume-modifier"}
_RAW_HEADERS = {**_HEADERS, "Accept": "application/vnd.github.raw"}
_TIMEOUT_SECONDS = 15
_MAX_REPOS = 10
_README_CHARS = 2500
_MANIFEST_CHARS = 1500
_MANIFEST_FILES = ["requirements.txt", "package.json", "pyproject.toml", "Pipfile", "go.mod", "Cargo.toml"]


def parse_github_username(url_or_username: str) -> str:
    """Accepts either a bare username or a full profile URL."""
    text = url_or_username.strip().rstrip("/")
    match = re.search(r"github\.com/([A-Za-z0-9-]+)", text)
    return match.group(1) if match else text


def fetch_public_repos(username: str) -> list[dict]:
    """The most recently updated public, non-fork repos owned by this user --
    capped at _MAX_REPOS to keep the downstream LLM prompt a reasonable size.
    Raises requests.HTTPError (e.g. 404 for an unknown username) -- callers
    should catch this and show a clear error."""
    response = requests.get(
        f"https://api.github.com/users/{username}/repos",
        params={"sort": "updated", "per_page": 30, "type": "owner"},
        headers=_HEADERS, timeout=_TIMEOUT_SECONDS,
    )
    response.raise_for_status()
    repos = [r for r in response.json() if not r.get("fork")]
    return repos[:_MAX_REPOS]


def fetch_readme_text(owner: str, repo: str) -> str | None:
    try:
        response = requests.get(
            f"https://api.github.com/repos/{owner}/{repo}/readme",
            headers=_RAW_HEADERS, timeout=_TIMEOUT_SECONDS,
        )
        if response.status_code != 200:
            return None
        return response.text[:_README_CHARS]
    except requests.RequestException:
        return None


def fetch_manifest_excerpts(owner: str, repo: str) -> dict[str, str]:
    """Best-effort fetch of common dependency-manifest files -- a missing file
    is silently skipped (a 404 here is completely normal), not an error."""
    excerpts = {}
    for filename in _MANIFEST_FILES:
        try:
            response = requests.get(
                f"https://api.github.com/repos/{owner}/{repo}/contents/{filename}",
                headers=_RAW_HEADERS, timeout=_TIMEOUT_SECONDS,
            )
            if response.status_code == 200 and response.text:
                excerpts[filename] = response.text[:_MANIFEST_CHARS]
        except requests.RequestException:
            continue
    return excerpts


def fetch_repo_evidence(username: str) -> list[dict]:
    """Raw evidence only (name, description, language, topics, README excerpt,
    manifest excerpts) for the user's most recently updated public repos --
    no technology extraction happens here."""
    repos = fetch_public_repos(username)
    evidence = []
    for r in repos:
        owner = r["owner"]["login"]
        name = r["name"]
        evidence.append(
            {
                "name": name,
                "description": r.get("description") or "",
                "url": r.get("html_url", ""),
                "language": r.get("language") or "",
                "topics": r.get("topics") or [],
                "readme_excerpt": fetch_readme_text(owner, name) or "",
                "manifest_excerpts": fetch_manifest_excerpts(owner, name),
            }
        )
    return evidence

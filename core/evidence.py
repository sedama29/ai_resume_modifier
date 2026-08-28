"""Cross-references a job's required/preferred skills against every source of
candidate evidence -- the master resume (via the existing skill_match result),
previously-confirmed GitHub/learning experiences saved to the profile,
unconfirmed GitHub-analysis findings, and current-learning entries.

Deliberately NOT an LLM call: this is a set of deterministic lookups over data
already produced elsewhere, which is both cheaper and more trustworthy than
asking a model to do table lookups. The one rule that matters everywhere else
in this app applies here too -- a row here is a *lead to verify*, never
something the resume can act on until the candidate confirms it."""
from dataclasses import dataclass, field

TIER_RANK = {
    "professional": 1,
    "research": 2,
    "project": 3,
    "github_project": 4,
    "academic": 5,
    "coursework": 6,
    "none": 7,
}

TIER_LABELS = {
    "professional": "Professional",
    "research": "Research/Work",
    "project": "Project",
    "github_project": "GitHub Project",
    "academic": "Academic",
    "coursework": "Learning",
    "none": "Not confirmed",
}


@dataclass
class EvidenceRow:
    skill: str
    importance: str  # required | preferred
    tier: str
    found_in: str  # human-readable source label
    confirmed: bool
    detail: dict = field(default_factory=dict)  # raw source detail (repo/learning item), for the follow-up UI


def _norm(s: str) -> str:
    return s.strip().lower()


def build_evidence_rows(job_analysis: dict, match_result: dict, candidate_profile: dict) -> list[EvidenceRow]:
    present_skills = {_norm(p["skill"]) for p in (match_result.get("present") or [])}

    confirmed_by_skill: dict[str, dict] = {}
    for c in candidate_profile.get("confirmed_experiences") or []:
        confirmed_by_skill.setdefault(_norm(c["technology"]), c)

    github_by_tech: dict[str, dict] = {}
    for repo in (candidate_profile.get("github_analysis") or {}).get("repos") or []:
        for tech in repo.get("technologies") or []:
            github_by_tech.setdefault(
                _norm(tech["name"]), {"repo": repo["name"], "evidence": tech.get("evidence", "")}
            )

    learning_by_tech: dict[str, dict] = {}
    for item in candidate_profile.get("current_learning") or []:
        for tech in item.get("technologies") or []:
            learning_by_tech.setdefault(_norm(tech), item)

    rows: list[EvidenceRow] = []
    required = job_analysis.get("required_skills") or []
    preferred = job_analysis.get("preferred_skills") or []
    for skill, importance in [(s, "required") for s in required] + [(s, "preferred") for s in preferred]:
        key = _norm(skill)

        if key in present_skills:
            rows.append(EvidenceRow(skill, importance, "professional", "Master Resume", True))
            continue

        if key in confirmed_by_skill:
            c = confirmed_by_skill[key]
            rows.append(EvidenceRow(skill, importance, c["tier"], c.get("source_detail") or "Confirmed", True, c))
            continue

        in_github = github_by_tech.get(key)
        in_learning = learning_by_tech.get(key)
        if in_github and in_learning:
            rows.append(EvidenceRow(skill, importance, "github_project", f"{in_github['repo']} + Learning", False, in_github))
        elif in_github:
            rows.append(EvidenceRow(skill, importance, "github_project", in_github["repo"], False, in_github))
        elif in_learning:
            rows.append(EvidenceRow(skill, importance, "coursework", in_learning.get("title") or "Current learning", False, in_learning))
        else:
            rows.append(EvidenceRow(skill, importance, "none", "No evidence", False))

    return rows


def unconfirmed_discoveries(rows: list[EvidenceRow]) -> list[EvidenceRow]:
    """Rows with real (GitHub/learning) evidence not yet confirmed by the
    candidate -- what the Follow-up Questions page's second phase asks about."""
    return [r for r in rows if not r.confirmed and r.tier in ("github_project", "coursework")]

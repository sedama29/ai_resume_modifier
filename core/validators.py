"""
The real fabrication-prevention layer -- enforced in Python, not trusted from
prompting or from Groq's structured-output schema alone. Every rule here
answers a concrete "how could the LLM lie" question:

- entry_id / item_id whitelist: the LLM can only edit bullets/skills that
  already existed, or add new ones with a confirmed source. It can never
  delete or invent a whole job/entry.
- source_answer_id integrity: any 'added' item must cite a real confirmed
  ("yes") follow-up answer for this application, or it's dropped.
- numeric-fidelity check: a new number appearing in rewritten text that
  wasn't in the original and isn't explained by a confirmed answer is
  flagged (not dropped) so a human reviews it on the Review Changes screen.
- new-term check: a rewording can legally surface a fact that was already
  true elsewhere in the resume (e.g. a skill mentioned only in the summary
  getting pulled into the skills line too) -- but it can just as easily
  smuggle in a skill that was never mentioned ANYWHERE. Any capitalized/
  acronym-like term appearing in rewritten text that isn't in that item's
  original text AND isn't anywhere else in the original resume is flagged.
- defensive fallback: if the LLM drops bullets/an entry entirely, the
  original is used instead of rendering something empty.
"""
import re
from dataclasses import dataclass

from core.resume_model import ContentModel, ExperienceEntry, SkillLine, Summary

_NUMBER_RE = re.compile(r"\d+(?:,\d{3})*(?:\.\d+)?%?\+?")
_TERM_RE = re.compile(r"[A-Z][A-Za-z0-9+#.]*")


@dataclass
class ValidationWarning:
    region: str
    ref: str
    kind: str  # unknown_id | missing_source_answer | numeric_mismatch | unverified_new_term | fallback_to_original
    message: str


def _numbers_in(text: str) -> set[str]:
    return set(_NUMBER_RE.findall(text))


def _terms_in(text: str) -> set[str]:
    """Capitalized/acronym-like tokens, excluding sentence-initial words
    (capitalization there is grammatical, not a signal of a proper noun)."""
    terms = set()
    for m in _TERM_RE.finditer(text):
        start = m.start()
        prefix = text[max(0, start - 2) : start]
        if start == 0 or prefix.endswith(". ") or prefix.endswith(".\n"):
            continue
        terms.add(m.group(0))
    return terms


def _known_terms(content_model: ContentModel) -> set[str]:
    """Every capitalized/acronym-like term appearing anywhere in the original
    resume -- rewording one bullet to surface a term that's truthfully
    elsewhere in the resume is allowed; anything outside this set is not."""
    chunks = [content_model.summary.text]
    chunks += [b.text for e in content_model.experience for b in e.bullets]
    chunks += [s.text for s in content_model.skills]
    return _terms_in(" ".join(chunks))


def validate_and_merge(
    original: ContentModel, llm_output: ContentModel, confirmed_answer_ids: set[str]
) -> tuple[ContentModel, list[ValidationWarning]]:
    warnings: list[ValidationWarning] = []
    known_terms = _known_terms(original)

    merged_summary = _merge_summary(original.summary, llm_output.summary, known_terms, warnings)
    merged_experience = _merge_experience(
        original.experience, llm_output.experience, confirmed_answer_ids, known_terms, warnings
    )
    merged_skills = _merge_skills(original.skills, llm_output.skills, confirmed_answer_ids, known_terms, warnings)

    return (
        ContentModel(summary=merged_summary, experience=merged_experience, skills=merged_skills),
        warnings,
    )


def _flag_new_terms(region: str, ref: str, orig_text: str, new_text: str, known_terms: set[str], warnings: list[ValidationWarning]) -> None:
    new_terms = _terms_in(new_text) - _terms_in(orig_text) - known_terms
    if new_terms:
        warnings.append(
            ValidationWarning(
                region, ref, "unverified_new_term",
                f"New term(s) {sorted(new_terms)} not present anywhere in the original resume -- verify before accepting.",
            )
        )


def _merge_summary(original: Summary, llm: Summary | None, known_terms: set[str], warnings: list[ValidationWarning]) -> Summary:
    if llm is None or not llm.text.strip():
        warnings.append(ValidationWarning("summary", "summary", "fallback_to_original", "LLM returned empty summary; kept original."))
        return original
    new_numbers = _numbers_in(llm.text) - _numbers_in(original.text)
    if new_numbers:
        warnings.append(
            ValidationWarning(
                "summary", "summary", "numeric_mismatch",
                f"New number(s) {sorted(new_numbers)} in rewritten summary not present in the original -- verify before accepting.",
            )
        )
    _flag_new_terms("summary", "summary", original.text, llm.text, known_terms, warnings)
    return Summary(text=llm.text, change=llm.change)


def _merge_experience(
    original: list[ExperienceEntry],
    llm: list[ExperienceEntry],
    confirmed_answer_ids: set[str],
    known_terms: set[str],
    warnings: list[ValidationWarning],
) -> list[ExperienceEntry]:
    original_by_id = {e.entry_id: e for e in original}
    llm_by_id = {e.entry_id: e for e in llm}

    merged: list[ExperienceEntry] = []
    for entry_id, orig_entry in original_by_id.items():
        llm_entry = llm_by_id.get(entry_id)
        if llm_entry is None:
            warnings.append(
                ValidationWarning("experience", entry_id, "fallback_to_original", "LLM omitted this entire job entry; kept original.")
            )
            merged.append(orig_entry)
            continue

        merged_bullets = _merge_bullets(orig_entry, llm_entry, confirmed_answer_ids, known_terms, warnings)
        # org_label is always the original's -- never trust the LLM's echo of org/title.
        merged.append(ExperienceEntry(entry_id=entry_id, org_label=orig_entry.org_label, bullets=merged_bullets))

    # Any entry_id in the LLM output not present originally is a fabricated job -- dropped.
    for entry_id in llm_by_id:
        if entry_id not in original_by_id:
            warnings.append(
                ValidationWarning("experience", entry_id, "unknown_id", "LLM referenced a job entry that doesn't exist in the master resume; discarded.")
            )

    return merged


def _merge_bullets(orig_entry: ExperienceEntry, llm_entry: ExperienceEntry, confirmed_answer_ids, known_terms, warnings):
    orig_by_id = {b.bullet_id: b for b in orig_entry.bullets}

    if not llm_entry.bullets:
        warnings.append(
            ValidationWarning("experience", orig_entry.entry_id, "fallback_to_original", "LLM returned no bullets for this entry; kept original bullets.")
        )
        return list(orig_entry.bullets)

    merged = []
    for bullet in llm_entry.bullets:
        orig_bullet = orig_by_id.get(bullet.bullet_id)

        if orig_bullet is None:
            # A genuinely new bullet -- must be explicitly marked 'added' with a
            # confirmed source, otherwise it's an unexplained fabrication.
            if bullet.change != "added" or bullet.source_answer_id not in confirmed_answer_ids:
                warnings.append(
                    ValidationWarning(
                        "experience", f"{orig_entry.entry_id}:{bullet.bullet_id}", "missing_source_answer",
                        "New bullet has no valid confirmed-answer source; discarded.",
                    )
                )
                continue
            merged.append(bullet)
            continue

        if bullet.change == "added" and bullet.source_answer_id not in confirmed_answer_ids:
            warnings.append(
                ValidationWarning(
                    "experience", f"{orig_entry.entry_id}:{bullet.bullet_id}", "missing_source_answer",
                    "Bullet marked 'added' has no valid confirmed-answer source; original text kept instead.",
                )
            )
            merged.append(orig_bullet)
            continue

        new_numbers = _numbers_in(bullet.text) - _numbers_in(orig_bullet.text)
        if new_numbers:
            warnings.append(
                ValidationWarning(
                    "experience", f"{orig_entry.entry_id}:{bullet.bullet_id}", "numeric_mismatch",
                    f"New number(s) {sorted(new_numbers)} not present in the original bullet -- verify before accepting.",
                )
            )
        _flag_new_terms(
            "experience", f"{orig_entry.entry_id}:{bullet.bullet_id}", orig_bullet.text, bullet.text, known_terms, warnings
        )
        merged.append(bullet)

    return merged


def _merge_skills(
    original: list[SkillLine], llm: list[SkillLine], confirmed_answer_ids: set[str], known_terms: set[str], warnings: list[ValidationWarning]
) -> list[SkillLine]:
    if not llm:
        warnings.append(ValidationWarning("skills", "skills", "fallback_to_original", "LLM returned no skills; kept original list."))
        return list(original)

    orig_by_id = {s.item_id: s for s in original}
    merged = []
    for skill in llm:
        orig_skill = orig_by_id.get(skill.item_id)

        if orig_skill is None:
            if skill.change != "added" or skill.source_answer_id not in confirmed_answer_ids:
                warnings.append(
                    ValidationWarning("skills", f"skills:{skill.item_id}", "missing_source_answer", "New skill line has no valid confirmed-answer source; discarded.")
                )
                continue
            merged.append(skill)
            continue

        if skill.change == "added" and skill.source_answer_id not in confirmed_answer_ids:
            warnings.append(
                ValidationWarning("skills", f"skills:{skill.item_id}", "missing_source_answer", "Skill line marked 'added' has no valid confirmed-answer source; original kept instead.")
            )
            merged.append(orig_skill)
            continue

        _flag_new_terms("skills", f"skills:{skill.item_id}", orig_skill.text, skill.text, known_terms, warnings)
        merged.append(skill)

    return merged

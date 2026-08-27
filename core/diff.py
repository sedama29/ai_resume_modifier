"""Computes a human-readable diff between the original and merged content
models for the Review Changes screen: Added / Reworded / Removed per item,
plus a coarse per-section Reordered flag."""
from dataclasses import dataclass

from core.resume_model import ContentModel


@dataclass
class ChangeEntry:
    region: str  # "summary" | "experience" | "skills"
    ref: str  # human-readable location, e.g. "exp1:exp1-b3" or "skill4"
    change_type: str  # "added" | "reworded" | "removed"
    old_text: str | None
    new_text: str | None
    source_answer_id: int | None = None


@dataclass
class SectionDiff:
    changes: list[ChangeEntry]
    reordered_sections: list[str]  # e.g. ["exp1", "skills"]


def _filtered_order(order: list[str], keep: set[str]) -> list[str]:
    return [x for x in order if x in keep]


def _diff_item_list(region: str, section_ref: str, original_items, merged_items) -> tuple[list[ChangeEntry], bool]:
    orig_by_id = {getattr(i, "bullet_id", None) or getattr(i, "item_id", None): i for i in original_items}
    merged_by_id = {getattr(i, "bullet_id", None) or getattr(i, "item_id", None): i for i in merged_items}

    changes = []
    for item_id, item in merged_by_id.items():
        orig_item = orig_by_id.get(item_id)
        if orig_item is None:
            changes.append(ChangeEntry(region, f"{section_ref}:{item_id}", "added", None, item.text, item.source_answer_id))
        elif orig_item.text != item.text:
            changes.append(ChangeEntry(region, f"{section_ref}:{item_id}", "reworded", orig_item.text, item.text))

    for item_id, orig_item in orig_by_id.items():
        if item_id not in merged_by_id:
            changes.append(ChangeEntry(region, f"{section_ref}:{item_id}", "removed", orig_item.text, None))

    common_ids = set(orig_by_id) & set(merged_by_id)
    orig_order = _filtered_order(list(orig_by_id.keys()), common_ids)
    merged_order = _filtered_order(list(merged_by_id.keys()), common_ids)
    reordered = orig_order != merged_order

    return changes, reordered


def compute_diff(original: ContentModel, merged: ContentModel) -> SectionDiff:
    all_changes: list[ChangeEntry] = []
    reordered_sections: list[str] = []

    if original.summary.text != merged.summary.text:
        all_changes.append(ChangeEntry("summary", "summary", "reworded", original.summary.text, merged.summary.text))

    orig_exp_by_id = {e.entry_id: e for e in original.experience}
    for entry in merged.experience:
        orig_entry = orig_exp_by_id.get(entry.entry_id)
        orig_bullets = orig_entry.bullets if orig_entry else []
        changes, reordered = _diff_item_list("experience", entry.entry_id, orig_bullets, entry.bullets)
        all_changes.extend(changes)
        if reordered:
            reordered_sections.append(entry.entry_id)

    skill_changes, skills_reordered = _diff_item_list("skills", "skills", original.skills, merged.skills)
    all_changes.extend(skill_changes)
    if skills_reordered:
        reordered_sections.append("skills")

    return SectionDiff(changes=all_changes, reordered_sections=reordered_sections)

from core.diff import compute_diff
from core.resume_model import Bullet, ContentModel, ExperienceEntry, SkillLine, Summary


def _cm(bullets, skills=None):
    return ContentModel(
        summary=Summary(text="Original summary."),
        experience=[ExperienceEntry(entry_id="exp1", org_label="Acme — Engineer", bullets=bullets)],
        skills=skills or [SkillLine(item_id="skill1", text="Python.")],
    )


def test_reworded_and_added_and_removed_detected():
    original = _cm([
        Bullet(bullet_id="exp1-b1", text="Did thing A."),
        Bullet(bullet_id="exp1-b2", text="Did thing B."),
    ])
    merged = _cm([
        Bullet(bullet_id="exp1-b1", text="Did thing A, reworded."),
        Bullet(bullet_id="exp1-b3", text="Did new thing C.", change="added", source_answer_id="q1"),
    ])
    diff = compute_diff(original, merged)
    kinds = {c.ref: c.change_type for c in diff.changes}
    assert kinds["exp1:exp1-b1"] == "reworded"
    assert kinds["exp1:exp1-b3"] == "added"
    assert kinds["exp1:exp1-b2"] == "removed"


def test_reorder_detected_when_relative_order_changes():
    original = _cm([
        Bullet(bullet_id="exp1-b1", text="A"),
        Bullet(bullet_id="exp1-b2", text="B"),
    ])
    merged = _cm([
        Bullet(bullet_id="exp1-b2", text="B"),
        Bullet(bullet_id="exp1-b1", text="A"),
    ])
    diff = compute_diff(original, merged)
    assert "exp1" in diff.reordered_sections

"""
The top-priority test: parsing the master resume into a content model and
rendering it back with zero changes must reproduce the original file
byte-for-byte. This is what proves the LaTeX skeleton is never touched.
"""
from pathlib import Path

from core.parser import parse_master_tex
from core.renderer import render_tex

MASTER_TEX = Path(__file__).resolve().parent.parent / "Resources" / "main.tex"


def test_unmodified_roundtrip_is_byte_identical():
    parsed = parse_master_tex(str(MASTER_TEX))
    rendered = render_tex(parsed, parsed.content_model)
    assert rendered == parsed.original_text


def test_content_model_has_expected_shape():
    parsed = parse_master_tex(str(MASTER_TEX))
    cm = parsed.content_model
    assert "Software Applications Developer" in cm.summary.text
    assert len(cm.experience) == 5
    assert len(cm.experience[0].bullets) == 5
    assert len(cm.experience[1].bullets) == 9
    assert len(cm.skills) == 7
    # No LaTeX escape sequences should leak into the content model.
    for entry in cm.experience:
        for b in entry.bullets:
            assert "\\" not in b.text
    assert "\\" not in cm.summary.text


def test_editing_a_bullet_only_changes_that_bullet():
    parsed = parse_master_tex(str(MASTER_TEX))
    cm = parsed.content_model.model_copy(deep=True)
    original_first_bullet = cm.experience[0].bullets[0].text
    cm.experience[0].bullets[0].text = "Rewrote this bullet entirely for a test."
    rendered = render_tex(parsed, cm)

    assert "Rewrote this bullet entirely for a test." in rendered
    assert original_first_bullet not in rendered
    # Everything else — including the other bullets in the same entry — is untouched:
    # \textbf{iOS application} in the rendered LaTeX is the escaped form of the
    # content model's **iOS application** markdown-lite text.
    assert "\\textbf{iOS application}" in rendered
    assert rendered.count("\\resumeItemListEnd") == parsed.original_text.count("\\resumeItemListEnd")


def test_added_bullet_with_no_raw_counterpart_renders_cleanly():
    parsed = parse_master_tex(str(MASTER_TEX))
    cm = parsed.content_model.model_copy(deep=True)
    from core.resume_model import Bullet

    cm.experience[0].bullets.append(
        Bullet(bullet_id="exp1-bnew", text="Added a brand new bullet for testing.", change="added")
    )
    rendered = render_tex(parsed, cm)
    assert "Added a brand new bullet for testing." in rendered
    assert rendered.count("\\resumeItemListEnd") == parsed.original_text.count("\\resumeItemListEnd")

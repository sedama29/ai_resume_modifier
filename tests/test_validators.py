from core.resume_model import Bullet, ContentModel, ExperienceEntry, SkillLine, Summary
from core.validators import validate_and_merge


def _base_content_model() -> ContentModel:
    return ContentModel(
        summary=Summary(text="Experienced developer with Python and FastAPI background."),
        experience=[
            ExperienceEntry(
                entry_id="exp1",
                org_label="Acme — Engineer",
                bullets=[
                    Bullet(bullet_id="exp1-b1", text="Built a data pipeline processing 10TB of data."),
                    Bullet(bullet_id="exp1-b2", text="Led a team of 3 engineers."),
                ],
            )
        ],
        skills=[SkillLine(item_id="skill1", text="Python, SQL, Docker.")],
    )


def test_invented_entry_id_is_discarded():
    original = _base_content_model()
    llm_output = original.model_copy(deep=True)
    llm_output.experience.append(
        ExperienceEntry(entry_id="exp99", org_label="Fake Corp — CEO", bullets=[])
    )
    merged, warnings = validate_and_merge(original, llm_output, confirmed_answer_ids=set())

    assert {e.entry_id for e in merged.experience} == {"exp1"}
    assert any(w.kind == "unknown_id" for w in warnings)


def test_added_bullet_without_confirmed_source_is_dropped():
    original = _base_content_model()
    llm_output = original.model_copy(deep=True)
    llm_output.experience[0].bullets.append(
        Bullet(bullet_id="exp1-bnew", text="Expert in Kubernetes at massive scale.", change="added", source_answer_id=None)
    )
    merged, warnings = validate_and_merge(original, llm_output, confirmed_answer_ids=set())

    bullet_ids = {b.bullet_id for b in merged.experience[0].bullets}
    assert "exp1-bnew" not in bullet_ids
    assert any(w.kind == "missing_source_answer" for w in warnings)


def test_added_bullet_with_confirmed_source_is_kept():
    original = _base_content_model()
    llm_output = original.model_copy(deep=True)
    llm_output.experience[0].bullets.append(
        Bullet(bullet_id="exp1-bnew", text="Used Docker for containerized deployments.", change="added", source_answer_id="q1")
    )
    merged, warnings = validate_and_merge(original, llm_output, confirmed_answer_ids={"q1"})

    bullet_ids = {b.bullet_id for b in merged.experience[0].bullets}
    assert "exp1-bnew" in bullet_ids
    assert not any(w.kind == "missing_source_answer" for w in warnings)


def test_unexplained_new_number_is_flagged_not_dropped():
    original = _base_content_model()
    llm_output = original.model_copy(deep=True)
    llm_output.experience[0].bullets[0].text = "Built a data pipeline processing 500TB of data, saving $2M annually."
    merged, warnings = validate_and_merge(original, llm_output, confirmed_answer_ids=set())

    # Not dropped -- it's the human review gate's job to accept/reject, not the validator's.
    assert merged.experience[0].bullets[0].text == llm_output.experience[0].bullets[0].text
    assert any(w.kind == "numeric_mismatch" for w in warnings)


def test_new_term_not_present_anywhere_is_flagged():
    original = _base_content_model()
    llm_output = original.model_copy(deep=True)
    llm_output.experience[0].bullets[1].text = "Led a team of 3 engineers using Kubernetes."
    merged, warnings = validate_and_merge(original, llm_output, confirmed_answer_ids=set())

    assert merged.experience[0].bullets[1].text == llm_output.experience[0].bullets[1].text  # flagged, not dropped
    term_warnings = [w for w in warnings if w.kind == "unverified_new_term"]
    assert len(term_warnings) == 1
    assert "Kubernetes" in term_warnings[0].message


def test_term_truthfully_elsewhere_in_resume_is_not_flagged():
    original = _base_content_model()
    original.skills.append(SkillLine(item_id="skill2", text="Familiar with Docker."))
    llm_output = original.model_copy(deep=True)
    # "Docker" already appears in the original skills section -- surfacing it
    # in a bullet too is a legitimate reorganization, not fabrication.
    llm_output.experience[0].bullets[1].text = "Led a team of 3 engineers deploying with Docker."
    merged, warnings = validate_and_merge(original, llm_output, confirmed_answer_ids=set())

    assert not any(w.kind == "unverified_new_term" for w in warnings)


def test_missing_entry_falls_back_to_original():
    original = _base_content_model()
    llm_output = original.model_copy(deep=True)
    llm_output.experience = []  # LLM dropped the whole job entry
    merged, warnings = validate_and_merge(original, llm_output, confirmed_answer_ids=set())

    assert len(merged.experience) == 1
    assert merged.experience[0].entry_id == "exp1"
    assert any(w.kind == "fallback_to_original" for w in warnings)


def test_empty_bullets_falls_back_to_original_bullets():
    original = _base_content_model()
    llm_output = original.model_copy(deep=True)
    llm_output.experience[0].bullets = []
    merged, warnings = validate_and_merge(original, llm_output, confirmed_answer_ids=set())

    assert len(merged.experience[0].bullets) == 2
    assert any(w.kind == "fallback_to_original" for w in warnings)

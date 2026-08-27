"""
The editable "content model" -- the ONLY representation of resume content the
LLM ever sees or produces. Plain/markdown-lite text (see text_transform.py),
no LaTeX. This is what gets sent to Groq, stored in the DB per resume version,
and shown on the Review Changes screen.

Fields NOT modeled here (org, title, dates, location, education, certifications)
are never sent to the LLM and are always taken from the original parse -- see
core/parser.py's raw region map for how they're preserved.
"""
from typing import Literal, Optional
from pydantic import BaseModel, Field

ChangeType = Literal["unchanged", "reworded", "reordered", "added", "removed"]


class Bullet(BaseModel):
    bullet_id: str
    text: str
    change: ChangeType = "unchanged"
    source_answer_id: Optional[int] = None


class ExperienceEntry(BaseModel):
    entry_id: str
    org_label: str  # display-only, e.g. "Harte Research Institute -- Software Applications Developer"
    bullets: list[Bullet] = Field(default_factory=list)


class SkillLine(BaseModel):
    item_id: str
    text: str
    change: ChangeType = "unchanged"
    source_answer_id: Optional[int] = None


class Summary(BaseModel):
    text: str
    change: ChangeType = "unchanged"


class ContentModel(BaseModel):
    summary: Summary
    experience: list[ExperienceEntry] = Field(default_factory=list)
    skills: list[SkillLine] = Field(default_factory=list)

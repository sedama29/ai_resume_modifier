"""
Parses the master resume .tex into a ContentModel (editable content, for the LLM)
plus a raw region map (whitespace/marker bookkeeping needed to splice edited
content back into the original file byte-for-byte when unchanged).

Anchored on actual section headings and macro usage as they appear in the real
file, not just macro definitions in the preamble -- some defined macros
(\\resumeItem, \\resumeHeadingSkillStart) are never actually used in the body.
"""
import re
from dataclasses import dataclass, field
from pathlib import Path

from core.resume_model import Bullet, ContentModel, ExperienceEntry, SkillLine, Summary
from core.text_transform import tex_unescape

_ITEM_MARKER_RE = re.compile(r"\\item[ \t]?")


@dataclass
class RawItem:
    item_id: str
    marker: str
    leading_ws: str
    stripped_text_raw: str
    trailing_ws: str


@dataclass
class ItemizedRegionRaw:
    start: int
    end: int
    header_ws: str
    items: list[RawItem] = field(default_factory=list)


@dataclass
class ParagraphRegionRaw:
    start: int
    end: int
    leading_ws: str
    stripped_text_raw: str
    trailing_ws: str


@dataclass
class ParsedResume:
    original_text: str
    content_model: ContentModel
    regions: dict  # region key -> ItemizedRegionRaw | ParagraphRegionRaw


def _consume_brace_groups(text: str, pos: int, n: int) -> tuple[list[str], int]:
    """Consume n consecutive balanced {...} groups starting at/after pos.
    Returns (group_contents, index_after_last_group)."""
    groups = []
    i = pos
    for _ in range(n):
        while i < len(text) and text[i] != "{":
            i += 1
        if i >= len(text):
            raise ValueError(f"expected {n} brace groups, found {len(groups)}")
        depth = 1
        j = i + 1
        start_inner = j
        while j < len(text) and depth > 0:
            if text[j] == "{":
                depth += 1
            elif text[j] == "}":
                depth -= 1
            j += 1
        groups.append(text[start_inner : j - 1])
        i = j
    return groups, i


def _strip_outer_braces(text: str) -> str:
    text = text.strip()
    if text.startswith("{") and text.endswith("}"):
        return text[1:-1].strip()
    return text


def _parse_itemized_region(region_text: str, id_prefix: str) -> tuple[str, list[RawItem]]:
    matches = list(_ITEM_MARKER_RE.finditer(region_text))
    if not matches:
        return region_text, []
    header_ws = region_text[: matches[0].start()]
    items = []
    for idx, m in enumerate(matches):
        body_start = m.end()
        body_end = matches[idx + 1].start() if idx + 1 < len(matches) else len(region_text)
        body = region_text[body_start:body_end]
        stripped = body.strip()
        if stripped:
            lead_idx = body.index(stripped)
            leading_ws = body[:lead_idx]
            trailing_ws = body[lead_idx + len(stripped) :]
        else:
            leading_ws = body
            trailing_ws = ""
        items.append(
            RawItem(
                item_id=f"{id_prefix}{idx + 1}",
                marker=m.group(0),
                leading_ws=leading_ws,
                stripped_text_raw=stripped,
                trailing_ws=trailing_ws,
            )
        )
    return header_ws, items


def extract_header_fields(original_text: str) -> dict:
    """Best-effort extraction of display-only contact fields for seeding
    candidate_profile. Never used for rendering -- the header is always
    pass-through skeleton. Missing fields are left as None for the user to
    fill in manually."""
    fields: dict = {"name": None, "phone": None, "email": None, "github": None, "location": None}

    # Restrict to the document body -- the preamble's comment header can contain
    # an unrelated template-author email/name that must never be picked up.
    doc_idx = original_text.find(r"\begin{document}")
    body = original_text[doc_idx:] if doc_idx != -1 else original_text

    m = re.search(r"\{\\Huge\\textbf\{(.*?)\}\}", body)
    if m:
        fields["name"] = tex_unescape(m.group(1)).strip()

    m = re.search(r"\\faPhone\\?\s*([+\d][\d\-\s]*\d)", body)
    if m:
        fields["phone"] = m.group(1).strip()

    m = re.search(r"[\w.+-]+@[\w-]+\.[\w.-]+", body)
    if m:
        fields["email"] = m.group(0)

    m = re.search(r"github\.com/([\w-]+)", body)
    if m:
        fields["github"] = m.group(1)

    m = re.search(r"\\faMapMarker\\?\s*([^\n}]+)", body)
    if m:
        location = tex_unescape(m.group(1)).replace("\\ ", " ").strip().rstrip("}").strip()
        fields["location"] = location

    return fields


def parse_master_tex(path: str) -> ParsedResume:
    original_text = Path(path).read_text()
    regions: dict = {}

    # --- Summary ---
    just_open = r"\begin{justify}"
    just_close = r"\end{justify}"
    just_start = original_text.index(just_open) + len(just_open)
    just_end = original_text.index(just_close, just_start)
    body = original_text[just_start:just_end]
    stripped = body.strip()
    lead_idx = body.index(stripped)
    summary_leading_ws = body[:lead_idx]
    summary_trailing_ws = body[lead_idx + len(stripped) :]
    regions["summary"] = ParagraphRegionRaw(
        just_start, just_end, summary_leading_ws, stripped, summary_trailing_ws
    )
    summary_text = tex_unescape(stripped)

    # --- Experience ---
    exp_section_start = original_text.index(r"\section{\textbf{PROFESSIONAL EXPERIENCE")
    list_start_tag = r"\resumeSubHeadingListStart"
    list_end_tag = r"\resumeSubHeadingListEnd"
    exp_list_start = original_text.index(list_start_tag, exp_section_start) + len(list_start_tag)
    exp_list_end = original_text.index(list_end_tag, exp_list_start)
    exp_block = original_text[exp_list_start:exp_list_end]

    experience_entries = []
    item_start_tag = r"\resumeItemListStart"
    item_end_tag = r"\resumeItemListEnd"
    for entry_idx, m in enumerate(re.finditer(r"\\resumeSubheading", exp_block), start=1):
        entry_id = f"exp{entry_idx}"
        groups, after_groups = _consume_brace_groups(exp_block, m.end(), 4)
        org, _location, title, _dates = groups
        il_start = exp_block.index(item_start_tag, after_groups) + len(item_start_tag)
        il_end = exp_block.index(item_end_tag, il_start)
        region_text = exp_block[il_start:il_end]
        header_ws, raw_items = _parse_itemized_region(region_text, f"{entry_id}-b")
        regions[entry_id] = ItemizedRegionRaw(
            start=exp_list_start + il_start,
            end=exp_list_start + il_end,
            header_ws=header_ws,
            items=raw_items,
        )
        bullets = [
            Bullet(bullet_id=ri.item_id, text=tex_unescape(ri.stripped_text_raw))
            for ri in raw_items
        ]
        org_label = f"{tex_unescape(_strip_outer_braces(org))} — {tex_unescape(_strip_outer_braces(title))}"
        experience_entries.append(
            ExperienceEntry(entry_id=entry_id, org_label=org_label, bullets=bullets)
        )

    # --- Skills ---
    skills_section_start = original_text.index(r"\section{\textbf{Skills}}")
    m_begin = re.search(r"\\begin\{itemize\}(\[[^\]]*\])?", original_text[skills_section_start:])
    skills_body_start = skills_section_start + m_begin.end()
    skills_body_end = original_text.index(r"\end{itemize}", skills_body_start)
    skills_region_text = original_text[skills_body_start:skills_body_end]
    skills_header_ws, skills_raw_items = _parse_itemized_region(skills_region_text, "skill")
    regions["skills"] = ItemizedRegionRaw(
        skills_body_start, skills_body_end, skills_header_ws, skills_raw_items
    )
    skills = [
        SkillLine(item_id=ri.item_id, text=tex_unescape(ri.stripped_text_raw))
        for ri in skills_raw_items
    ]

    content_model = ContentModel(
        summary=Summary(text=summary_text),
        experience=experience_entries,
        skills=skills,
    )
    return ParsedResume(original_text=original_text, content_model=content_model, regions=regions)

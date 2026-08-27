"""
Re-emits a full .tex file by splicing the ORIGINAL file's bytes with regenerated
content only in the regions core/parser.py identified. Every byte outside those
regions -- preamble, macros, packages, geometry, header, education,
certifications -- is copied through untouched.
"""
from core.parser import ItemizedRegionRaw, ParagraphRegionRaw, ParsedResume
from core.resume_model import ContentModel
from core.text_transform import tex_escape


def _render_itemized_region(raw: ItemizedRegionRaw, items: list[tuple[str, str]]) -> str:
    id_to_raw = {ri.item_id: ri for ri in raw.items}
    default_marker = raw.items[0].marker if raw.items else "\\item "
    default_trailing_ws = raw.items[-1].trailing_ws if raw.items else "\n"

    parts = [raw.header_ws]
    for item_id, text in items:
        escaped = tex_escape(text)
        ri = id_to_raw.get(item_id)
        if ri is not None:
            parts.append(ri.marker)
            parts.append(ri.leading_ws)
            parts.append(escaped)
            parts.append(ri.trailing_ws)
        else:
            # A newly-added item with no original counterpart: match sibling style.
            parts.append(default_marker)
            parts.append(escaped)
            parts.append(default_trailing_ws)
    return "".join(parts)


def _render_paragraph_region(raw: ParagraphRegionRaw, text: str) -> str:
    return raw.leading_ws + tex_escape(text) + raw.trailing_ws


def render_tex(parsed: ParsedResume, content_model: ContentModel) -> str:
    spans: list[tuple[int, int, str]] = []

    summary_raw = parsed.regions["summary"]
    spans.append(
        (summary_raw.start, summary_raw.end, _render_paragraph_region(summary_raw, content_model.summary.text))
    )

    for entry in content_model.experience:
        raw = parsed.regions[entry.entry_id]
        items = [(b.bullet_id, b.text) for b in entry.bullets]
        spans.append((raw.start, raw.end, _render_itemized_region(raw, items)))

    skills_raw = parsed.regions["skills"]
    skill_items = [(s.item_id, s.text) for s in content_model.skills]
    spans.append((skills_raw.start, skills_raw.end, _render_itemized_region(skills_raw, skill_items)))

    spans.sort(key=lambda s: s[0])

    original = parsed.original_text
    out = []
    cursor = 0
    for start, end, text in spans:
        out.append(original[cursor:start])
        out.append(text)
        cursor = end
    out.append(original[cursor:])
    return "".join(out)

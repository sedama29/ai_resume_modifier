"""Deterministic ATS (Applicant Tracking System) compatibility analysis --
no LLM call, for the same reason core/evidence.py isn't one: a rule-based
check over facts we can already compute exactly is more trustworthy than
asking a model to judge keyword-safety or invent a score. Every issue this
raises is traceable to a concrete, reproducible check, and every "safe
improvement" it suggests is gated on evidence that's already confirmed --
this never recommends adding a keyword the candidate hasn't actually
confirmed, the same rule that governs resume_rewrite/validate_and_merge.

Checks the FINALIZED, approved resume content (after Review Changes) against
the job's requirements and every confirmed evidence source (master resume,
confirmed_experiences, GitHub, learning) via core/evidence.py -- reused
rather than re-implemented, per the same cross-referencing this app already
does for the Match Summary evidence table and Follow-up Questions discoveries."""
import io
import re
from dataclasses import dataclass, field

from core.evidence import build_evidence_rows
from core.resume_model import ContentModel

CONTACT_EMAIL_RE = re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+")
CONTACT_PHONE_RE = re.compile(r"(\+?\d[\d\-.\s()]{7,}\d)")
SECTION_LINE_RE = re.compile(r"\\(?:cv)?section\*?\{(.+)\}\s*$", re.MULTILINE)
LATEX_COMMAND_RE = re.compile(r"\\[a-zA-Z]+\*?(?:\{|\s|$)|[{}]")

REQUIRED_SECTION_KEYWORDS = {
    "Summary": ["summary", "objective", "profile"],
    "Experience": ["experience"],
    "Education": ["education"],
    "Skills": ["skills"],
}
OPTIONAL_SECTION_KEYWORDS = {
    "Projects": ["project"],
    "Certifications": ["certification"],
}

STUFFING_THRESHOLD = 6  # occurrences of one keyword before it reads as unnatural repetition
TONE_RANK = {"green": 0, "yellow": 1, "red": 2}


@dataclass
class ATSIssue:
    category: str
    severity: str  # "info" | "warning"
    message: str


@dataclass
class ATSCategory:
    key: str
    label: str
    tone: str  # green | yellow | red | gray ("gray" = not evaluable, e.g. no PDF)
    summary: str


@dataclass
class SafeImprovement:
    skill: str
    tier: str
    evidence: str
    detail: str


@dataclass
class ATSResult:
    overall_tone: str
    categories: list[ATSCategory]
    issues: list[ATSIssue] = field(default_factory=list)
    safe_improvements: list[SafeImprovement] = field(default_factory=list)
    extracted_text: str = ""
    pdf_available: bool = False


def _extract_pdf_text(pdf_bytes: bytes | None) -> str:
    if not pdf_bytes:
        return ""
    try:
        from pypdf import PdfReader
        reader = PdfReader(io.BytesIO(pdf_bytes))
        return "\n".join((page.extract_text() or "") for page in reader.pages)
    except Exception:
        return ""


def _detected_sections(tex_content: str) -> set[str]:
    titles = SECTION_LINE_RE.findall(tex_content)
    plain_titles = " | ".join(LATEX_COMMAND_RE.sub(" ", t).lower() for t in titles)
    found = set()
    for name, keywords in {**REQUIRED_SECTION_KEYWORDS, **OPTIONAL_SECTION_KEYWORDS}.items():
        if any(kw in plain_titles for kw in keywords):
            found.add(name)
    return found


def _clean_org_label(label: str) -> str:
    # org_label uses this app's markdown-lite **bold** convention (see
    # text_transform.py), not raw LaTeX -- strip both so the comparison
    # against plain extracted PDF text isn't defeated by leftover markers.
    text = LATEX_COMMAND_RE.sub(" ", label).replace("**", "")
    return re.sub(r"\s+", " ", text).strip()


def _overall_tone(tones: list[str]) -> str:
    real = [t for t in tones if t != "gray"]
    if not real:
        return "gray"
    worst = max(real, key=lambda t: TONE_RANK.get(t, 0))
    return worst


def run_ats_check(
    tex_content: str,
    pdf_bytes: bytes | None,
    content_model: ContentModel,
    job_analysis: dict,
    match_result: dict,
    candidate_profile: dict,
    confirmed_followup_skills: set[str] | None = None,
) -> ATSResult:
    """confirmed_followup_skills: lowercased skill names confirmed "yes" via a
    plain missing-skill Follow-up Question (related_skill + answer_bool=True
    in followup_questions) -- build_evidence_rows() only knows about
    match_result.present and candidate_profile.confirmed_experiences (the
    GitHub/learning discovery store), so without this, a skill confirmed
    through an ordinary follow-up question would be wrongly reported here as
    "not supported by confirmed experience" even though it's exactly that."""
    issues: list[ATSIssue] = []
    safe_improvements: list[SafeImprovement] = []
    confirmed_followup_skills = confirmed_followup_skills or set()

    # --- Keyword alignment (reuses the same evidence cross-reference as
    # Match Summary / Follow-up Questions -- never invents a new judgment) ---
    rows = build_evidence_rows(job_analysis, match_result, candidate_profile)
    for r in rows:
        if not r.confirmed and r.skill.lower() in confirmed_followup_skills:
            r.confirmed = True
            r.found_in = "Confirmed via Follow-up Questions"

    unsupported = [r for r in rows if not r.confirmed and r.tier == "none"]
    discovered_not_added = [r for r in rows if not r.confirmed and r.tier != "none"]

    for r in unsupported:
        issues.append(ATSIssue(
            "keyword_alignment", "warning",
            f'"{r.skill}" appears in the job description but is not supported by your confirmed experience.',
        ))
    for r in discovered_not_added:
        issues.append(ATSIssue(
            "keyword_alignment", "info",
            f'"{r.skill}" has unconfirmed evidence ({r.found_in}) -- confirm it on the Follow-up Questions '
            f"step to consider adding it.",
        ))

    required_count = sum(1 for r in rows if r.importance == "required")
    required_hit = sum(1 for r in rows if r.importance == "required" and r.confirmed)
    if not rows:
        keyword_tone = "gray"
    elif not unsupported:
        keyword_tone = "green"
    elif len(unsupported) <= max(1, required_count // 3):
        keyword_tone = "yellow"
    else:
        keyword_tone = "red"
    keyword_summary = (
        f"{required_hit}/{required_count} required keywords supported by confirmed experience."
        if required_count else "No required keywords were extracted from this job description."
    )

    # --- Text extraction ------------------------------------------------------
    extracted_text = _extract_pdf_text(pdf_bytes)
    extracted_lower = extracted_text.lower()
    pdf_available = pdf_bytes is not None
    text_extractable = bool(extracted_text.strip())

    if pdf_available and not text_extractable:
        issues.append(ATSIssue(
            "text_extraction", "warning",
            "No selectable text could be extracted from the generated PDF -- content may be rendered as an image.",
        ))
    text_tone = "gray" if not pdf_available else ("green" if text_extractable else "red")
    text_summary = (
        "Not checked yet -- generate the PDF first." if not pdf_available
        else ("Resume text is selectable and extractable." if text_extractable
              else "Text could not be extracted from the PDF.")
    )

    # Whitespace-insensitive: some fonts' ToUnicode CMaps introduce spurious
    # spaces around certain letter pairs when text is extracted from the
    # compiled PDF (e.g. "Tata" -> "T ata") -- collapsing whitespace on both
    # sides avoids flagging that PDF-extraction noise as missing content.
    extracted_nospace = re.sub(r"\s+", "", extracted_lower)

    # Confirmed evidence whose keyword doesn't literally appear in the
    # rendered text -- a *safe* candidate improvement, since the evidence is
    # already confirmed, it just may be phrased differently than the exact
    # job-description term.
    if text_extractable:
        for r in rows:
            if r.confirmed and re.sub(r"\s+", "", r.skill.lower()) not in extracted_nospace:
                safe_improvements.append(SafeImprovement(
                    skill=r.skill, tier=r.tier, evidence=r.found_in,
                    detail=f'"{r.skill}" is confirmed experience but may not be explicitly worded in the customized resume.',
                ))

        for r in rows:
            count = len(re.findall(re.escape(r.skill.lower()), extracted_lower))
            if count >= STUFFING_THRESHOLD:
                issues.append(ATSIssue(
                    "keyword_alignment", "warning",
                    f'"{r.skill}" appears {count} times -- consider reducing repetition so it reads naturally.',
                ))

    # --- Section structure ------------------------------------------------------
    detected = _detected_sections(tex_content)
    missing_required = [name for name in REQUIRED_SECTION_KEYWORDS if name not in detected]
    for name in missing_required:
        issues.append(ATSIssue("section_structure", "warning", f'No recognizable "{name}" section was detected.'))
    section_tone = "green" if not missing_required else ("yellow" if len(missing_required) == 1 else "red")
    section_summary = (
        "All standard sections detected." if not missing_required
        else f"Missing section(s): {', '.join(missing_required)}."
    )

    # --- Contact information ------------------------------------------------------
    if text_extractable:
        has_email = bool(CONTACT_EMAIL_RE.search(extracted_text))
        has_phone = bool(CONTACT_PHONE_RE.search(extracted_text))
        if not has_email:
            issues.append(ATSIssue("contact_info", "warning", "No email address was found as selectable text."))
        if not has_phone:
            issues.append(ATSIssue("contact_info", "info", "No phone number was found as selectable text."))
        contact_tone = "green" if (has_email and has_phone) else ("yellow" if (has_email or has_phone) else "red")
        contact_summary = "Email and phone are present as selectable text." if (has_email and has_phone) else "Some contact details may be missing as selectable text."
    else:
        contact_tone = "gray"
        contact_summary = "Not checked yet -- generate the PDF first."

    # --- Skills / experience clearly represented ------------------------------------
    missing_experience_entries = []
    if text_extractable:
        for e in content_model.experience:
            label_text = _clean_org_label(e.org_label).lower()
            first_word_chunk = re.sub(r"\s+", "", label_text.split(" — ")[0].strip())[:24]
            if first_word_chunk and first_word_chunk not in extracted_nospace:
                missing_experience_entries.append(e.org_label)
    for label in missing_experience_entries:
        issues.append(ATSIssue(
            "skills_alignment", "info",
            f'"{_clean_org_label(label)}" may not be clearly represented in the extracted PDF text -- worth a quick visual check.',
        ))

    # Deliberately independent of the "unsupported" keyword list above --
    # that's Keyword Alignment's concern (do you HAVE the skill); this is
    # about whether what you DO have is clearly/visibly represented, so the
    # same underlying issue doesn't get flagged twice under two different
    # category badges.
    if not text_extractable:
        skills_tone = "gray"
        skills_summary = "Not checked yet -- generate the PDF first."
    elif not content_model.skills:
        skills_tone = "red"
        skills_summary = "No skills section content was found."
    elif missing_experience_entries:
        skills_tone = "yellow"
        skills_summary = "Skills are listed, with a few experience entries worth a quick visual check."
    else:
        skills_tone = "green"
        skills_summary = "Skills and experience entries are clearly represented."

    # --- Formatting (includes lightweight consistency heuristics) ------------------
    formatting_notes = []
    if "\\includegraphics" in tex_content:
        formatting_notes.append("The template includes an image -- make sure no essential information (name, contact details) is embedded only in it.")
    table_count = len(re.findall(r"\\begin\{tabular", tex_content))
    if table_count > 3:
        formatting_notes.append(f"The layout uses {table_count} tables -- some ATS parsers handle tables less reliably than plain text.")
    bullet_texts = [b.text for e in content_model.experience for b in e.bullets]
    trailing_punct = {b.strip()[-1] for b in bullet_texts if b.strip() and b.strip()[-1] in ".!"}
    if len(trailing_punct) > 1:
        formatting_notes.append("Bullet points end inconsistently (some with periods, some without) -- consider making this uniform.")
    for note in formatting_notes:
        issues.append(ATSIssue("formatting", "info", note))
    formatting_tone = "green" if not formatting_notes else "yellow"
    formatting_summary = "No formatting concerns detected." if not formatting_notes else f"{len(formatting_notes)} formatting note(s) to review."

    categories = [
        ATSCategory("keyword_alignment", "Keyword Alignment", keyword_tone, keyword_summary),
        ATSCategory("formatting", "Formatting", formatting_tone, formatting_summary),
        ATSCategory("text_extraction", "Text Extractability", text_tone, text_summary),
        ATSCategory("section_structure", "Section Structure", section_tone, section_summary),
        ATSCategory("contact_info", "Contact Information", contact_tone, contact_summary),
        ATSCategory("skills_alignment", "Skills Alignment", skills_tone, skills_summary),
    ]
    overall_tone = _overall_tone([c.tone for c in categories])

    return ATSResult(
        overall_tone=overall_tone,
        categories=categories,
        issues=issues,
        safe_improvements=safe_improvements,
        extracted_text=extracted_text,
        pdf_available=pdf_available,
    )

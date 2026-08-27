"""
Converts between raw LaTeX text and plain/markdown-lite text safe to send to an LLM.

The LLM only ever sees/produces plain English plus **bold** markers. Nothing it
outputs is ever interpreted as LaTeX syntax: escape() mechanically re-escapes
every special character on the way back in a single pass, regardless of what
the model produced -- a stray '\\', '{', '%', etc. in LLM output can only ever
render as a literal character, never as LaTeX syntax.
"""
import re

_EM_DASH = "—"
_EN_DASH = "–"

# Single-character LaTeX specials -> their escaped source form.
_ESCAPE_MAP = {
    "\\": r"\textbackslash{}",
    "{": r"\{",
    "}": r"\}",
    "%": r"\%",
    "&": r"\&",
    "#": r"\#",
    "_": r"\_",
    "$": r"\$",
    "~": r"\textasciitilde{}",
    "^": r"\textasciicircum{}",
}
_ESCAPE_RE = re.compile("|".join(re.escape(c) for c in _ESCAPE_MAP))

# Escaped source forms -> their plain character, longest-first so e.g.
# \textbackslash{} is matched before a bare \.
_UNESCAPE_MAP = {
    r"\textbackslash{}": "\\",
    r"\textasciitilde{}": "~",
    r"\textasciicircum{}": "^",
    r"\{": "{",
    r"\}": "}",
    r"\%": "%",
    r"\&": "&",
    r"\#": "#",
    r"\_": "_",
    r"\$": "$",
}
_UNESCAPE_RE = re.compile(
    "|".join(re.escape(k) for k in sorted(_UNESCAPE_MAP, key=len, reverse=True))
)


def _convert_textbf_to_bold(text: str) -> str:
    out = []
    i = 0
    n = len(text)
    marker = "\\textbf{"
    while i < n:
        idx = text.find(marker, i)
        if idx == -1:
            out.append(text[i:])
            break
        out.append(text[i:idx])
        depth = 1
        j = idx + len(marker)
        start_inner = j
        while j < n and depth > 0:
            if text[j] == "{":
                depth += 1
            elif text[j] == "}":
                depth -= 1
            j += 1
        inner = text[start_inner : j - 1]
        out.append("**" + _convert_textbf_to_bold(inner) + "**")
        i = j
    return "".join(out)


def _convert_bold_to_textbf(text: str) -> str:
    return re.sub(r"\*\*(.+?)\*\*", lambda m: "\\textbf{" + m.group(1) + "}", text)


def tex_unescape(text: str) -> str:
    """LaTeX source fragment -> plain/markdown-lite text for the LLM."""
    text = _convert_textbf_to_bold(text)
    text = _UNESCAPE_RE.sub(lambda m: _UNESCAPE_MAP[m.group(0)], text)
    text = text.replace("---", _EM_DASH).replace("--", _EN_DASH)
    return text


def tex_escape(text: str) -> str:
    """Plain/markdown-lite text (possibly LLM output) -> safe LaTeX source fragment."""
    text = text.replace(_EM_DASH, "---").replace(_EN_DASH, "--")
    # Single pass over the ORIGINAL string only -- replacement text is never
    # re-scanned, so this cannot double-escape or be corrupted by its own output.
    text = _ESCAPE_RE.sub(lambda m: _ESCAPE_MAP[m.group(0)], text)
    text = _convert_bold_to_textbf(text)
    return text

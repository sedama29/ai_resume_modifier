"""Shared visual styling injected on every page. One place to keep the look
consistent -- call inject_custom_css() right after st.set_page_config().

Design language: neutral off-white background, white surfaces, one muted
accent (indigo), reserved for primary actions and active/selected states.
Avoid bright saturated blue as a dominant color -- it should read as a
calm, premium productivity tool, not a chatbot."""
import streamlit as st

_CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');

:root {
    --bg: #FAFAF9;
    --surface: #FFFFFF;
    --ink: #18181B;
    --muted: #71717A;
    --border: #E4E4E7;
    --accent: #5B5FC7;
    --accent-hover: #4C50AD;
    --accent-tint: #F1F1FB;
    --success: #15803D;
    --success-tint: #F0FDF4;
    --success-border: #BBF7D0;
    --warning: #B45309;
    --warning-tint: #FFFBEB;
    --warning-border: #FDE68A;
    --error: #B91C1C;
    --error-tint: #FEF2F2;
    --error-border: #FECACA;
}

html, body, [class*="css"], .stMarkdown, .stText {
    font-family: 'Inter', -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif !important;
}

[data-testid="stAppViewContainer"] { background: var(--bg); }
.block-container { padding-top: 2.75rem; max-width: 880px; }
[data-testid="stMainBlockContainer"] { max-width: 880px; }

/* Wider containers for content that genuinely needs the room */
.wide-content .block-container { max-width: 1180px; }

/* --- Headers --- */
h1 { font-weight: 650 !important; letter-spacing: -0.02em; color: var(--ink); font-size: 1.9rem !important; }
h2, h3 { font-weight: 600 !important; letter-spacing: -0.01em; color: var(--ink); }
h2 { font-size: 1.2rem !important; }
h3 { font-size: 1.02rem !important; }
[data-testid="stCaptionContainer"] { color: var(--muted) !important; }
p { color: var(--ink); }
hr { border-color: var(--border); margin: 0.75rem 0; }

/* --- Buttons: restrained, one accent --- */
.stButton > button, .stFormSubmitButton > button, .stDownloadButton > button {
    border-radius: 8px;
    font-weight: 500;
    padding: 0.45rem 1rem;
    border: 1px solid var(--border);
    background: var(--surface);
    color: var(--ink);
    box-shadow: none;
    transition: background 0.12s ease, border-color 0.12s ease;
}
.stButton > button:hover, .stFormSubmitButton > button:hover, .stDownloadButton > button:hover {
    background: #F7F7F8;
    border-color: #C9C9CE;
    color: var(--ink);
}
.stButton > button[kind="primary"], .stFormSubmitButton > button[kind="primary"] {
    background: var(--accent);
    border-color: var(--accent);
    color: #FFFFFF;
}
.stButton > button[kind="primary"]:hover, .stFormSubmitButton > button[kind="primary"]:hover {
    background: var(--accent-hover);
    border-color: var(--accent-hover);
    color: #FFFFFF;
}

/* --- Card-style bordered containers --- */
div[data-testid="stVerticalBlockBorderWrapper"] {
    border-radius: 10px !important;
    border-color: var(--border) !important;
    background: var(--surface);
    box-shadow: none;
}

/* --- Metrics --- */
div[data-testid="stMetric"] {
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: 10px;
    padding: 14px 16px;
}
div[data-testid="stMetricValue"] { color: var(--ink); font-weight: 650; }
div[data-testid="stMetricLabel"] { color: var(--muted); }

/* --- Inputs --- */
.stTextInput input, .stTextArea textarea, .stNumberInput input, div[data-baseweb="select"] {
    border-radius: 8px !important;
}
.stTextInput input:focus, .stTextArea textarea:focus {
    border-color: var(--accent) !important;
    box-shadow: 0 0 0 1px var(--accent) !important;
}
.stRadio [role="radiogroup"] label {
    border: 1px solid var(--border);
    border-radius: 8px;
    padding: 6px 12px;
    margin-right: 6px;
}

/* --- Tabs (used for Paste / URL job input, etc.) --- */
.stTabs [data-baseweb="tab-list"] { gap: 4px; border-bottom: 1px solid var(--border); }
.stTabs [data-baseweb="tab"] {
    border-radius: 8px 8px 0 0;
    color: var(--muted);
    font-weight: 500;
    padding: 8px 16px;
}
.stTabs [aria-selected="true"] {
    color: var(--accent) !important;
    border-bottom: 2px solid var(--accent) !important;
}

/* --- Sidebar: quiet, app-like, not a bare Streamlit menu --- */
section[data-testid="stSidebar"] {
    background: #FBFBFA;
    border-right: 1px solid var(--border);
}
section[data-testid="stSidebar"] .block-container { padding-top: 1.5rem; }
section[data-testid="stSidebar"] [data-testid="stSidebarNav"] { padding-top: 0; }
section[data-testid="stSidebar"] [data-testid="stSidebarNavSeparator"] { display: none; }
section[data-testid="stSidebar"] [data-testid="stSidebarNavLink"],
section[data-testid="stSidebar"] a {
    border-radius: 7px;
    font-weight: 500;
    color: var(--muted);
    padding: 6px 10px;
}
section[data-testid="stSidebar"] a:hover { background: #F0F0F0; color: var(--ink); }
section[data-testid="stSidebar"] [aria-current="page"] {
    background: var(--accent-tint) !important;
    color: var(--accent) !important;
    font-weight: 600;
}
/* Section group headings Streamlit renders for dict-based st.navigation() */
section[data-testid="stSidebar"] [data-testid="stSidebarHeader"] { display: none; }
section[data-testid="stSidebar"] [data-testid="stNavSectionHeader"] p {
    font-size: 0.68rem !important;
    text-transform: uppercase;
    letter-spacing: 0.07em;
    color: #A1A1AA !important;
    font-weight: 600 !important;
    margin: 10px 0 2px 6px !important;
}
section[data-testid="stSidebar"] [data-testid="stNavSectionHeader"] [data-testid="stIconMaterial"] {
    color: #C4C4C9 !important;
    font-size: 1rem !important;
}

/* Flow-only steps (Eligibility/Match/Questions/Review/Generate) are reached
   via the in-page stepper and Continue buttons, not the persistent sidebar --
   still fully functional pages (st.switch_page targets them normally), just
   not offered as independent jump-to links to avoid a flat wall of nav items. */
section[data-testid="stSidebar"] a[href*="/flow-"] { display: none !important; }

/* --- Alerts --- */
div[data-testid="stAlert"] { border-radius: 8px; border-width: 1px; }
</style>
"""


def inject_custom_css() -> None:
    st.markdown(_CSS, unsafe_allow_html=True)


def wide_content() -> None:
    """Opt a page into a wider content column (job descriptions, resume diffs,
    admin tables) instead of the default comfortable-reading width."""
    st.markdown('<div class="wide-content"></div>', unsafe_allow_html=True)
    st.markdown(
        """<style>.block-container { max-width: 1180px !important; }</style>""",
        unsafe_allow_html=True,
    )


def page_header(title: str, subtitle: str = "") -> None:
    """Plain, typographic page heading -- no icons, no decorative rules."""
    subtitle_html = (
        f'<div style="color:var(--muted);font-size:0.95rem;margin-top:4px;max-width:60ch;">{subtitle}</div>'
        if subtitle
        else ""
    )
    st.markdown(
        f"""
        <div style="padding:0 0 22px 0;">
          <div style="font-size:1.7rem;font-weight:650;letter-spacing:-0.02em;color:#18181B;">{title}</div>
          {subtitle_html}
        </div>
        """,
        unsafe_allow_html=True,
    )


_FLOW_STEPS = [
    ("job_input", "Job"),
    ("eligibility", "Eligibility"),
    ("match", "Match"),
    ("questions", "Questions"),
    ("review", "Review"),
    ("generate", "Generate"),
]


def progress_stepper(current_key: str) -> None:
    """Compact horizontal stepper -- numbered circles, thin connector line,
    checkmarks for completed steps, accent for the current one."""
    keys = [k for k, _ in _FLOW_STEPS]
    current_idx = keys.index(current_key) if current_key in keys else -1

    parts = []
    for idx, (_key, label) in enumerate(_FLOW_STEPS):
        if idx < current_idx:
            circle, circle_style = "✓", "background:#F1F1FB;color:#5B5FC7;border:1px solid #D6D6F5;"
            label_style = "color:#71717A;font-weight:500;"
        elif idx == current_idx:
            circle, circle_style = str(idx + 1), "background:#5B5FC7;color:#FFFFFF;border:1px solid #5B5FC7;"
            label_style = "color:#18181B;font-weight:600;"
        else:
            circle, circle_style = str(idx + 1), "background:#FFFFFF;color:#A1A1AA;border:1px solid #E4E4E7;"
            label_style = "color:#A1A1AA;font-weight:500;"

        if idx > 0:
            line_color = "#5B5FC7" if idx <= current_idx else "#E4E4E7"
            parts.append(f'<div style="flex:1;height:1px;background:{line_color};margin-top:11px;min-width:12px;"></div>')

        parts.append(
            '<div style="display:flex;flex-direction:column;align-items:center;gap:4px;min-width:56px;">'
            f'<div style="width:22px;height:22px;border-radius:50%;display:flex;align-items:center;'
            f'justify-content:center;font-size:0.68rem;font-weight:600;{circle_style}">{circle}</div>'
            f'<div style="font-size:0.68rem;white-space:nowrap;{label_style}">{label}</div>'
            "</div>"
        )

    st.markdown(
        f'<div style="display:flex;align-items:flex-start;padding:2px 0 22px 0;">{"".join(parts)}</div>',
        unsafe_allow_html=True,
    )


def status_badge(label: str, tone: str) -> str:
    """Returns an HTML pill badge. tone: green | yellow | red | gray."""
    colors = {
        "green": ("#F0FDF4", "#15803D", "#BBF7D0"),
        "yellow": ("#FFFBEB", "#B45309", "#FDE68A"),
        "red": ("#FEF2F2", "#B91C1C", "#FECACA"),
        "gray": ("#FAFAF9", "#71717A", "#E4E4E7"),
    }
    bg, fg, border = colors.get(tone, colors["gray"])
    return (
        f'<span style="background:{bg};color:{fg};border:1px solid {border};padding:3px 10px;'
        f'border-radius:6px;font-weight:500;font-size:0.82rem;display:inline-block;">{label}</span>'
    )


def status_card(label: str, description: str, tone: str) -> None:
    """A single prominent status card (used by Eligibility) -- only this card
    carries the semantic color, not the whole page."""
    colors = {
        "green": ("#F0FDF4", "#BBF7D0", "#15803D", "🟢"),
        "yellow": ("#FFFBEB", "#FDE68A", "#B45309", "🟡"),
        "red": ("#FEF2F2", "#FECACA", "#B91C1C", "🔴"),
        "gray": ("#FAFAF9", "#E4E4E7", "#71717A", "⚪"),
    }
    bg, border, fg, icon = colors.get(tone, colors["gray"])
    st.markdown(
        f"""
        <div style="background:{bg};border:1px solid {border};border-radius:10px;padding:20px 22px;">
          <div style="display:flex;align-items:center;gap:10px;">
            <div style="font-size:1.3rem;line-height:1;flex-shrink:0;">{icon}</div>
            <div style="font-size:1.05rem;font-weight:650;color:{fg};">{label}</div>
          </div>
          <div style="color:#3F3F46;margin-top:8px;font-size:0.92rem;">{description}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


REQUIREMENT_STATUS_DISPLAY = {
    "meets": ("green", "Meets"),
    "does_not_meet": ("red", "Does Not Meet"),
    "potential_issue": ("yellow", "Potential Issue"),
    "not_mentioned": ("gray", "Not Mentioned"),
    "needs_verification": ("yellow", "Needs Verification"),
}


def requirement_row(label: str, status: str, detail: str) -> None:
    """One row of the eligibility requirement breakdown -- label, a small
    status badge, and the reasoning/detail text underneath."""
    tone, status_label = REQUIREMENT_STATUS_DISPLAY.get(status, ("gray", status.replace("_", " ").title()))
    st.markdown(
        f"""
        <div style="padding:10px 0;border-bottom:1px solid var(--border);">
          <div style="display:flex;align-items:center;justify-content:space-between;gap:10px;">
            <div style="font-weight:600;font-size:0.9rem;color:var(--ink);">{label}</div>
            {status_badge(status_label, tone)}
          </div>
          <div style="color:var(--muted);font-size:0.85rem;margin-top:3px;">{detail}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def initials(name: str | None, email: str) -> str:
    source = (name or email or "?").strip()
    parts = [p for p in source.replace(".", " ").replace("@", " ").split() if p]
    if not parts:
        return "?"
    if len(parts) == 1:
        return parts[0][:2].upper()
    return (parts[0][0] + parts[1][0]).upper()

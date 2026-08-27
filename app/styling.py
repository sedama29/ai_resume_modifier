"""Shared visual styling injected on every page. One place to keep the look
consistent -- call inject_custom_css() right after st.set_page_config()."""
import streamlit as st

_CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');

:root {
    --ink: #0B1220;
    --muted: #667085;
    --line: #E4E7EC;
    --accent: #1F5EFF;
}

html, body, [class*="css"], .stMarkdown, .stText {
    font-family: 'Inter', -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif !important;
}

.block-container { padding-top: 3rem; max-width: 1140px; }

/* --- Headers --- */
h1 { font-weight: 650 !important; letter-spacing: -0.02em; color: var(--ink); }
h2, h3 { font-weight: 600 !important; letter-spacing: -0.01em; color: var(--ink); }
h2 { font-size: 1.25rem !important; }
h3 { font-size: 1.05rem !important; }
[data-testid="stCaptionContainer"] { color: var(--muted) !important; }
hr { border-color: var(--line); }

/* --- Buttons: flat, restrained --- */
.stButton > button, .stFormSubmitButton > button, .stDownloadButton > button {
    border-radius: 6px;
    font-weight: 500;
    border: 1px solid var(--line);
    background: #FFFFFF;
    color: var(--ink);
    box-shadow: none;
    transition: background 0.12s ease, border-color 0.12s ease;
}
.stButton > button:hover, .stFormSubmitButton > button:hover, .stDownloadButton > button:hover {
    background: #F7F8FA;
    border-color: #C9CFD9;
    color: var(--ink);
}
.stButton > button[kind="primary"], .stFormSubmitButton > button[kind="primary"] {
    background: var(--accent);
    border-color: var(--accent);
    color: #FFFFFF;
}
.stButton > button[kind="primary"]:hover, .stFormSubmitButton > button[kind="primary"]:hover {
    background: #1A4FD8;
    border-color: #1A4FD8;
    color: #FFFFFF;
}

/* --- Card-style bordered containers --- */
div[data-testid="stVerticalBlockBorderWrapper"] {
    border-radius: 8px !important;
    border-color: var(--line) !important;
    box-shadow: none;
}

/* --- Metrics --- */
div[data-testid="stMetric"] {
    background: #FFFFFF;
    border: 1px solid var(--line);
    border-radius: 8px;
    padding: 14px 16px;
}
div[data-testid="stMetricValue"] { color: var(--ink); font-weight: 600; }

/* --- Inputs --- */
.stTextInput input, .stTextArea textarea, .stNumberInput input, div[data-baseweb="select"] {
    border-radius: 6px !important;
}

/* --- Sidebar --- */
section[data-testid="stSidebar"] {
    background: #FBFBFC;
    border-right: 1px solid var(--line);
}
section[data-testid="stSidebar"] .block-container { padding-top: 2rem; }
section[data-testid="stSidebar"] a {
    border-radius: 6px;
    font-weight: 500;
}
section[data-testid="stSidebar"] a:hover { background: #F0F1F4; }
section[data-testid="stSidebar"] [aria-current="page"] {
    background: #EDF1FF !important;
    color: var(--accent) !important;
}

/* --- Alerts --- */
div[data-testid="stAlert"] { border-radius: 8px; }
</style>
"""


def inject_custom_css() -> None:
    st.markdown(_CSS, unsafe_allow_html=True)


def page_header(title: str, subtitle: str = "") -> None:
    """Plain, typographic page heading -- no icons, no decoration."""
    subtitle_html = (
        f'<div style="color:#667085;font-size:0.95rem;margin-top:4px;max-width:70ch;">{subtitle}</div>'
        if subtitle
        else ""
    )
    st.markdown(
        f"""
        <div style="padding:0 0 20px 0;border-bottom:1px solid #E4E7EC;margin-bottom:24px;">
          <div style="font-size:1.6rem;font-weight:650;letter-spacing:-0.02em;color:#0B1220;">{title}</div>
          {subtitle_html}
        </div>
        """,
        unsafe_allow_html=True,
    )


_FLOW_STEPS = [
    ("job_input", "Job Input"),
    ("eligibility", "Eligibility"),
    ("match", "Match"),
    ("questions", "Questions"),
    ("review", "Review"),
    ("generate", "Generate"),
]


def progress_stepper(current_key: str) -> None:
    """Horizontal stepper across the top of each flow page -- numbered steps,
    with completed and current steps in the accent colour."""
    keys = [k for k, _ in _FLOW_STEPS]
    current_idx = keys.index(current_key) if current_key in keys else -1

    parts = []
    for idx, (_key, label) in enumerate(_FLOW_STEPS):
        if idx < current_idx:
            circle_style = "background:#EDF1FF;color:#1F5EFF;border:1px solid #C7D5FF;"
            label_style = "color:#667085;font-weight:500;"
        elif idx == current_idx:
            circle_style = "background:#1F5EFF;color:#FFFFFF;border:1px solid #1F5EFF;"
            label_style = "color:#0B1220;font-weight:600;"
        else:
            circle_style = "background:#FFFFFF;color:#98A2B3;border:1px solid #E4E7EC;"
            label_style = "color:#98A2B3;font-weight:500;"

        if idx > 0:
            line_color = "#1F5EFF" if idx <= current_idx else "#E4E7EC"
            parts.append(
                f'<div style="flex:1;height:1px;background:{line_color};margin-top:13px;min-width:16px;"></div>'
            )

        parts.append(
            '<div style="display:flex;flex-direction:column;align-items:center;gap:6px;min-width:64px;">'
            f'<div style="width:26px;height:26px;border-radius:50%;display:flex;align-items:center;'
            f'justify-content:center;font-size:0.75rem;font-weight:600;{circle_style}">{idx + 1}</div>'
            f'<div style="font-size:0.72rem;white-space:nowrap;{label_style}">{label}</div>'
            "</div>"
        )

    st.markdown(
        f'<div style="display:flex;align-items:flex-start;padding:0 0 28px 0;">{"".join(parts)}</div>',
        unsafe_allow_html=True,
    )


def status_badge(label: str, tone: str) -> str:
    """Returns an HTML pill badge. tone: green | yellow | red | gray."""
    colors = {
        "green": ("#ECFDF3", "#067647", "#ABEFC6"),
        "yellow": ("#FFFAEB", "#B54708", "#FEDF89"),
        "red": ("#FEF3F2", "#B42318", "#FECDCA"),
        "gray": ("#F9FAFB", "#475467", "#E4E7EC"),
    }
    bg, fg, border = colors.get(tone, colors["gray"])
    return (
        f'<span style="background:{bg};color:{fg};border:1px solid {border};padding:3px 10px;'
        f'border-radius:6px;font-weight:500;font-size:0.82rem;display:inline-block;">{label}</span>'
    )

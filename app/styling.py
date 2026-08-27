"""Shared visual styling injected on every page. One place to keep the look
consistent -- call inject_custom_css() right after st.set_page_config()."""
import streamlit as st

_CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap');

html, body, [class*="css"], .stMarkdown, .stText {
    font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif !important;
}

/* --- Headers --- */
h1 { font-weight: 800 !important; letter-spacing: -0.02em; color: #0F172A; }
h2, h3 { font-weight: 700 !important; letter-spacing: -0.01em; color: #0F172A; }
[data-testid="stCaptionContainer"] { color: #64748B !important; }

/* --- Buttons --- */
.stButton > button, .stFormSubmitButton > button {
    border-radius: 8px;
    font-weight: 600;
    border: 1px solid #E2E8F0;
    transition: all 0.15s ease;
}
.stButton > button:hover, .stFormSubmitButton > button:hover {
    border-color: #2563EB;
    color: #2563EB;
}
.stButton > button[kind="primary"], .stFormSubmitButton > button[kind="primary"] {
    background: linear-gradient(135deg, #2563EB 0%, #4F46E5 100%);
    border: none;
    box-shadow: 0 1px 3px rgba(37,99,235,0.35);
}
.stButton > button[kind="primary"]:hover, .stFormSubmitButton > button[kind="primary"]:hover {
    box-shadow: 0 6px 16px rgba(37,99,235,0.4);
    transform: translateY(-1px);
    color: white;
}

/* --- Card-style bordered containers --- */
div[data-testid="stVerticalBlockBorderWrapper"] {
    border-radius: 12px !important;
    border-color: #E5E7EB !important;
    box-shadow: 0 1px 2px rgba(0,0,0,0.04);
}

/* --- Metrics --- */
div[data-testid="stMetric"] {
    background: linear-gradient(135deg, #F8FAFC 0%, #EFF6FF 100%);
    border: 1px solid #E2E8F0;
    border-radius: 12px;
    padding: 14px 16px;
}
div[data-testid="stMetricValue"] { color: #1E3A8A; font-weight: 800; }

/* --- Inputs --- */
.stTextInput input, .stTextArea textarea, .stNumberInput input, div[data-baseweb="select"] {
    border-radius: 8px !important;
}

/* --- Sidebar: dark, modern --- */
section[data-testid="stSidebar"] {
    background: linear-gradient(180deg, #0F172A 0%, #111827 100%);
}
section[data-testid="stSidebar"] * {
    color: #E2E8F0 !important;
}
section[data-testid="stSidebar"] [data-testid="stCaptionContainer"] {
    color: #94A3B8 !important;
}
section[data-testid="stSidebar"] a {
    border-radius: 8px;
}
section[data-testid="stSidebar"] a:hover {
    background: rgba(255,255,255,0.06);
}
section[data-testid="stSidebar"] [aria-current="page"] {
    background: rgba(37,99,235,0.25) !important;
    font-weight: 600;
}
section[data-testid="stSidebar"] .stButton > button {
    border-color: #334155;
    background: transparent;
    color: #E2E8F0;
}
section[data-testid="stSidebar"] .stButton > button:hover {
    border-color: #EF4444;
    color: #F87171 !important;
}

/* --- Alerts --- */
div[data-testid="stAlert"] { border-radius: 10px; }
</style>
"""


def inject_custom_css() -> None:
    st.markdown(_CSS, unsafe_allow_html=True)


def page_header(icon: str, title: str, subtitle: str = "") -> None:
    """Replaces bare st.title() -- a bigger, icon-led header consistent with
    the sign-in hero's style instead of Streamlit's plain default heading."""
    subtitle_html = f'<div style="color:#64748B;font-size:1.05em;margin-top:2px;">{subtitle}</div>' if subtitle else ""
    st.markdown(
        f"""
        <div style="padding:4px 0 8px 0;">
          <div style="font-size:2em;font-weight:800;letter-spacing:-0.02em;color:#0F172A;
                      display:flex;align-items:center;gap:12px;">
            <span style="font-size:1.05em;">{icon}</span> {title}
          </div>
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
    """Horizontal stepper across the top of each flow page -- completed steps
    checked, current step highlighted, future steps dimmed."""
    keys = [k for k, _ in _FLOW_STEPS]
    current_idx = keys.index(current_key) if current_key in keys else -1

    parts = []
    for idx, (key, label) in enumerate(_FLOW_STEPS):
        if idx < current_idx:
            circle, circle_style, label_style = "✓", "background:#2563EB;color:white;", "color:#2563EB;font-weight:600;"
        elif idx == current_idx:
            circle, circle_style = str(idx + 1), "background:#2563EB;color:white;box-shadow:0 0 0 4px rgba(37,99,235,0.15);"
            label_style = "color:#0F172A;font-weight:700;"
        else:
            circle, circle_style, label_style = str(idx + 1), "background:#E2E8F0;color:#94A3B8;", "color:#94A3B8;font-weight:500;"

        if idx > 0:
            line_color = "#2563EB" if idx <= current_idx else "#E2E8F0"
            parts.append(f'<div style="flex:1;height:2px;background:{line_color};margin-top:15px;min-width:20px;"></div>')

        parts.append(
            '<div style="display:flex;flex-direction:column;align-items:center;gap:4px;min-width:64px;">'
            f'<div style="width:30px;height:30px;border-radius:50%;display:flex;align-items:center;justify-content:center;'
            f'font-size:0.8em;font-weight:700;{circle_style}">{circle}</div>'
            f'<div style="font-size:0.75em;white-space:nowrap;{label_style}">{label}</div>'
            "</div>"
        )

    st.markdown(
        f'<div style="display:flex;align-items:flex-start;padding:4px 0 24px 0;">{"".join(parts)}</div>',
        unsafe_allow_html=True,
    )


def status_badge(label: str, tone: str) -> str:
    """Returns an HTML pill badge. tone: green | yellow | red | gray."""
    colors = {
        "green": ("#DCFCE7", "#166534"),
        "yellow": ("#FEF9C3", "#854D0E"),
        "red": ("#FEE2E2", "#991B1B"),
        "gray": ("#F1F5F9", "#475569"),
    }
    bg, fg = colors.get(tone, colors["gray"])
    return (
        f'<span style="background:{bg};color:{fg};padding:4px 12px;border-radius:999px;'
        f'font-weight:600;font-size:0.85em;display:inline-block;">{label}</span>'
    )

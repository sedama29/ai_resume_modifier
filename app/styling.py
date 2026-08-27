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

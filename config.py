import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()


def _get_secret(key: str, default: str = "") -> str:
    """Local dev reads .env via os.environ; on Streamlit Community Cloud (no
    local .env, no filesystem access to secrets/) the same key is read from
    st.secrets (set in the app's Advanced Settings -> Secrets box) instead."""
    try:
        import streamlit as st

        if key in st.secrets:
            return st.secrets[key]
    except Exception:
        pass
    return os.environ.get(key, default)


BASE_DIR = Path(__file__).resolve().parent

GROQ_API_KEY = _get_secret("GROQ_API_KEY", "")
GROQ_MODEL = "openai/gpt-oss-120b"

MASTER_RESUME_PATH = str(BASE_DIR / "Resources" / "main.tex")

# Estimated Groq pricing for openai/gpt-oss-120b (per 1M tokens). Re-check
# against console.groq.com/docs/models if this needs to stay accurate long-term.
GROQ_INPUT_PRICE_PER_1M = 0.15
GROQ_OUTPUT_PRICE_PER_1M = 0.60

# --- Firebase ---
FIREBASE_SERVICE_ACCOUNT_PATH = os.environ.get(
    "FIREBASE_SERVICE_ACCOUNT_PATH",
    str(BASE_DIR / "secrets" / "ai-resume-modifier-firebase-adminsdk-fbsvc-0174734850.json"),
)
SUPERUSER_BOOTSTRAP_EMAIL = _get_secret("SUPERUSER_BOOTSTRAP_EMAIL", "sathwikareddy0799@gmail.com")

# Client-side Firebase config -- not a secret by Firebase's own design (security
# is enforced by Firestore rules + server-side ID token verification, not by
# hiding this object), safe to keep in source.
FIREBASE_CONFIG = {
    "apiKey": "AIzaSyDAbm7eAAnZD0APWzXG5aDedGGJ85rFcSg",
    "authDomain": "ai-resume-modifier.firebaseapp.com",
    "projectId": "ai-resume-modifier",
    "storageBucket": "ai-resume-modifier.firebasestorage.app",
    "messagingSenderId": "665190029564",
    "appId": "1:665190029564:web:941767076ad08887771f79",
}

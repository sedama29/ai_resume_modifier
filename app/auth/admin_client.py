"""Firebase Admin SDK singleton -- server-side identity verification and
Firestore access. Never exposes the service account key to the frontend."""
import firebase_admin
from firebase_admin import auth as fb_auth
from firebase_admin import credentials, firestore

from config import FIREBASE_SERVICE_ACCOUNT_PATH

_app: firebase_admin.App | None = None


def _build_credential() -> credentials.Certificate:
    """Local dev reads the service account JSON file from disk (gitignored,
    path in .env). Streamlit Community Cloud has no access to that file, so
    there we read the same fields from st.secrets['firebase_service_account']
    (a TOML table pasted into the app's Advanced Settings -> Secrets box)."""
    try:
        import streamlit as st

        if "firebase_service_account" in st.secrets:
            return credentials.Certificate(dict(st.secrets["firebase_service_account"]))
    except Exception:
        pass
    return credentials.Certificate(FIREBASE_SERVICE_ACCOUNT_PATH)


def get_app() -> firebase_admin.App:
    """Our own _app cache can get out of sync with firebase_admin's internal
    app registry under Streamlit's rerun/hot-reload model -- this module can
    be re-imported (resetting _app to None) while the underlying process (and
    firebase_admin's own already-initialized default app) is still alive.
    Falling back to firebase_admin.get_app() before initializing avoids a
    spurious 'default app already exists' ValueError in that case."""
    global _app
    if _app is not None:
        return _app
    try:
        _app = firebase_admin.get_app()
    except ValueError:
        _app = firebase_admin.initialize_app(_build_credential())
    return _app


def get_firestore():
    get_app()
    return firestore.client()


def verify_id_token(id_token: str) -> dict:
    """Verifies a Firebase ID token server-side. Raises on an invalid/expired/
    forged token -- callers must not treat a raised exception as "signed out",
    only as "reject this request"."""
    get_app()
    return fb_auth.verify_id_token(id_token)


def get_user_by_email(email: str):
    get_app()
    return fb_auth.get_user_by_email(email)

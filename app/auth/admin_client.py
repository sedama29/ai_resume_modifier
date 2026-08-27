"""Firebase Admin SDK singleton -- server-side identity verification and
Firestore access. Never exposes the service account key to the frontend."""
import firebase_admin
from firebase_admin import auth as fb_auth
from firebase_admin import credentials, firestore

from config import FIREBASE_SERVICE_ACCOUNT_PATH

_app: firebase_admin.App | None = None


def get_app() -> firebase_admin.App:
    global _app
    if _app is None:
        cred = credentials.Certificate(FIREBASE_SERVICE_ACCOUNT_PATH)
        _app = firebase_admin.initialize_app(cred)
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

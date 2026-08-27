"""Firestore-backed authorized_users collection. Document ID = lowercased
email -- the superuser adds people by email before they've ever signed in,
so a Firebase uid (which doesn't exist until first login) can't be the key."""
from datetime import datetime, timezone

from app.auth.admin_client import get_firestore
from config import SUPERUSER_BOOTSTRAP_EMAIL

_COLLECTION = "authorized_users"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def get_authorization(email: str) -> dict | None:
    email = email.lower()
    db = get_firestore()
    doc = db.collection(_COLLECTION).document(email).get()
    if doc.exists:
        return doc.to_dict()

    # Bootstrap: nobody can use the admin UI to authorize the very first user,
    # since nobody has admin access yet. This fallback only fires when NO
    # Firestore doc exists for this email -- after the first login it's
    # persisted and every subsequent check is purely Firestore-driven.
    if email == SUPERUSER_BOOTSTRAP_EMAIL.lower():
        record = {
            "email": email, "role": "superuser", "active": True,
            "uid": None, "added_by": "bootstrap", "added_at": _now(),
        }
        db.collection(_COLLECTION).document(email).set(record)
        return record

    return None


def record_login(email: str, uid: str) -> None:
    email = email.lower()
    get_firestore().collection(_COLLECTION).document(email).set({"uid": uid}, merge=True)


def add_user(email: str, added_by: str) -> None:
    email = email.lower()
    get_firestore().collection(_COLLECTION).document(email).set({
        "email": email, "role": "user", "active": True,
        "uid": None, "added_by": added_by, "added_at": _now(),
    })


def set_user_active(email: str, active: bool) -> None:
    email = email.lower()
    get_firestore().collection(_COLLECTION).document(email).set({"active": active}, merge=True)


def delete_user(email: str) -> None:
    email = email.lower()
    get_firestore().collection(_COLLECTION).document(email).delete()


def list_users() -> list[dict]:
    db = get_firestore()
    return [doc.to_dict() for doc in db.collection(_COLLECTION).stream()]

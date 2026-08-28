"""Thin wrapper around the Firebase Storage bucket. Uses the same service-
account credential as Firestore/Auth (app/auth/admin_client.py) -- Admin SDK
access bypasses Storage security rules entirely, same as Firestore. The real
enforcement today is that every call here is already gated by an owner_uid
check in the caller (see app/state.py's require_user()); storage.rules (repo
root) exists as defense-in-depth for if direct client-SDK access is ever
added later -- every path below is uid-prefixed so ownership is derivable
from the path alone, which is what makes that file able to say anything
meaningful.

Path conventions:
  masters/{uid}/main.tex                                     user's uploaded master resume source
  masters/{uid}/main.pdf                                     its compiled PDF
  masters/{uid}/assets/{filename}                            supporting project files (images, .sty, .bib, fonts)
  applications/{uid}/{application_id}/{version_name}.tex     generated resume source per version
  applications/{uid}/{application_id}/{version_name}.pdf     compiled PDF per version
"""
from datetime import timedelta

from firebase_admin import storage as fb_storage

from app.auth.admin_client import get_app
from config import FIREBASE_CONFIG


def _bucket():
    return fb_storage.bucket(FIREBASE_CONFIG["storageBucket"], app=get_app())


def upload_text(storage_path: str, content: str) -> None:
    _bucket().blob(storage_path).upload_from_string(content, content_type="text/plain; charset=utf-8")


def upload_bytes(storage_path: str, content: bytes, content_type: str) -> None:
    _bucket().blob(storage_path).upload_from_string(content, content_type=content_type)


def download_text(storage_path: str) -> str:
    return _bucket().blob(storage_path).download_as_text()


def download_bytes(storage_path: str) -> bytes:
    return _bucket().blob(storage_path).download_as_bytes()


def blob_exists(storage_path: str) -> bool:
    return _bucket().blob(storage_path).exists()


def generate_signed_url(storage_path: str, expiration_minutes: int = 15) -> str:
    """A short-lived, publicly-fetchable URL for an otherwise-private blob --
    used only for the "Open in Overleaf" link, since Overleaf's own server
    (not this app, not the user's browser) has to be able to fetch the file
    to seed a new project from it."""
    return _bucket().blob(storage_path).generate_signed_url(
        version="v4", expiration=timedelta(minutes=expiration_minutes), method="GET"
    )

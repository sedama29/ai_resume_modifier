"""Thin wrapper around the Firebase Storage bucket. Uses the same service-
account credential as Firestore/Auth (app/auth/admin_client.py) -- Admin SDK
access bypasses Storage security rules entirely, same as Firestore, so there
is no rules file to maintain here: every call is already gated by an
owner_uid check in the caller before this module is touched.

Path conventions:
  masters/{uid}/main.tex                              user's uploaded master resume source
  applications/{application_id}/{version_name}.tex     generated resume source per version
  applications/{application_id}/{version_name}.pdf     compiled PDF per version
"""
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

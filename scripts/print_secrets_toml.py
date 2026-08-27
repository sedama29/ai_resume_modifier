"""
Run this YOURSELF locally (do not share its output in chat):

    .venv/bin/python scripts/print_secrets_toml.py

Prints a ready-to-paste TOML block for Streamlit Community Cloud's
"Advanced settings -> Secrets" box, built from your local .env and the
Firebase service account JSON file. Copy the printed output directly into
that box -- nothing here is written to disk or sent anywhere.
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from config import FIREBASE_SERVICE_ACCOUNT_PATH, GROQ_API_KEY, SUPERUSER_BOOTSTRAP_EMAIL


def toml_escape(value: str) -> str:
    return value.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n")


def main() -> None:
    sa_path = Path(FIREBASE_SERVICE_ACCOUNT_PATH)
    if not sa_path.exists():
        print(f"Service account file not found at {sa_path}", file=sys.stderr)
        sys.exit(1)
    sa = json.loads(sa_path.read_text())

    print(f'GROQ_API_KEY = "{toml_escape(GROQ_API_KEY)}"')
    print(f'SUPERUSER_BOOTSTRAP_EMAIL = "{toml_escape(SUPERUSER_BOOTSTRAP_EMAIL)}"')
    print()
    print("[firebase_service_account]")
    for key in [
        "type", "project_id", "private_key_id", "private_key", "client_email",
        "client_id", "auth_uri", "token_uri", "auth_provider_x509_cert_url",
        "client_x509_cert_url", "universe_domain",
    ]:
        if key in sa:
            print(f'{key} = "{toml_escape(sa[key])}"')


if __name__ == "__main__":
    main()

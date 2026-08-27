"""One-off backfill: run this ONCE after the superuser has signed in at least
one time (their Firebase uid doesn't exist before that first login).

Usage:
    .venv/bin/python -m db.migrate_add_multitenancy

Backs up storage/app.db to storage/app.db.bak before making any changes.
Safe to re-run -- ALTER TABLE ADD COLUMN is skipped if the column already
exists, and the UPDATE only touches rows where owner_uid IS NULL.
"""
import shutil
import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.auth.admin_client import get_user_by_email
from config import DB_PATH, SUPERUSER_BOOTSTRAP_EMAIL

TABLES = ["master_resume_versions", "candidate_profile", "job_applications"]


def _add_column_if_missing(conn: sqlite3.Connection, table: str) -> None:
    cols = [row[1] for row in conn.execute(f"PRAGMA table_info({table})")]
    if "owner_uid" not in cols:
        conn.execute(f"ALTER TABLE {table} ADD COLUMN owner_uid TEXT")
        print(f"  added owner_uid column to {table}")
    else:
        print(f"  {table} already has owner_uid")


def main() -> None:
    db_path = Path(DB_PATH)
    if not db_path.exists():
        print(f"No database found at {db_path} -- nothing to migrate.")
        return

    backup_path = db_path.with_suffix(db_path.suffix + ".bak")
    shutil.copy2(db_path, backup_path)
    print(f"Backed up {db_path} -> {backup_path}")

    try:
        user = get_user_by_email(SUPERUSER_BOOTSTRAP_EMAIL)
    except Exception as e:
        print(f"Could not resolve {SUPERUSER_BOOTSTRAP_EMAIL} in Firebase: {e}")
        print("Sign in as the superuser in the app at least once before running this migration.")
        sys.exit(1)

    uid = user.uid
    print(f"Resolved {SUPERUSER_BOOTSTRAP_EMAIL} -> uid={uid}")

    conn = sqlite3.connect(str(db_path))
    try:
        for table in TABLES:
            _add_column_if_missing(conn, table)
        conn.commit()

        for table in TABLES:
            cur = conn.execute(f"UPDATE {table} SET owner_uid = ? WHERE owner_uid IS NULL", (uid,))
            print(f"  backfilled {cur.rowcount} row(s) in {table}")
        conn.commit()
    finally:
        conn.close()

    print("Migration complete.")


if __name__ == "__main__":
    main()

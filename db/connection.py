import sqlite3
from pathlib import Path

from config import DB_PATH

_SCHEMA_PATH = Path(__file__).resolve().parent / "schema.sql"


def get_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def init_db() -> None:
    Path(DB_PATH).parent.mkdir(parents=True, exist_ok=True)
    conn = get_connection()
    try:
        conn.executescript(_SCHEMA_PATH.read_text())
        conn.commit()
    finally:
        conn.close()

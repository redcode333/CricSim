"""
save_manager.py
One save slot per user per mode, backed by Postgres (Neon). Public function
signatures are unchanged from the old JSON-file version, so every caller
(api/routes/tournament.py, api/routes/draft.py, api/routes/saves.py, and the
CLI modes) needs no changes.
"""
import json
from datetime import datetime
from typing import Optional

from psycopg2.extras import Json

from engine.db import get_conn


def save_exists(username: str, mode: str) -> bool:
    key = username.lower()
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute(
            "SELECT 1 FROM saves WHERE username_key = %s AND mode = %s", (key, mode),
        )
        return cur.fetchone() is not None


def write_save(username: str, mode: str, state: dict):
    key = username.lower()
    state = dict(state)
    state["_saved_at"] = datetime.now().strftime("%Y-%m-%d %H:%M")
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO saves (username_key, mode, data, saved_at)
            VALUES (%s, %s, %s, now())
            ON CONFLICT (username_key, mode)
            DO UPDATE SET data = EXCLUDED.data, saved_at = EXCLUDED.saved_at
            """,
            (key, mode, Json(state)),
        )


def read_save(username: str, mode: str) -> Optional[dict]:
    key = username.lower()
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute(
            "SELECT data FROM saves WHERE username_key = %s AND mode = %s", (key, mode),
        )
        row = cur.fetchone()
    if not row:
        return None
    data = row[0]
    # psycopg2 usually deserializes JSONB to a dict already; guard for drivers
    # that return the raw JSON string instead.
    return data if isinstance(data, dict) else json.loads(data)


def delete_save(username: str, mode: str):
    key = username.lower()
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute(
            "DELETE FROM saves WHERE username_key = %s AND mode = %s", (key, mode),
        )


def save_hint(username: str, mode: str) -> Optional[str]:
    """Short string for main menu display. Returns None if no save exists."""
    data = read_save(username, mode)
    if not data:
        return None
    hint = data.get("_summary", "saved game")
    ts = data.get("_saved_at", "")
    return f"{hint}  (saved {ts})" if ts else hint

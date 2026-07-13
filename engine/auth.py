"""
auth.py
Account system backed by Postgres (Neon): SHA-256 + random salt per user.
Public function signatures are unchanged from the old JSON-file version, so
every caller (api/routes/auth.py) needs no changes.
"""
import hashlib
import secrets

from engine.db import get_conn


def _hash(password: str, salt: str) -> str:
    return hashlib.sha256(f"{salt}{password}".encode()).hexdigest()


def register(username: str, password: str) -> tuple[bool, str]:
    """Returns (ok, username_key | error_message)."""
    key = username.strip().lower()
    if len(key) < 3:
        return False, "Username must be at least 3 characters."
    if not password:
        return False, "Password cannot be empty."

    salt = secrets.token_hex(16)
    password_hash = _hash(password, salt)

    with get_conn() as conn, conn.cursor() as cur:
        cur.execute("SELECT 1 FROM users WHERE username_key = %s", (key,))
        if cur.fetchone():
            return False, "Username already taken."
        cur.execute(
            "INSERT INTO users (username_key, password_hash, salt, display, method) "
            "VALUES (%s, %s, %s, %s, 'password')",
            (key, password_hash, salt, username.strip()),
        )
    return True, key


def login(username: str, password: str) -> tuple[bool, str]:
    """Returns (ok, username_key | error_message)."""
    key = username.strip().lower()
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute("SELECT password_hash, salt FROM users WHERE username_key = %s", (key,))
        row = cur.fetchone()
    if not row:
        return False, "Username not found."
    password_hash, salt = row
    if _hash(password, salt) != password_hash:
        return False, "Incorrect password."
    return True, key


def display_name(username: str) -> str:
    key = username.lower()
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute("SELECT display FROM users WHERE username_key = %s", (key,))
        row = cur.fetchone()
    return row[0] if row else username


def get_or_create_google_user(google_id: str, email: str, name: str) -> str:
    """Find or create an account for a Google-authenticated user. Returns the
    username_key (a stable 'g_<google_id>' key). Used by the Google OAuth
    callback in api/routes/auth.py."""
    key = f"g_{google_id}"
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute("SELECT 1 FROM users WHERE username_key = %s", (key,))
        if not cur.fetchone():
            salt = secrets.token_hex(16)
            random_pw = secrets.token_hex(16)
            cur.execute(
                "INSERT INTO users (username_key, password_hash, salt, display, email, method) "
                "VALUES (%s, %s, %s, %s, %s, 'google')",
                (key, _hash(random_pw, salt), salt, name, email),
            )
    return key

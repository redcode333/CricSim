"""
db.py
Shared Postgres connection pool + schema bootstrap for engine/auth.py and
engine/save_manager.py. Backed by Neon (or any Postgres) via DATABASE_URL.
"""
import os
from contextlib import contextmanager

import psycopg2
import psycopg2.pool

_pool = None


def _get_pool():
    global _pool
    if _pool is None:
        dsn = os.environ.get("DATABASE_URL")
        if not dsn:
            raise RuntimeError(
                "DATABASE_URL is not set. Set it to your Neon connection string "
                "(see .env.example)."
            )
        _pool = psycopg2.pool.SimpleConnectionPool(1, 5, dsn)
    return _pool


@contextmanager
def get_conn():
    """Yield a pooled connection, committing on success and rolling back on error."""
    pool = _get_pool()
    conn = pool.getconn()
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        pool.putconn(conn)


def init_db():
    """Create the users/saves tables if they don't already exist. Safe to call
    on every startup."""
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute("""
            CREATE TABLE IF NOT EXISTS users (
                username_key TEXT PRIMARY KEY,
                password_hash TEXT NOT NULL,
                salt TEXT NOT NULL,
                display TEXT NOT NULL,
                email TEXT,
                method TEXT NOT NULL DEFAULT 'password'
            )
        """)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS saves (
                username_key TEXT NOT NULL,
                mode TEXT NOT NULL,
                data JSONB NOT NULL,
                saved_at TIMESTAMPTZ NOT NULL DEFAULT now(),
                PRIMARY KEY (username_key, mode)
            )
        """)

import sqlite3
import json
import time
from pathlib import Path

DB_PATH = Path("data/cache.db")


def get_conn():
    DB_PATH.parent.mkdir(exist_ok=True)

    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA synchronous=NORMAL;")
    conn.execute("PRAGMA foreign_keys=ON;")
    return conn


def _ensure_cache_table(conn):
    conn.execute("""
        CREATE TABLE IF NOT EXISTS cache (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL,
            created_at INTEGER NOT NULL,
            ttl INTEGER NOT NULL
        )
    """)
    conn.commit()


def init_cache():
    conn = get_conn()

    _ensure_cache_table(conn)
    conn.commit()
    conn.close()


def get_cache_entry(key, allow_expired: bool = False):
    conn = get_conn()
    _ensure_cache_table(conn)

    row = conn.execute(
        "SELECT value, created_at, ttl FROM cache WHERE key = ?",
        (key,)
    ).fetchone()

    conn.close()

    if row is None:
        return None

    value, created_at, ttl = row
    age_seconds = int(time.time()) - created_at
    is_expired = age_seconds > ttl

    if is_expired and not allow_expired:
        return None

    return {
        "value": json.loads(value),
        "created_at": created_at,
        "ttl": ttl,
        "age_seconds": age_seconds,
        "is_expired": is_expired,
    }


def get_cache(key, allow_expired: bool = False):
    entry = get_cache_entry(key, allow_expired=allow_expired)
    if entry is None:
        return None
    return entry["value"]


def set_cache(key, value, ttl):
    conn = get_conn()
    _ensure_cache_table(conn)

    conn.execute(
        """
        INSERT OR REPLACE INTO cache (key, value, created_at, ttl)
        VALUES (?, ?, ?, ?)
        """,
        (key, json.dumps(value, default=str), int(time.time()), ttl)
    )

    conn.commit()
    conn.close()


def clear_cache():
    conn = get_conn()
    _ensure_cache_table(conn)
    conn.execute("DELETE FROM cache")
    conn.commit()
    conn.close()

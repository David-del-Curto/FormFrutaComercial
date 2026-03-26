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


def init_cache():
    conn = get_conn()

    conn.execute("""
        CREATE TABLE IF NOT EXISTS cache (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL,
            created_at INTEGER NOT NULL,
            ttl INTEGER NOT NULL
        )
    """)

    conn.commit()
    conn.close()


def get_cache(key):
    conn = get_conn()

    row = conn.execute(
        "SELECT value, created_at, ttl FROM cache WHERE key = ?",
        (key,)
    ).fetchone()

    conn.close()

    if row is None:
        return None

    value, created_at, ttl = row

    if int(time.time()) - created_at > ttl:
        return None

    return json.loads(value)


def set_cache(key, value, ttl):
    conn = get_conn()

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
    conn.execute("DELETE FROM cache")
    conn.commit()
    conn.close()

"""Persistence: Postgres when DATABASE_URL is set (e.g. a free Neon database), SQLite otherwise.

Tables
  reports      citizen flood reports (+ optional downscaled photo and its verification score)
  subscribers  people who opted in to WhatsApp / SMS alerts for one location
  alert_log    every alert sent (or attempted), for audit and de-duplication
"""

from __future__ import annotations

import os
import secrets
import sqlite3
import threading
from contextlib import contextmanager
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

SCHEMA = [
    """CREATE TABLE IF NOT EXISTS reports (
        id {pk}, created_at TEXT, lat REAL, lon REAL, category TEXT, depth TEXT, note TEXT, lang TEXT,
        auto_category TEXT, urgent INTEGER DEFAULT 0,
        photo {blob}, photo_flood_prob REAL, photo_verified INTEGER)""",
    """CREATE TABLE IF NOT EXISTS subscribers (
        id {pk}, created_at TEXT, channel TEXT, phone TEXT, lang TEXT, lat REAL, lon REAL, label TEXT,
        min_alert TEXT DEFAULT 'orange', active INTEGER DEFAULT 0, token TEXT, verified INTEGER DEFAULT 0,
        code_hash TEXT, code_expires TEXT, attempts INTEGER DEFAULT 0)""",
    """CREATE TABLE IF NOT EXISTS alert_log (
        id {pk}, created_at TEXT, subscriber_id INTEGER, alert_date TEXT, alert TEXT, channel TEXT,
        status TEXT, provider_id TEXT, detail TEXT)""",
]
# columns added after v0.1 (lightweight migrations for existing databases)
MIGRATIONS = {
    "subscribers": [("chat_id", "TEXT")],   # Telegram chat linked to the subscription
    "reports": [("auto_category", "TEXT"), ("urgent", "INTEGER DEFAULT 0"), ("photo", "{blob}"),
                ("photo_flood_prob", "REAL"), ("photo_verified", "INTEGER")],
}


class DB:
    def __init__(self, url: str | None = None, sqlite_path: str | None = None):
        self.url = url if url is not None else os.environ.get("DATABASE_URL")
        self.pg = bool(self.url and self.url.startswith(("postgres://", "postgresql://")))
        self.path = sqlite_path or os.environ.get("MS_DB", str(ROOT / "data" / "reports.sqlite"))
        self._lock = threading.Lock()
        self.init()

    @property
    def kind(self) -> str:
        return "postgres" if self.pg else "sqlite"

    @contextmanager
    def conn(self):
        if self.pg:
            import psycopg

            con = psycopg.connect(self.url, autocommit=False, connect_timeout=15)
        else:
            Path(self.path).parent.mkdir(parents=True, exist_ok=True)
            con = sqlite3.connect(self.path)
        try:
            yield con
            con.commit()
        finally:
            con.close()

    def _sql(self, q: str) -> str:
        return q.replace("?", "%s") if self.pg else q

    def execute(self, q: str, params: tuple = ()) -> int | None:
        """Run a statement; returns the new row id for INSERTs."""
        with self._lock, self.conn() as con:
            cur = con.cursor()
            if self.pg and q.lstrip().upper().startswith("INSERT"):
                cur.execute(self._sql(q) + " RETURNING id", params)
                return cur.fetchone()[0]
            cur.execute(self._sql(q), params)
            return getattr(cur, "lastrowid", None)

    def query(self, q: str, params: tuple = ()) -> list[dict]:
        with self._lock, self.conn() as con:
            cur = con.cursor()
            cur.execute(self._sql(q), params)
            cols = [d[0] for d in cur.description]
            return [dict(zip(cols, r)) for r in cur.fetchall()]

    def init(self):
        pk = "SERIAL PRIMARY KEY" if self.pg else "INTEGER PRIMARY KEY AUTOINCREMENT"
        blob = "BYTEA" if self.pg else "BLOB"
        with self._lock, self.conn() as con:
            cur = con.cursor()
            for s in SCHEMA:
                cur.execute(s.format(pk=pk, blob=blob))
            for table, cols in MIGRATIONS.items():
                if self.pg:
                    cur.execute("SELECT column_name FROM information_schema.columns WHERE table_name = %s", (table,))
                    have = {r[0] for r in cur.fetchall()}
                else:
                    have = {r[1] for r in cur.execute(f"PRAGMA table_info({table})")}
                for col, typ in cols:
                    if col not in have:
                        cur.execute(f"ALTER TABLE {table} ADD COLUMN {col} {typ.format(blob=blob)}")


def new_token() -> str:
    return secrets.token_urlsafe(16)

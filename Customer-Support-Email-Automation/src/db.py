"""
Lightweight SQLite persistence so the dashboard has something to show and
the workflow survives restarts. Deliberately dependency-free (stdlib
sqlite3 only) — this is an ops log, not a data warehouse.
"""
import json
import sqlite3
import threading
import time
from contextlib import contextmanager
from pathlib import Path

from .config import settings

_lock = threading.Lock()


def _connect():
    Path(settings.db_path).parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(settings.db_path, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


@contextmanager
def get_conn():
    with _lock:
        conn = _connect()
        try:
            yield conn
            conn.commit()
        finally:
            conn.close()


def init_db():
    with get_conn() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS emails (
                id TEXT PRIMARY KEY,
                thread_id TEXT,
                sender TEXT,
                subject TEXT,
                body TEXT,
                category TEXT,
                generated_email TEXT,
                status TEXT,               -- queued, processing, draft_created, sent, rejected, skipped, failed
                trials INTEGER DEFAULT 0,
                error TEXT,
                writer_history TEXT,       -- JSON list of draft/feedback strings
                created_at REAL,
                updated_at REAL
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS events (
                event_id INTEGER PRIMARY KEY AUTOINCREMENT,
                email_id TEXT,
                node TEXT,
                message TEXT,
                level TEXT DEFAULT 'info', -- info, warn, error
                created_at REAL
            )
        """)
        conn.execute("CREATE INDEX IF NOT EXISTS idx_events_created ON events(created_at)")


def upsert_email(email_id, **fields):
    now = time.time()
    with get_conn() as conn:
        existing = conn.execute("SELECT id FROM emails WHERE id = ?", (email_id,)).fetchone()
        if existing:
            set_clause = ", ".join(f"{k} = ?" for k in fields)
            conn.execute(
                f"UPDATE emails SET {set_clause}, updated_at = ? WHERE id = ?",
                (*fields.values(), now, email_id),
            )
        else:
            cols = ["id", "created_at", "updated_at"] + list(fields.keys())
            vals = [email_id, now, now] + list(fields.values())
            placeholders = ", ".join(["?"] * len(vals))
            conn.execute(
                f"INSERT INTO emails ({', '.join(cols)}) VALUES ({placeholders})", vals
            )


def log_event(email_id, node, message, level="info"):
    with get_conn() as conn:
        conn.execute(
            "INSERT INTO events (email_id, node, message, level, created_at) VALUES (?, ?, ?, ?, ?)",
            (email_id, node, message, level, time.time()),
        )


def get_emails(status=None, limit=100):
    with get_conn() as conn:
        if status:
            rows = conn.execute(
                "SELECT * FROM emails WHERE status = ? ORDER BY updated_at DESC LIMIT ?",
                (status, limit),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM emails ORDER BY updated_at DESC LIMIT ?", (limit,)
            ).fetchall()
        return [dict(r) for r in rows]


def get_email(email_id):
    with get_conn() as conn:
        row = conn.execute("SELECT * FROM emails WHERE id = ?", (email_id,)).fetchone()
        return dict(row) if row else None


def get_events(email_id=None, limit=200):
    with get_conn() as conn:
        if email_id:
            rows = conn.execute(
                "SELECT * FROM events WHERE email_id = ? ORDER BY created_at ASC LIMIT ?",
                (email_id, limit),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM events ORDER BY created_at DESC LIMIT ?", (limit,)
            ).fetchall()
        return [dict(r) for r in rows]


def get_stats():
    with get_conn() as conn:
        total = conn.execute("SELECT COUNT(*) c FROM emails").fetchone()["c"]
        by_status = {
            r["status"]: r["c"]
            for r in conn.execute(
                "SELECT status, COUNT(*) c FROM emails GROUP BY status"
            ).fetchall()
        }
        by_category = {
            r["category"]: r["c"]
            for r in conn.execute(
                "SELECT category, COUNT(*) c FROM emails WHERE category IS NOT NULL GROUP BY category"
            ).fetchall()
        }
        avg_trials_row = conn.execute(
            "SELECT AVG(trials) a FROM emails WHERE trials > 0"
        ).fetchone()
        return {
            "total": total,
            "by_status": by_status,
            "by_category": by_category,
            "avg_trials": round(avg_trials_row["a"], 2) if avg_trials_row["a"] else 0,
        }


def append_writer_history(email_id, entry):
    email = get_email(email_id)
    history = json.loads(email["writer_history"]) if email and email.get("writer_history") else []
    history.append(entry)
    upsert_email(email_id, writer_history=json.dumps(history))
    return history

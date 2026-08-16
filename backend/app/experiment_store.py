"""
experiment_store.py
--------------------
Lightweight, real persistence for Experiment objects using SQLite (stdlib,
no new dependency). This is what makes "save / reopen / branch" actual
capabilities rather than aspirational ones -- experiments survive a server
restart, unlike the in-memory lru_cache used elsewhere in this backend.

Not a replacement for a production database (no multi-user auth, no
migrations tooling) -- but it's real durable storage, not a mock.
"""
from __future__ import annotations

import json
import sqlite3
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

DB_PATH = Path(__file__).resolve().parent / "experiments.sqlite3"


def _connect() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    with _connect() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS experiments (
                id TEXT PRIMARY KEY,
                label TEXT NOT NULL,
                mode TEXT NOT NULL,
                parent_id TEXT,
                created_at TEXT NOT NULL,
                annotation TEXT,
                payload TEXT NOT NULL
            )
        """)
        conn.execute("CREATE INDEX IF NOT EXISTS idx_parent ON experiments(parent_id)")


def new_id() -> str:
    return uuid.uuid4().hex[:12]


def save_experiment(experiment: dict) -> dict:
    """experiment is a full Experiment dict (metadata + spec + result)."""
    meta = experiment["metadata"]
    with _connect() as conn:
        conn.execute(
            """INSERT OR REPLACE INTO experiments (id, label, mode, parent_id, created_at, annotation, payload)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (
                meta["id"], meta["label"], meta["mode"], meta.get("parent_id"),
                meta["created_at"], meta.get("annotation"), json.dumps(experiment),
            ),
        )
    return experiment


def load_experiment(experiment_id: str) -> Optional[dict]:
    with _connect() as conn:
        row = conn.execute("SELECT payload FROM experiments WHERE id = ?", (experiment_id,)).fetchone()
    return json.loads(row["payload"]) if row else None


def list_experiments(limit: int = 100) -> list[dict]:
    with _connect() as conn:
        rows = conn.execute(
            """SELECT id, label, mode, parent_id, created_at, annotation
               FROM experiments ORDER BY created_at DESC LIMIT ?""",
            (limit,),
        ).fetchall()
    return [dict(r) for r in rows]


def delete_experiment(experiment_id: str) -> bool:
    with _connect() as conn:
        cur = conn.execute("DELETE FROM experiments WHERE id = ?", (experiment_id,))
        return cur.rowcount > 0


def update_annotation(experiment_id: str, annotation: str) -> Optional[dict]:
    exp = load_experiment(experiment_id)
    if exp is None:
        return None
    exp["metadata"]["annotation"] = annotation
    save_experiment(exp)
    return exp


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


init_db()

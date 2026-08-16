"""
notebook_store.py
------------------
Persistence for Notebooks -- ordered collections of experiment references
plus researcher-written text (conclusions, comparisons, notes). Same
SQLite approach as experiment_store.py: real, durable, survives restarts.
"""
from __future__ import annotations

import json
import sqlite3
import uuid
from pathlib import Path
from typing import Optional

from . import experiment_store as exp_store

DB_PATH = Path(__file__).resolve().parent / "experiments.sqlite3"  # same db file, new tables


def _connect() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    with _connect() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS notebooks (
                id TEXT PRIMARY KEY,
                title TEXT NOT NULL,
                description TEXT,
                author TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS notebook_entries (
                id TEXT PRIMARY KEY,
                notebook_id TEXT NOT NULL,
                position INTEGER NOT NULL,
                entry_type TEXT NOT NULL,
                experiment_ids TEXT NOT NULL,
                text TEXT,
                created_at TEXT NOT NULL,
                FOREIGN KEY (notebook_id) REFERENCES notebooks(id)
            )
        """)
        conn.execute("CREATE INDEX IF NOT EXISTS idx_entry_notebook ON notebook_entries(notebook_id)")


def new_id() -> str:
    return uuid.uuid4().hex[:12]


def create_notebook(title: str, description: Optional[str], author: Optional[str]) -> dict:
    nb_id = new_id()
    now = exp_store.now_iso()
    with _connect() as conn:
        conn.execute(
            "INSERT INTO notebooks (id, title, description, author, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?)",
            (nb_id, title, description, author, now, now),
        )
    return get_notebook_meta(nb_id)


def get_notebook_meta(notebook_id: str) -> Optional[dict]:
    with _connect() as conn:
        row = conn.execute("SELECT * FROM notebooks WHERE id = ?", (notebook_id,)).fetchone()
    return dict(row) if row else None


def list_notebooks() -> list[dict]:
    with _connect() as conn:
        rows = conn.execute("SELECT * FROM notebooks ORDER BY updated_at DESC").fetchall()
    return [dict(r) for r in rows]


def delete_notebook(notebook_id: str) -> bool:
    with _connect() as conn:
        conn.execute("DELETE FROM notebook_entries WHERE notebook_id = ?", (notebook_id,))
        cur = conn.execute("DELETE FROM notebooks WHERE id = ?", (notebook_id,))
        return cur.rowcount > 0


def add_entry(notebook_id: str, entry_type: str, experiment_ids: list[str], text: Optional[str]) -> Optional[dict]:
    if get_notebook_meta(notebook_id) is None:
        return None
    with _connect() as conn:
        pos_row = conn.execute(
            "SELECT COALESCE(MAX(position), -1) + 1 AS next_pos FROM notebook_entries WHERE notebook_id = ?",
            (notebook_id,),
        ).fetchone()
        entry_id = new_id()
        now = exp_store.now_iso()
        conn.execute(
            """INSERT INTO notebook_entries (id, notebook_id, position, entry_type, experiment_ids, text, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (entry_id, notebook_id, pos_row["next_pos"], entry_type, json.dumps(experiment_ids), text, now),
        )
        conn.execute("UPDATE notebooks SET updated_at = ? WHERE id = ?", (now, notebook_id))
    return get_entry(entry_id)


def get_entry(entry_id: str) -> Optional[dict]:
    with _connect() as conn:
        row = conn.execute("SELECT * FROM notebook_entries WHERE id = ?", (entry_id,)).fetchone()
    if row is None:
        return None
    d = dict(row)
    d["experiment_ids"] = json.loads(d["experiment_ids"])
    return d


def list_entries(notebook_id: str) -> list[dict]:
    with _connect() as conn:
        rows = conn.execute(
            "SELECT * FROM notebook_entries WHERE notebook_id = ? ORDER BY position ASC", (notebook_id,)
        ).fetchall()
    out = []
    for r in rows:
        d = dict(r)
        d["experiment_ids"] = json.loads(d["experiment_ids"])
        out.append(d)
    return out


def update_entry_text(entry_id: str, text: str) -> Optional[dict]:
    entry = get_entry(entry_id)
    if entry is None:
        return None
    with _connect() as conn:
        conn.execute("UPDATE notebook_entries SET text = ? WHERE id = ?", (text, entry_id))
        conn.execute("UPDATE notebooks SET updated_at = ? WHERE id = ?", (exp_store.now_iso(), entry["notebook_id"]))
    return get_entry(entry_id)


def delete_entry(entry_id: str) -> bool:
    entry = get_entry(entry_id)
    if entry is None:
        return False
    with _connect() as conn:
        conn.execute("DELETE FROM notebook_entries WHERE id = ?", (entry_id,))
    return True


init_db()

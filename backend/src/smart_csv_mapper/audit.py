"""Append-only audit log in SQLite: who exported what, with which mapping and model (ADR-008)."""

import json
import sqlite3
from datetime import UTC, datetime
from pathlib import Path

from pydantic import BaseModel

SCHEMA = """
CREATE TABLE IF NOT EXISTS audit_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    at TEXT NOT NULL,
    user TEXT NOT NULL,
    filename TEXT NOT NULL,
    file_sha256 TEXT NOT NULL,
    rows_total INTEGER NOT NULL,
    rows_exported INTEGER NOT NULL,
    rows_skipped INTEGER NOT NULL,
    mapping TEXT NOT NULL,
    model TEXT NOT NULL,
    ai_stats TEXT NOT NULL
);
CREATE TRIGGER IF NOT EXISTS audit_log_no_update BEFORE UPDATE ON audit_log
BEGIN SELECT RAISE(ABORT, 'audit_log is append-only'); END;
CREATE TRIGGER IF NOT EXISTS audit_log_no_delete BEFORE DELETE ON audit_log
BEGIN SELECT RAISE(ABORT, 'audit_log is append-only'); END;
"""


class AuditEntry(BaseModel):
    id: int | None = None
    at: str = ""
    user: str
    filename: str
    file_sha256: str
    rows_total: int
    rows_exported: int
    rows_skipped: int
    mapping: list[dict[str, object]]
    model: str
    ai_stats: list[dict[str, object]]


class AuditLog:
    def __init__(self, path: str | Path) -> None:
        self._path = str(path)
        with self._connect() as db:
            db.executescript(SCHEMA)

    def _connect(self) -> sqlite3.Connection:
        db = sqlite3.connect(self._path)
        db.row_factory = sqlite3.Row
        return db

    def append(self, entry: AuditEntry) -> AuditEntry:
        at = datetime.now(UTC).isoformat(timespec="seconds")
        with self._connect() as db:
            cursor = db.execute(
                "INSERT INTO audit_log (at, user, filename, file_sha256, rows_total, "
                "rows_exported, rows_skipped, mapping, model, ai_stats) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    at,
                    entry.user,
                    entry.filename,
                    entry.file_sha256,
                    entry.rows_total,
                    entry.rows_exported,
                    entry.rows_skipped,
                    json.dumps(entry.mapping),
                    entry.model,
                    json.dumps(entry.ai_stats),
                ),
            )
        return entry.model_copy(update={"id": cursor.lastrowid, "at": at})

    def recent(self, limit: int = 50) -> list[AuditEntry]:
        with self._connect() as db:
            rows = db.execute(
                "SELECT * FROM audit_log ORDER BY id DESC LIMIT ?", (limit,)
            ).fetchall()
        entries = []
        for row in rows:
            data = dict(row)
            data["mapping"] = json.loads(data["mapping"])
            data["ai_stats"] = json.loads(data["ai_stats"])
            entries.append(AuditEntry(**data))
        return entries

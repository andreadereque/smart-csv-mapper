import sqlite3
from pathlib import Path

import pytest

from smart_csv_mapper.audit import AuditEntry, AuditLog


def entry(filename: str = "a.csv") -> AuditEntry:
    return AuditEntry(
        user="demo",
        filename=filename,
        file_sha256="abc",
        rows_total=3,
        rows_exported=2,
        rows_skipped=1,
        mapping=[{"target": "email"}],
        model="m",
        ai_stats=[{"llm_calls": 1}],
    )


def test_append_returns_the_entry_with_id_and_time(tmp_path: Path) -> None:
    saved = AuditLog(tmp_path / "a.sqlite").append(entry())
    assert saved.id == 1
    assert saved.at.endswith("+00:00")


def test_recent_returns_newest_first_with_json_fields_decoded(tmp_path: Path) -> None:
    log = AuditLog(tmp_path / "a.sqlite")
    log.append(entry("first.csv"))
    log.append(entry("second.csv"))
    recent = log.recent()
    assert [e.filename for e in recent] == ["second.csv", "first.csv"]
    assert recent[0].mapping == [{"target": "email"}]
    assert recent[0].ai_stats == [{"llm_calls": 1}]
    assert len(log.recent(limit=1)) == 1


def test_the_log_is_append_only(tmp_path: Path) -> None:
    path = tmp_path / "a.sqlite"
    AuditLog(path).append(entry())
    db = sqlite3.connect(path)
    with pytest.raises(sqlite3.IntegrityError, match="append-only"):
        db.execute("UPDATE audit_log SET user = 'someone else'")
    with pytest.raises(sqlite3.IntegrityError, match="append-only"):
        db.execute("DELETE FROM audit_log")


def test_reopening_keeps_existing_entries(tmp_path: Path) -> None:
    AuditLog(tmp_path / "a.sqlite").append(entry())
    assert len(AuditLog(tmp_path / "a.sqlite").recent()) == 1

import sqlite3
from pathlib import Path

import pytest

from walle.audit_review import read_audit_entries, summarize_audit


def _make_db(tmp_path: Path, rows: list[tuple]) -> Path:
    db_path = tmp_path / "jarvis.db"
    conn = sqlite3.connect(str(db_path))
    conn.execute(
        """
        CREATE TABLE audit_entries (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT NOT NULL,
            agent TEXT NOT NULL,
            tier TEXT NOT NULL,
            allowed INTEGER NOT NULL,
            reason TEXT,
            detail TEXT
        )
        """
    )
    conn.executemany(
        "INSERT INTO audit_entries (timestamp, agent, tier, allowed, reason, detail) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        rows,
    )
    conn.commit()
    conn.close()
    return db_path


def test_read_audit_entries_missing_db(tmp_path):
    entries = read_audit_entries(db_path=tmp_path / "does-not-exist.db")
    assert entries == []


def test_read_audit_entries_and_types(tmp_path):
    db_path = _make_db(
        tmp_path,
        [
            ("2026-01-01T00:00:00Z", "friday", "personal-token", 1, "agent-declared default_sensitivity_tier floor", "{}"),
        ],
    )
    entries = read_audit_entries(db_path=db_path)
    assert len(entries) == 1
    assert entries[0]["allowed"] is True
    assert entries[0]["agent"] == "friday"


def test_summarize_audit_clean_case(tmp_path):
    db_path = _make_db(
        tmp_path,
        [
            ("t1", "friday", "personal-token", 1, "agent-declared default_sensitivity_tier floor (personal-token)", "{}"),
            ("t2", "ultron", "private", 1, "agent-declared default_sensitivity_tier floor (private)", "{}"),
            ("t3", "alfred", "work", 1, "explicit --tier override", "{}"),
        ],
    )
    entries = read_audit_entries(db_path=db_path)
    summary = summarize_audit(entries)
    assert summary["total_entries"] == 3
    assert summary["per_tier_counts"] == {"personal-token": 1, "private": 1, "work": 1}
    assert summary["private_tier_violations"] == []
    assert summary["fail_closed_count"] == 0


def test_summarize_audit_violation_case(tmp_path):
    # private tier, allowed, routed to friday (not ultron) -- should never
    # happen if Jarvis's own tier engine is working, but Wall-E must catch
    # it if it ever does.
    db_path = _make_db(
        tmp_path,
        [
            ("t1", "friday", "private", 1, "explicit --tier override", "{}"),
            ("t2", "ultron", "private", 1, "agent-declared default_sensitivity_tier floor (private)", "{}"),
        ],
    )
    entries = read_audit_entries(db_path=db_path)
    summary = summarize_audit(entries)
    assert len(summary["private_tier_violations"]) == 1
    assert summary["private_tier_violations"][0]["agent"] == "friday"


def test_summarize_audit_refused_private_not_flagged(tmp_path):
    # allowed=0 (refused) rows must NOT be flagged as violations -- the
    # conflict was correctly caught and dispatch refused.
    db_path = _make_db(
        tmp_path,
        [("t1", "friday", "private", 0, "refusing to dispatch: tier conflict", "{}")],
    )
    entries = read_audit_entries(db_path=db_path)
    summary = summarize_audit(entries)
    assert summary["private_tier_violations"] == []


def test_summarize_audit_fail_closed_detection(tmp_path):
    db_path = _make_db(
        tmp_path,
        [
            ("t1", "friday", "private", 1, "fail-closed default: no path override, no explicit override, no target agent known yet", "{}"),
            ("t2", "alfred", "work", 1, "explicit --tier override", "{}"),
        ],
    )
    entries = read_audit_entries(db_path=db_path)
    summary = summarize_audit(entries)
    assert summary["fail_closed_count"] == 1
    assert summary["fail_closed_entries"][0]["agent"] == "friday"

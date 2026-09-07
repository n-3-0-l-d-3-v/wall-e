"""Privacy audit review: reads Jarvis's dispatch audit log and produces a
summary + flags violations.

Judgment call: **read Jarvis's sqlite audit log directly with stdlib
`sqlite3`**, rather than importing `jarvis.store.AuditLog`. Why: it avoids
making `jarvis` a hard runtime dependency of Wall-E (same reasoning as
health_aggregation.py), and the schema is small, stable, and documented
right here in one place -- `jarvis/store.py::AuditLog._init_schema()`:

    CREATE TABLE audit_entries (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        timestamp TEXT NOT NULL,
        agent TEXT NOT NULL,
        tier TEXT NOT NULL,
        allowed INTEGER NOT NULL,
        reason TEXT,
        detail TEXT
    )

Default DB location matches `jarvis.store.default_db_path()`:
`~/.jarvis/jarvis.db`, overridable with the same `JARVIS_DB_PATH` env var
Jarvis itself honors, so pointing Wall-E at a non-default Jarvis DB needs no
new configuration.

Two things this module flags, per the task spec and
10x/docs/omniroute-privacy-spec.md:

1. **private-tier dispatch routed to a non-Ultron agent.** Per the privacy
   spec, `private` is the strictest tier (local-only, zero network calls);
   per Jarvis's own tier engine (`jarvis/tiers.py::check_conflict`), a
   dispatch is only ever *allowed* to reach an agent whose declared
   `default_sensitivity_tier` floor is at least as protective as the
   request's tier -- and only Ultron declares `private` as its floor
   (Friday and Alfred are `personal-token`). So an `allowed=1` row with
   `tier='private'` and `agent != 'ultron'` should be *impossible* if
   Jarvis's own conflict check is working; if Wall-E ever finds one, it's
   either a real privacy violation or a regression in Jarvis's tier
   enforcement, and either way it's worth surfacing loudly rather than
   silently trusting the upstream check.
2. **fail-closed / ambiguous tier classification.** `jarvis/tiers.py`
   writes a specific reason string, `"fail-closed default: ..."`, when no
   path override, no explicit override, and no target agent floor were
   available to compute a confident tier (see `compute_tier`'s last
   branch). Wall-E matches on that substring rather than re-deriving the
   condition, since the reason string is the one place Jarvis records
   *why* a tier was assigned, and matching it keeps this check honest
   about only flagging what Jarvis itself labeled as a fallback (not
   guessing from tier value alone, since `private` is also a valid
   deliberate default, e.g. Jarvis's and Ultron's own agent-declared
   default).
"""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Optional

PRIVATE_TIER = "private"
TRUSTED_PRIVATE_AGENT = "ultron"
FAIL_CLOSED_MARKER = "fail-closed"


def default_jarvis_db_path() -> Path:
    import os

    override = os.environ.get("JARVIS_DB_PATH")
    if override:
        return Path(override)
    return Path.home() / ".jarvis" / "jarvis.db"


def read_audit_entries(db_path: Optional[Path] = None, limit: int = 1000) -> list[dict]:
    """Read up to `limit` most recent audit_entries rows. Returns `[]`
    (never raises) if the DB file doesn't exist or the table isn't there
    yet -- both are normal states (Jarvis not run yet on this machine, or
    a fresh JARVIS_DB_PATH), not errors."""
    path = db_path or default_jarvis_db_path()
    if not path.exists():
        return []

    try:
        conn = sqlite3.connect(str(path))
        conn.row_factory = sqlite3.Row
        try:
            cur = conn.execute(
                "SELECT id, timestamp, agent, tier, allowed, reason, detail "
                "FROM audit_entries ORDER BY id DESC LIMIT ?",
                (limit,),
            )
            rows = [dict(row) for row in cur.fetchall()]
        finally:
            conn.close()
    except sqlite3.Error:
        return []

    for row in rows:
        row["allowed"] = bool(row["allowed"])
        if row.get("detail"):
            try:
                row["detail"] = json.loads(row["detail"])
            except (json.JSONDecodeError, TypeError, ValueError):
                pass
    return rows


def summarize_audit(entries: list[dict]) -> dict:
    """Counts per tier, and the two flagged categories described above."""
    per_tier: dict[str, int] = {}
    violations: list[dict] = []
    fail_closed: list[dict] = []

    for row in entries:
        tier = row.get("tier", "unknown")
        per_tier[tier] = per_tier.get(tier, 0) + 1

        if (
            row.get("allowed")
            and tier == PRIVATE_TIER
            and row.get("agent") != TRUSTED_PRIVATE_AGENT
        ):
            violations.append(row)

        reason = (row.get("reason") or "").lower()
        if FAIL_CLOSED_MARKER in reason:
            fail_closed.append(row)

    return {
        "total_entries": len(entries),
        "per_tier_counts": per_tier,
        "private_tier_violations": violations,
        "fail_closed_count": len(fail_closed),
        "fail_closed_entries": fail_closed,
    }

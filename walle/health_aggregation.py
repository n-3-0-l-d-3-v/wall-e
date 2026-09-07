"""Agent health aggregation.

Judgment call: **shell out to `jarvis health`** rather than importing
Jarvis's `jarvis.health` module directly as a library dependency.

Why: Jarvis already implements exactly this polling job -- it loads
`jarvis/agents.yaml`, runs each sibling agent's declared
`health_check_command` as a subprocess with a timeout, and aggregates
healthy/unhealthy plus Jarvis's own self-health -- see
`jarvis/health.py::check_all_agents_health` and `jarvis_self_health`, both
wired into the `jarvis health` subcommand (`jarvis/cli.py`). Re-implementing
that polling logic here (parsing `agents.yaml`, running each of the four
health_check_commands, handling the FileNotFoundError/TimeoutExpired cases)
would duplicate real, tested code for no benefit.

Importing `jarvis.health` as a library was the alternative. Rejected
because: (1) it would make `jarvis` a hard runtime dependency of Wall-E
(pyproject.toml would need `jarvis @ file://...` or similar, awkward for a
sibling repo that isn't published to an index), (2) Jarvis's own README
documents `jarvis health` as *the* supported aggregate-health surface for
exactly this "future Wall-E agent" use case, so shelling out to the CLI is
the intended integration point, not a workaround, and (3) it keeps Wall-E
resilient to Jarvis being present-but-not-pip-installed (e.g. checked out
but `pip install -e .` never run) the same way `jarvis health` itself
degrades gracefully (per-agent errors) rather than crashing when a sibling
isn't installed.

The `jarvis health` subcommand's `--json` flag defaults to True already
(see jarvis/cli.py), so plain `jarvis health` on stdout is already the JSON
payload: `{"jarvis": {...self-health...}, "agents": {"friday": {...}, ...}}`.
"""

from __future__ import annotations

import json
import shutil
import subprocess
from typing import Optional

DEFAULT_COMMAND = ["jarvis", "health"]
DEFAULT_TIMEOUT = 30.0


def run_jarvis_health(
    command: Optional[list[str]] = None, timeout: float = DEFAULT_TIMEOUT
) -> dict:
    """Run `jarvis health` (or an override command) and return its parsed
    JSON payload, plus a `wall_e_meta` block describing how the call went.
    Never raises -- a failure to run Jarvis at all is reported as an
    unreachable-orchestrator result, not an exception, so it can't crash
    `wall-e report`.
    """
    cmd = command or DEFAULT_COMMAND

    if shutil.which(cmd[0]) is None:
        return {
            "reachable": False,
            "error": f"command not found on PATH: {cmd[0]!r}. Is Jarvis "
            f"installed (`pip install -e .` in the jarvis repo)?",
            "jarvis": None,
            "agents": {},
        }

    try:
        proc = subprocess.run(
            cmd, capture_output=True, text=True, timeout=timeout
        )
    except subprocess.TimeoutExpired:
        return {
            "reachable": False,
            "error": f"`{' '.join(cmd)}` timed out after {timeout}s",
            "jarvis": None,
            "agents": {},
        }
    except OSError as exc:
        return {
            "reachable": False,
            "error": f"failed to launch `{' '.join(cmd)}`: {exc}",
            "jarvis": None,
            "agents": {},
        }

    try:
        payload = json.loads(proc.stdout)
    except (json.JSONDecodeError, ValueError):
        return {
            "reachable": False,
            "error": f"`{' '.join(cmd)}` did not print valid JSON "
            f"(exit {proc.returncode}); stderr: {proc.stderr.strip()[:500]}",
            "jarvis": None,
            "agents": {},
        }

    jarvis_self = payload.get("jarvis") or {}
    agents = payload.get("agents") or {}

    return {
        "reachable": True,
        "error": None,
        "exit_code": proc.returncode,
        "jarvis": jarvis_self,
        "agents": agents,
    }


def summarize_health(health_payload: dict) -> dict:
    """Reduce the raw `run_jarvis_health` payload to counts + a flat list of
    unhealthy entries, for the weekly report."""
    if not health_payload.get("reachable"):
        return {
            "reachable": False,
            "error": health_payload.get("error"),
            "healthy_count": 0,
            "unhealthy_count": 0,
            "total_count": 0,
            "unhealthy": [],
        }

    agents = health_payload.get("agents", {}) or {}
    jarvis_self = health_payload.get("jarvis") or {}

    entries = dict(agents)
    entries["jarvis"] = jarvis_self

    unhealthy = []
    healthy_count = 0
    for name, status in entries.items():
        is_healthy = bool(status.get("healthy"))
        if is_healthy:
            healthy_count += 1
        else:
            unhealthy.append(
                {
                    "agent": name,
                    "error": status.get("error") or "reported unhealthy",
                }
            )

    return {
        "reachable": True,
        "error": None,
        "healthy_count": healthy_count,
        "unhealthy_count": len(unhealthy),
        "total_count": len(entries),
        "unhealthy": unhealthy,
    }

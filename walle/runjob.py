"""Windowless runner for the weekly scheduled jobs.

Task Scheduler launches `pythonw -m walle.runjob <job> <exe> [args...]`.
pythonw has no console, and the job runs with CREATE_NO_WINDOW, so no
window ever appears (its own subprocesses share that hidden console).
A visible console at catch-up time got closed by hand: `friday github`
died with 0xC000013A on 2026-10-18/25 and 11-01.

Output goes to ~/.walle/jobs/<job>.log with a header and an
`exit=<code>` footer per run, so failures are debuggable after the fact
and `wall-e report` can flag failed or stale jobs (see last_run()).
The runner exits with the job's own exit code, so Task Scheduler's
Last Result stays meaningful.
"""
from __future__ import annotations

import datetime
import os
import re
import subprocess
import sys
from pathlib import Path
from typing import Optional

LOG_DIR = Path.home() / ".walle" / "jobs"
MAX_LOG_BYTES = 256_000
_FOOTER = re.compile(r"^=== end (\S+) exit=(-?\d+) ===$", re.MULTILINE)


def log_path(job: str, log_dir: Optional[Path] = None) -> Path:
    return (log_dir or LOG_DIR) / f"{job}.log"


def run(job: str, cmd: list[str], log_dir: Optional[Path] = None) -> int:
    log = log_path(job, log_dir)
    log.parent.mkdir(parents=True, exist_ok=True)
    if log.exists() and log.stat().st_size > MAX_LOG_BYTES:
        log.replace(log.with_suffix(".log.1"))
    flags = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
    with log.open("a", encoding="utf-8", errors="replace") as f:
        f.write(f"=== start {datetime.datetime.now().isoformat(timespec='seconds')} {' '.join(cmd)} ===\n")
        f.flush()
        try:
            code = subprocess.run(cmd, stdout=f, stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL,
                                  creationflags=flags).returncode
        except OSError as exc:
            f.write(f"could not start: {exc}\n")
            code = 127
        f.write(f"=== end {datetime.datetime.now().isoformat(timespec='seconds')} exit={code} ===\n")
    return code


def last_run(job: str, log_dir: Optional[Path] = None) -> Optional[dict]:
    """{"when": datetime, "exit": int} for the job's most recent finished run, or None."""
    log = log_path(job, log_dir)
    if not log.is_file():
        return None
    ends = _FOOTER.findall(log.read_text(encoding="utf-8", errors="replace"))
    if not ends:
        return None
    when, code = ends[-1]
    try:
        return {"when": datetime.datetime.fromisoformat(when), "exit": int(code)}
    except ValueError:
        return None


def main(argv: Optional[list[str]] = None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    if len(argv) < 2:
        return 2
    return run(argv[0], argv[1:])


if __name__ == "__main__":
    sys.exit(main())

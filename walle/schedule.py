"""Weekly `wall-e report` scheduling via the OS scheduler.

Windows: Task Scheduler (schtasks). Elsewhere: prints the cron line to
install (Phase 1's Linux target will use a systemd timer instead).
"""
from __future__ import annotations

import os
import shutil
import subprocess

TASK_NAME = "WallE-WeeklyReport"


def _command() -> str:
    exe = shutil.which("wall-e") or "wall-e"
    return f'"{exe}" report'


def build_create_args(day: str = "SUN", time: str = "09:00") -> list[str]:
    return ["schtasks", "/Create", "/F", "/TN", TASK_NAME, "/SC", "WEEKLY", "/D", day, "/ST", time, "/TR", _command()]


def cron_line(day: int = 0, hour: int = 9) -> str:
    return f"0 {hour} * * {day} {_command()}"


def install(day: str = "SUN", time: str = "09:00") -> str:
    if os.name != "nt":
        return f"Add to crontab: {cron_line()}"
    r = subprocess.run(build_create_args(day, time), capture_output=True, text=True)
    if r.returncode != 0:
        raise RuntimeError((r.stderr or r.stdout).strip())
    return f"Scheduled '{TASK_NAME}' weekly {day} {time}"


def remove() -> str:
    if os.name != "nt":
        return "Remove the wall-e line from your crontab."
    r = subprocess.run(["schtasks", "/Delete", "/F", "/TN", TASK_NAME], capture_output=True, text=True)
    return "Removed." if r.returncode == 0 else f"Not scheduled ({(r.stderr or r.stdout).strip()})"


def status() -> str:
    if os.name != "nt":
        return "cron-managed; see `crontab -l`"
    r = subprocess.run(["schtasks", "/Query", "/TN", TASK_NAME], capture_output=True, text=True)
    return "scheduled" if r.returncode == 0 else "not scheduled"

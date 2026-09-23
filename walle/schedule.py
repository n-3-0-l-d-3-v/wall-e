"""Weekly ecosystem jobs via the OS scheduler.

Jobs (each its own scheduled task, so one failing never blocks another):
  report  -> `wall-e report`   (health/privacy report into the vault)
  github  -> `friday github`   (GitHub stats snapshot into the vault)

Windows: Task Scheduler (schtasks). Elsewhere: prints the cron line to
install (Phase 1's Linux target will use a systemd timer instead).
"""
from __future__ import annotations

import os
import shutil
import subprocess
from dataclasses import dataclass


@dataclass(frozen=True)
class Job:
    task: str
    exe: str
    args: str
    day: str
    time: str


JOBS = {
    "report": Job("WallE-WeeklyReport", "wall-e", "report", "SUN", "09:00"),
    "github": Job("Friday-WeeklyGitHub", "friday", "github", "SUN", "09:15"),
}
TASK_NAME = JOBS["report"].task  # back-compat
_CRON_DAYS = {"SUN": 0, "MON": 1, "TUE": 2, "WED": 3, "THU": 4, "FRI": 5, "SAT": 6}


def _job(name: str) -> Job:
    if name not in JOBS:
        raise RuntimeError(f"unknown job {name!r}; choose from {sorted(JOBS)}")
    return JOBS[name]


def _command(job: Job) -> str:
    exe = shutil.which(job.exe) or job.exe
    return f'"{exe}" {job.args}'


def build_create_args(day: str | None = None, time: str | None = None, job: str = "report") -> list[str]:
    j = _job(job)
    return ["schtasks", "/Create", "/F", "/TN", j.task, "/SC", "WEEKLY",
            "/D", day or j.day, "/ST", time or j.time, "/TR", _command(j)]


def cron_line(job: str = "report") -> str:
    j = _job(job)
    hour, minute = (int(x) for x in j.time.split(":"))
    return f"{minute} {hour} * * {_CRON_DAYS[j.day]} {_command(j)}"


def install(day: str | None = None, time: str | None = None, job: str = "report") -> str:
    j = _job(job)
    if os.name != "nt":
        return f"Add to crontab: {cron_line(job)}"
    r = subprocess.run(build_create_args(day, time, job), capture_output=True, text=True)
    if r.returncode != 0:
        raise RuntimeError((r.stderr or r.stdout).strip())
    return f"Scheduled '{j.task}' weekly {day or j.day} {time or j.time}"


def remove(job: str = "report") -> str:
    j = _job(job)
    if os.name != "nt":
        return f"Remove the `{j.exe} {j.args}` line from your crontab."
    r = subprocess.run(["schtasks", "/Delete", "/F", "/TN", j.task], capture_output=True, text=True)
    return f"Removed '{j.task}'." if r.returncode == 0 else f"'{j.task}' not scheduled ({(r.stderr or r.stdout).strip()})"


def is_scheduled(job: str = "report") -> bool | None:
    """True/False on Windows; None where scheduling is cron-managed (unknown)."""
    if os.name != "nt":
        return None
    r = subprocess.run(["schtasks", "/Query", "/TN", _job(job).task], capture_output=True, text=True)
    return r.returncode == 0


def status(job: str = "report") -> str:
    state = is_scheduled(job)
    if state is None:
        return "cron-managed; see `crontab -l`"
    return "scheduled" if state else "not scheduled"

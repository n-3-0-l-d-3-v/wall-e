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
from pathlib import Path


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


_DAY_NAMES = {"SUN": "Sunday", "MON": "Monday", "TUE": "Tuesday", "WED": "Wednesday",
              "THU": "Thursday", "FRI": "Friday", "SAT": "Saturday"}


def task_xml(day: str | None = None, time: str | None = None, job: str = "report") -> str:
    """Task Scheduler definition. Unlike plain `schtasks /Create`, this lets a
    laptop job run on battery and catch up after a missed slot (machine off or
    asleep at 09:00) -- the defaults made both weekly jobs fail with
    0x800710E0 on 2026-09-28."""
    import datetime
    from xml.sax.saxutils import escape

    j = _job(job)
    day, time = (day or j.day).upper(), time or j.time
    if day not in _DAY_NAMES:
        raise RuntimeError(f"unknown day {day!r}; use one of {sorted(_DAY_NAMES)}")
    anchor = datetime.date(2026, 1, 4) + datetime.timedelta(days=_CRON_DAYS[day])  # 2026-01-04 is a Sunday
    exe = shutil.which(j.exe) or j.exe
    return f"""<?xml version="1.0" encoding="UTF-16"?>
<Task version="1.2" xmlns="http://schemas.microsoft.com/windows/2004/02/mit/task">
  <RegistrationInfo><Description>10x ecosystem weekly job: {escape(j.exe)} {escape(j.args)}</Description></RegistrationInfo>
  <Triggers>
    <CalendarTrigger>
      <StartBoundary>{anchor.isoformat()}T{time}:00</StartBoundary>
      <Enabled>true</Enabled>
      <ScheduleByWeek><DaysOfWeek><{_DAY_NAMES[day]} /></DaysOfWeek><WeeksInterval>1</WeeksInterval></ScheduleByWeek>
    </CalendarTrigger>
  </Triggers>
  <Principals><Principal id="Author"><LogonType>InteractiveToken</LogonType><RunLevel>LeastPrivilege</RunLevel></Principal></Principals>
  <Settings>
    <MultipleInstancesPolicy>IgnoreNew</MultipleInstancesPolicy>
    <DisallowStartIfOnBatteries>false</DisallowStartIfOnBatteries>
    <StopIfGoingOnBatteries>false</StopIfGoingOnBatteries>
    <StartWhenAvailable>true</StartWhenAvailable>
    <ExecutionTimeLimit>PT30M</ExecutionTimeLimit>
    <Enabled>true</Enabled>
  </Settings>
  <Actions Context="Author"><Exec><Command>{escape(exe)}</Command><Arguments>{escape(j.args)}</Arguments></Exec></Actions>
</Task>
"""


def build_create_args(xml_path: str, job: str = "report") -> list[str]:
    return ["schtasks", "/Create", "/F", "/TN", _job(job).task, "/XML", xml_path]


def cron_line(job: str = "report") -> str:
    j = _job(job)
    hour, minute = (int(x) for x in j.time.split(":"))
    return f"{minute} {hour} * * {_CRON_DAYS[j.day]} {_command(j)}"


def install(day: str | None = None, time: str | None = None, job: str = "report") -> str:
    j = _job(job)
    if os.name != "nt":
        return f"Add to crontab: {cron_line(job)}"
    import tempfile

    xml = task_xml(day, time, job)
    fd, path = tempfile.mkstemp(suffix=".xml")
    os.close(fd)
    try:
        Path(path).write_text(xml, encoding="utf-16")
        r = subprocess.run(build_create_args(path, job), capture_output=True, text=True)
    finally:
        Path(path).unlink(missing_ok=True)
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

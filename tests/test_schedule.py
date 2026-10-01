from walle import schedule


def test_task_xml_is_weekly_runs_report_and_survives_laptop_life():
    import xml.etree.ElementTree as ET
    xml = schedule.task_xml("MON", "08:30")
    root = ET.fromstring(xml.split("?>", 1)[1])
    ns = {"t": "http://schemas.microsoft.com/windows/2004/02/mit/task"}
    trig = root.find("t:Triggers/t:CalendarTrigger", ns)
    assert trig.find("t:StartBoundary", ns).text == "2026-01-05T08:30:00"  # a Monday
    assert trig.find("t:ScheduleByWeek/t:DaysOfWeek/t:Monday", ns) is not None
    st = root.find("t:Settings", ns)
    assert st.find("t:DisallowStartIfOnBatteries", ns).text == "false"
    assert st.find("t:StopIfGoingOnBatteries", ns).text == "false"
    assert st.find("t:StartWhenAvailable", ns).text == "true"
    assert root.find("t:Actions/t:Exec/t:Arguments", ns).text == "report"


def test_create_args_use_the_xml_definition():
    assert schedule.build_create_args("C:/t.xml") == ["schtasks", "/Create", "/F", "/TN", "WallE-WeeklyReport", "/XML", "C:/t.xml"]


def test_install_writes_utf16_xml_and_cleans_up(monkeypatch):
    monkeypatch.setattr(schedule.os, "name", "nt")
    seen = {}

    class R: returncode = 0; stderr = ""; stdout = "ok"

    def fake_run(args, **k):
        from pathlib import Path
        seen["text"] = Path(args[-1]).read_text(encoding="utf-16")
        seen["path"] = Path(args[-1])
        return R()
    monkeypatch.setattr(schedule.subprocess, "run", fake_run)
    assert "Scheduled 'Friday-WeeklyGitHub'" in schedule.install(job="github")
    assert "<Arguments>github</Arguments>" in seen["text"] and not seen["path"].exists()


def test_cron_line_shape():
    assert schedule.cron_line().startswith("0 9 * * 0 ")


def test_install_raises_on_failure(monkeypatch):
    monkeypatch.setattr(schedule.os, "name", "nt")
    class R: returncode = 1; stderr = "denied"; stdout = ""
    monkeypatch.setattr(schedule.subprocess, "run", lambda *a, **k: R())
    import pytest
    with pytest.raises(RuntimeError):
        schedule.install()


def test_github_job_runs_friday_github_at_its_own_task_name():
    assert "Friday-WeeklyGitHub" in schedule.build_create_args("x.xml", job="github")
    xml = schedule.task_xml(job="github")
    assert "<Arguments>github</Arguments>" in xml and "2026-01-04T09:15:00" in xml
    assert schedule.cron_line("github").startswith("15 9 * * 0 ")


def test_unknown_job_raises():
    import pytest
    with pytest.raises(RuntimeError):
        schedule.task_xml(job="nope")
    with pytest.raises(RuntimeError):
        schedule.task_xml("FUNDAY")


def test_cli_all_jobs_reports_each_and_fails_if_any_fails(monkeypatch):
    from click.testing import CliRunner
    from walle.cli import cli

    def fake(job="report"):
        if job == "github":
            raise RuntimeError("denied")
        return "scheduled"
    monkeypatch.setattr(schedule, "status", fake)
    r = CliRunner().invoke(cli, ["schedule", "status"])
    assert "report: scheduled" in r.output and "github: Error: denied" in r.output and r.exit_code == 1

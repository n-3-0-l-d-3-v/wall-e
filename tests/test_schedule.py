from walle import schedule


def test_create_args_are_weekly_and_run_report():
    a = schedule.build_create_args("MON", "08:30")
    assert a[:2] == ["schtasks", "/Create"] and "WEEKLY" in a and "MON" in a and "08:30" in a
    assert a[-1].endswith("report")


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
    a = schedule.build_create_args(job="github")
    assert "Friday-WeeklyGitHub" in a and a[-1].endswith("github") and "09:15" in a
    assert schedule.cron_line("github").startswith("15 9 * * 0 ")


def test_unknown_job_raises():
    import pytest
    with pytest.raises(RuntimeError):
        schedule.build_create_args(job="nope")


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

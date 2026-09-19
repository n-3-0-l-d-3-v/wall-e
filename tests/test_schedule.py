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

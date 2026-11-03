import datetime
import sys

from walle import runjob, setup_check


def test_run_logs_output_and_returns_the_jobs_exit_code(tmp_path):
    code = runjob.run("demo", [sys.executable, "-c", "print('hello'); raise SystemExit(3)"], log_dir=tmp_path)
    assert code == 3
    text = (tmp_path / "demo.log").read_text(encoding="utf-8")
    assert "=== start" in text and "hello" in text and "exit=3 ===" in text
    last = runjob.last_run("demo", tmp_path)
    assert last["exit"] == 3 and isinstance(last["when"], datetime.datetime)


def test_last_run_reads_the_latest_footer_and_handles_missing(tmp_path):
    assert runjob.last_run("nope", tmp_path) is None
    runjob.run("demo", [sys.executable, "-c", "raise SystemExit(1)"], log_dir=tmp_path)
    runjob.run("demo", [sys.executable, "-c", "pass"], log_dir=tmp_path)
    assert runjob.last_run("demo", tmp_path)["exit"] == 0


def test_unstartable_command_is_logged_as_127(tmp_path):
    assert runjob.run("bad", [str(tmp_path / "missing.exe")], log_dir=tmp_path) == 127
    assert "could not start" in (tmp_path / "bad.log").read_text(encoding="utf-8")


def test_log_rotates_when_large(tmp_path, monkeypatch):
    monkeypatch.setattr(runjob, "MAX_LOG_BYTES", 10)
    (tmp_path / "demo.log").write_text("x" * 100, encoding="utf-8")
    runjob.run("demo", [sys.executable, "-c", "pass"], log_dir=tmp_path)
    assert (tmp_path / "demo.log.1").exists() and "x" * 100 not in (tmp_path / "demo.log").read_text(encoding="utf-8")


def test_main_requires_job_and_command():
    assert runjob.main(["only-a-name"]) == 2


def test_job_runs_flag_failed_and_stale_but_not_never_run(tmp_path):
    runjob.run("report", [sys.executable, "-c", "raise SystemExit(1)"], log_dir=tmp_path)
    runjob.run("github", [sys.executable, "-c", "pass"], log_dir=tmp_path)
    runs = setup_check.check_job_runs(tmp_path)
    assert runs["report"]["exit"] == 1 and runs["github"]["exit"] == 0 and not runs["github"]["stale"]
    later = setup_check.check_job_runs(tmp_path, now=datetime.datetime.now() + datetime.timedelta(days=9))
    assert later["github"]["stale"] is True
    reasons = setup_check.reasons({"job_runs": later})
    assert any("'report' last run failed (exit 1" in r for r in reasons)
    assert any("'github' has not run since" in r for r in reasons)
    assert setup_check.reasons({"job_runs": {"report": None}}) == []

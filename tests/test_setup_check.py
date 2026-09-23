import subprocess

from walle import setup_check as sc


class R:
    def __init__(self, rc=0, out="", err=""):
        self.returncode, self.stdout, self.stderr = rc, out, err


OLLAMA_LIST = "NAME            ID      SIZE    MODIFIED\nqwen2.5:3b      abc     1.9 GB  2 weeks ago\nllama3:latest   def     4 GB    1 day ago\n"


def test_models_reports_missing_and_accepts_latest_suffix(monkeypatch):
    got = sc.check_models(run=lambda *a, **k: R(out=OLLAMA_LIST), exe="ollama")
    assert got["missing"] == ["qwen2.5:7b"] and got["error"] is None
    monkeypatch.setenv("WALLE_REQUIRED_MODELS", "llama3, qwen2.5:3b")
    assert sc.check_models(run=lambda *a, **k: R(out=OLLAMA_LIST), exe="ollama")["missing"] == []


def test_models_unknown_when_ollama_fails_or_times_out():
    assert sc.check_models(run=lambda *a, **k: R(1, err="server not running"), exe="o")["missing"] is None

    def boom(*a, **k):
        raise subprocess.TimeoutExpired("ollama", 20)
    assert sc.check_models(run=boom, exe="o")["missing"] is None


def test_sandbox_image_present_missing_unknown():
    assert sc.check_sandbox_image(run=lambda *a, **k: R(out="sha256:x"), exe="docker")["present"] is True
    assert sc.check_sandbox_image(run=lambda *a, **k: R(1, err="Error: No such image: ultron-sandbox"), exe="docker")["present"] is False
    daemon_down = sc.check_sandbox_image(run=lambda *a, **k: R(1, err="Cannot connect to the Docker daemon"), exe="docker")
    assert daemon_down["present"] is None and "daemon" in daemon_down["error"]


def test_guard_hooks(tmp_path):
    for name, content in (("a", "#!/bin/sh\n# tars-guard pre-commit hook\n"), ("b", "#!/bin/sh\necho hi\n"), ("c", None)):
        hooks = tmp_path / name / ".git" / "hooks"
        hooks.mkdir(parents=True)
        if content:
            (hooks / "pre-commit").write_text(content)
    (tmp_path / "notrepo").mkdir()
    got = sc.check_guard_hooks({n: tmp_path / n for n in ("a", "b", "c", "notrepo", "absent")})
    assert got == {"a": True, "b": False, "c": False}


def test_reasons_only_for_definite_failures():
    setup = {
        "models": {"required": ["m1", "m2"], "missing": ["m2"], "error": None},
        "sandbox_image": {"image": "ultron-sandbox", "present": False, "error": None},
        "schedules": {"github": False, "report": None},
        "guard_hooks": {"x": True, "y": False},
    }
    r = sc.reasons(setup)
    assert len(r) == 4 and any("m2" in x for x in r) and any("github" in x for x in r)
    assert not any("'report'" in x for x in r)  # unknown is not a failure
    unknown = {"models": {"required": ["m"], "missing": None, "error": "x"},
               "sandbox_image": {"image": "i", "present": None, "error": "x"},
               "schedules": {"report": None}, "guard_hooks": {}}
    assert sc.reasons(unknown) == [] and sc.reasons(None) == []
    text = "\n".join(sc.render(setup))
    assert "1/2 present; missing m2" in text and "github NO" in text and "missing in y" in text


def test_report_degrades_on_setup_drift():
    from walle.report import _overall_status, status_reasons
    healthy = {"reachable": True, "unhealthy_count": 0}
    setup = {"models": {"missing": ["m"]}, "sandbox_image": {}, "schedules": {}, "guard_hooks": {}}
    assert _overall_status(healthy, {}, {}, {}, setup) == "degraded"
    assert _overall_status(healthy, {}, {}, {}) == "ok"
    assert any("m" in r for r in status_reasons(healthy, {}, {}, {}, setup))

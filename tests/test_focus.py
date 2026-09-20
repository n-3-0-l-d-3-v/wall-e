from walle import focus


class _R:
    def __init__(self, out="", rc=0): self.stdout, self.stderr, self.returncode = out, "", rc


def test_on_off_restores_previous_plan(tmp_path, monkeypatch):
    monkeypatch.setattr(focus, "STATE", tmp_path / "focus.json")
    calls = []
    def fake_run(cmd, **k):
        calls.append(cmd)
        if cmd[1] == "/getactivescheme":
            return _R("Power Scheme GUID: 381b4222-f694-41f0-9685-ff5bb260df2e  (Balanced)")
        return _R()
    monkeypatch.setattr(focus.subprocess, "run", fake_run)
    monkeypatch.setattr(focus, "unload_models", lambda *a, **k: ["qwen2.5:7b"])
    assert "qwen2.5:7b" in focus.focus_on()
    assert ["powercfg", "/setactive", focus.POWER_SAVER] in calls
    focus.focus_off()
    assert ["powercfg", "/setactive", "381b4222-f694-41f0-9685-ff5bb260df2e"] in calls
    assert not (tmp_path / "focus.json").exists()


def test_off_with_no_state(tmp_path, monkeypatch):
    monkeypatch.setattr(focus, "STATE", tmp_path / "none.json")
    assert "nothing to restore" in focus.focus_off()

"""Focus/battery mode: unload local models and switch the Windows power plan.

`on` remembers the previous power plan in a state file so `off` restores it.
Nothing is killed; only reversible settings change.
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import urllib.request
from pathlib import Path

STATE = Path(os.environ.get("WALLE_STATE_DIR", Path.home() / ".wall-e")) / "focus.json"
POWER_SAVER = "a1841308-3541-4fab-bc81-f71556f20b4a"
_GUID = re.compile(r"[0-9a-fA-F]{8}(?:-[0-9a-fA-F]{4}){3}-[0-9a-fA-F]{12}")


def current_plan() -> str:
    out = subprocess.run(["powercfg", "/getactivescheme"], capture_output=True, text=True).stdout
    m = _GUID.search(out)
    if not m:
        raise RuntimeError("could not read the active power plan")
    return m.group(0)


def set_plan(guid: str) -> None:
    r = subprocess.run(["powercfg", "/setactive", guid], capture_output=True, text=True)
    if r.returncode != 0:
        raise RuntimeError((r.stderr or r.stdout).strip())


def unload_models(host: str = "http://127.0.0.1:11434") -> list[str]:
    """Ask Ollama to evict every loaded model from RAM/VRAM (keep_alive=0)."""
    try:
        with urllib.request.urlopen(f"{host}/api/ps", timeout=3) as r:
            loaded = [m["name"] for m in json.loads(r.read()).get("models", [])]
        for name in loaded:
            req = urllib.request.Request(f"{host}/api/generate", data=json.dumps({"model": name, "keep_alive": 0}).encode(),
                                         headers={"Content-Type": "application/json"})
            urllib.request.urlopen(req, timeout=10).read()
        return loaded
    except OSError:
        return []


def focus_on() -> str:
    prev = current_plan()
    STATE.parent.mkdir(parents=True, exist_ok=True)
    if prev != POWER_SAVER:
        STATE.write_text(json.dumps({"previous_plan": prev}), encoding="utf-8")
    set_plan(POWER_SAVER)
    unloaded = unload_models()
    return f"focus ON: power saver set, unloaded models: {unloaded or 'none'}"


def focus_off() -> str:
    if not STATE.exists():
        return "focus OFF: nothing to restore"
    prev = json.loads(STATE.read_text(encoding="utf-8"))["previous_plan"]
    set_plan(prev)
    STATE.unlink()
    return f"focus OFF: restored power plan {prev}"

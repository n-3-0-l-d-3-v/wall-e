"""Setup drift check: is the machine still set up the way the ecosystem needs?

* the local Ollama models the agents rely on are pulled (`ollama list`),
* Ultron's no-network sandbox image exists (`docker image inspect`),
* Wall-E's weekly jobs are registered with the OS scheduler,
* each sibling repo still has TARS's secret-blocking pre-commit hook.

Only local subprocesses and file reads -- no sockets, so it runs fine
under guard.network_guard(). "Can't tell" (tool missing, daemon down) is
reported as unknown (None), never as a failure or a pass.
"""
from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path
from typing import Callable, Optional

REQUIRED_MODELS = ("qwen2.5:3b", "qwen2.5:7b")
SANDBOX_IMAGE = "ultron-sandbox"
GUARD_MARKER = "# tars-guard"
TIMEOUT = 20


def _exe(name: str, fallback: Optional[Path] = None) -> Optional[str]:
    found = shutil.which(name)
    if found:
        return found
    return str(fallback) if fallback and fallback.exists() else None


def required_models() -> list[str]:
    raw = os.environ.get("WALLE_REQUIRED_MODELS", "")
    return [m.strip() for m in raw.split(",") if m.strip()] or list(REQUIRED_MODELS)


def check_models(run: Callable = subprocess.run, exe: Optional[str] = None) -> dict:
    exe = exe or _exe("ollama", Path.home() / "AppData" / "Local" / "Programs" / "Ollama" / "ollama.exe")
    wanted = required_models()
    if not exe:
        return {"required": wanted, "missing": None, "error": "ollama not installed"}
    try:
        r = run([exe, "list"], capture_output=True, text=True, timeout=TIMEOUT)
    except (OSError, subprocess.TimeoutExpired) as exc:
        return {"required": wanted, "missing": None, "error": str(exc)}
    if r.returncode != 0:
        return {"required": wanted, "missing": None, "error": (r.stderr or r.stdout).strip()[:200]}
    have = {line.split()[0] for line in r.stdout.splitlines()[1:] if line.strip()}
    have |= {h.removesuffix(":latest") for h in have}
    return {"required": wanted, "missing": [m for m in wanted if m not in have], "error": None}


def check_sandbox_image(run: Callable = subprocess.run, exe: Optional[str] = None) -> dict:
    exe = exe or _exe("docker")
    if not exe:
        return {"image": SANDBOX_IMAGE, "present": None, "error": "docker not installed"}
    try:
        r = run([exe, "image", "inspect", SANDBOX_IMAGE, "--format", "{{.Id}}"],
                capture_output=True, text=True, timeout=TIMEOUT)
    except (OSError, subprocess.TimeoutExpired) as exc:
        return {"image": SANDBOX_IMAGE, "present": None, "error": str(exc)}
    if r.returncode == 0:
        return {"image": SANDBOX_IMAGE, "present": True, "error": None}
    err = (r.stderr or r.stdout).strip()
    if "no such image" in err.lower():
        return {"image": SANDBOX_IMAGE, "present": False, "error": None}
    return {"image": SANDBOX_IMAGE, "present": None, "error": "docker daemon unavailable" if "daemon" in err.lower() or not err else err.splitlines()[0][:120]}


def check_schedules() -> dict:
    from walle import schedule

    out = {}
    for job in sorted(schedule.JOBS):
        try:
            out[job] = schedule.is_scheduled(job)
        except (OSError, subprocess.SubprocessError):
            out[job] = None
    return out


def check_guard_hooks(repos: dict[str, Path]) -> dict:
    out = {}
    for name, path in repos.items():
        hook = Path(path) / ".git" / "hooks" / "pre-commit"
        if not (Path(path) / ".git").is_dir():
            continue
        try:
            out[name] = hook.is_file() and GUARD_MARKER in hook.read_text(encoding="utf-8", errors="replace")
        except OSError:
            out[name] = False
    return out


def check_setup(repos: dict[str, Path]) -> dict:
    return {
        "models": check_models(),
        "sandbox_image": check_sandbox_image(),
        "schedules": check_schedules(),
        "guard_hooks": check_guard_hooks(repos),
    }


def reasons(setup: Optional[dict]) -> list[str]:
    if not setup:
        return []
    out: list[str] = []
    missing = (setup.get("models") or {}).get("missing")
    if missing:
        out.append("missing Ollama model(s): " + ", ".join(missing) + " (ollama pull <model>)")
    if (setup.get("sandbox_image") or {}).get("present") is False:
        out.append(f"Ultron sandbox image '{SANDBOX_IMAGE}' missing (ultron sandbox build)")
    for job, ok in (setup.get("schedules") or {}).items():
        if ok is False:
            out.append(f"weekly job '{job}' not scheduled (wall-e schedule install --job {job})")
    unguarded = [r for r, ok in (setup.get("guard_hooks") or {}).items() if ok is False]
    if unguarded:
        out.append("no tars-guard pre-commit hook in: " + ", ".join(sorted(unguarded)) + " (tars guard install --path <repo>)")
    return out


def render(setup: dict) -> list[str]:
    def mark(v):
        return "yes" if v is True else "NO" if v is False else "unknown"

    m, img = setup["models"], setup["sandbox_image"]
    lines = ["## 5. Setup Drift", ""]
    if m["missing"] is None:
        lines.append(f"- Ollama models: unknown ({m['error']})")
    else:
        lines.append(f"- Ollama models: {len(m['required']) - len(m['missing'])}/{len(m['required'])} present"
                     + (f"; missing {', '.join(m['missing'])}" if m["missing"] else ""))
    lines.append(f"- Sandbox image `{img['image']}`: {mark(img['present'])}" + (f" ({img['error']})" if img["error"] else ""))
    lines.append("- Scheduled jobs: " + ", ".join(f"{j} {mark(v)}" for j, v in setup["schedules"].items()))
    hooks = setup["guard_hooks"]
    lines.append(f"- tars-guard hooks: {sum(1 for v in hooks.values() if v)}/{len(hooks)} repos"
                 + (f"; missing in {', '.join(sorted(r for r, v in hooks.items() if not v))}" if not all(hooks.values()) else ""))
    lines.append("")
    return lines

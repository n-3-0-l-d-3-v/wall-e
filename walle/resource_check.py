"""Disk/basic resource check: disk space on each sibling repo's drive,
Python/pip version sanity, and git working-tree cleanliness for each
sibling repo. OS-agnostic by construction (stdlib `shutil.disk_usage` and
`git status --porcelain` both work the same on Windows/Linux/Mac) -- see
README.md "Explicitly out of scope for v1" for what this deliberately does
NOT do (no power/thermal management, no Linux-specific tooling).
"""

from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path
from typing import Optional


def disk_usage_for(path: Path) -> dict:
    """Disk usage for the drive containing `path`. Returns an error dict
    (never raises) if the path doesn't exist."""
    if not path.exists():
        return {"path": str(path), "error": "path does not exist"}
    try:
        usage = shutil.disk_usage(str(path))
    except OSError as exc:
        return {"path": str(path), "error": str(exc)}
    return {
        "path": str(path),
        "total_bytes": usage.total,
        "used_bytes": usage.used,
        "free_bytes": usage.free,
        "free_percent": round(usage.free / usage.total * 100, 1) if usage.total else None,
    }


def python_pip_versions() -> dict:
    """Sanity info about the interpreter/pip currently running Wall-E.
    Not a claim about any sibling agent's own venv -- each agent may run
    under its own interpreter (e.g. Alfred's apps/api/.venv)."""
    info = {
        "python_version": sys.version.split()[0],
        "python_executable": sys.executable,
        "pip_version": None,
        "pip_error": None,
    }
    try:
        proc = subprocess.run(
            [sys.executable, "-m", "pip", "--version"],
            capture_output=True,
            text=True,
            timeout=15,
        )
        if proc.returncode == 0:
            info["pip_version"] = proc.stdout.strip()
        else:
            info["pip_error"] = proc.stderr.strip() or f"exit code {proc.returncode}"
    except (OSError, subprocess.TimeoutExpired) as exc:
        info["pip_error"] = str(exc)
    return info


def git_status_for(repo_path: Path, timeout: float = 15.0) -> dict:
    """`git status --porcelain` against `repo_path`. Returns
    {"path", "is_git_repo", "clean", "dirty_files", "error"}."""
    result: dict = {
        "path": str(repo_path),
        "is_git_repo": (repo_path / ".git").exists(),
        "clean": None,
        "dirty_files": [],
        "error": None,
    }
    if not repo_path.exists():
        result["error"] = "path does not exist"
        return result
    if not result["is_git_repo"]:
        result["error"] = "not a git repository (no .git directory)"
        return result

    try:
        proc = subprocess.run(
            ["git", "status", "--porcelain"],
            cwd=str(repo_path),
            capture_output=True,
            text=True,
            timeout=timeout,
        )
    except FileNotFoundError:
        result["error"] = "git executable not found on PATH"
        return result
    except subprocess.TimeoutExpired:
        result["error"] = f"git status timed out after {timeout}s"
        return result

    if proc.returncode != 0:
        result["error"] = proc.stderr.strip() or f"git exited {proc.returncode}"
        return result

    lines = [line for line in proc.stdout.splitlines() if line.strip()]
    result["dirty_files"] = lines
    result["clean"] = len(lines) == 0
    return result


def check_sibling_repos(repo_paths: dict[str, Path]) -> dict:
    """Run disk usage + git status for each sibling repo path. Disk usage
    is de-duplicated by drive/anchor so repos sharing a drive aren't
    reported N times."""
    git_results = {key: git_status_for(path) for key, path in repo_paths.items()}

    disk_by_anchor: dict[str, dict] = {}
    disk_results: dict[str, dict] = {}
    for key, path in repo_paths.items():
        anchor = str(Path(path).resolve().anchor) if path.exists() else str(path)
        if anchor not in disk_by_anchor:
            disk_by_anchor[anchor] = disk_usage_for(path)
        disk_results[key] = disk_by_anchor[anchor]

    return {
        "git_status": git_results,
        "disk_usage": disk_results,
        "python_pip": python_pip_versions(),
    }


def default_sibling_repo_paths(ecosystem_root: Optional[Path] = None) -> dict[str, Path]:
    root = ecosystem_root or Path(__file__).resolve().parents[2]
    return {
        "friday": root / "friday",
        "ultron": root / "ultron",
        "alfred": root / "alfred",
        "jarvis": root / "jarvis",
        "tars": root / "tars",
        "vision": root / "vision",
    }

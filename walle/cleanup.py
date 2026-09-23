"""Disk cleanup SUGGESTIONS (`wall-e cleanup`). Measures, ranks, and prints the
exact command to reclaim space -- it never deletes anything itself. Deleting
is always the user's call.

Only regenerable things are suggested for removal (package caches, build
caches, bytecode); personal folders (Downloads) are listed as "review" with
their largest files, never as safe to delete.
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Optional

GB = 1024 ** 3


@dataclass
class Suggestion:
    name: str
    bytes: int
    kind: str  # "safe" (regenerable) | "review" (personal data, user decides)
    command: str
    detail: str = ""
    top_files: list[tuple[str, int]] = field(default_factory=list)


def dir_size(path: Path, limit_files: int = 400_000) -> int:
    total = 0
    count = 0
    for root, _dirs, files in os.walk(path, onerror=lambda e: None):
        for f in files:
            try:
                total += os.lstat(os.path.join(root, f)).st_size
            except OSError:
                pass
            count += 1
            if count >= limit_files:
                return total
    return total


def largest_files(path: Path, n: int = 5) -> list[tuple[str, int]]:
    found = []
    for root, _dirs, files in os.walk(path, onerror=lambda e: None):
        for f in files:
            p = os.path.join(root, f)
            try:
                found.append((p, os.lstat(p).st_size))
            except OSError:
                pass
    return sorted(found, key=lambda x: -x[1])[:n]


def _home() -> Path:
    return Path(os.environ.get("WALLE_HOME_OVERRIDE") or Path.home())


def cache_candidates(home: Path) -> list[tuple[str, Path, str, str]]:
    local = home / "AppData" / "Local"
    return [
        ("pip cache", local / "pip" / "Cache", "safe", "pip cache purge"),
        ("npm cache", local / "npm-cache", "safe", "npm cache clean --force"),
        ("HuggingFace cache", home / ".cache" / "huggingface", "safe", "delete unused models under ~/.cache/huggingface/hub"),
        ("Windows temp", local / "Temp", "safe", "Disk Cleanup > Temporary files (files in use are skipped)"),
        ("Downloads", home / "Downloads", "review", "review the largest files below and delete what you no longer need"),
    ]


def docker_reclaimable(run: Callable = subprocess.run) -> Optional[Suggestion]:
    if not shutil.which("docker"):
        return None
    try:
        r = run(["docker", "system", "df", "--format", "{{json .}}"], capture_output=True, text=True, timeout=20)
    except Exception:  # noqa: BLE001
        return None
    if r.returncode != 0:
        return None
    total = 0
    for line in r.stdout.splitlines():
        try:
            rec = json.loads(line)
        except ValueError:
            continue
        total += parse_size(str(rec.get("Reclaimable", "0")).split(" ")[0])
    if total <= 0:
        return None
    return Suggestion("Docker (unused images/cache)", total, "safe", "docker system prune (add -a to drop unused images)")


def parse_size(s: str) -> int:
    s = s.strip().upper()
    for unit, mult in (("TB", 1024 ** 4), ("GB", GB), ("MB", 1024 ** 2), ("KB", 1024), ("B", 1)):
        if s.endswith(unit):
            try:
                return int(float(s[: -len(unit)]) * mult)
            except ValueError:
                return 0
    return 0


def pycache_in(repos: list[Path]) -> Suggestion:
    total = 0
    for repo in repos:
        for p in repo.rglob("__pycache__"):
            total += dir_size(p)
    return Suggestion("Python bytecode in agent repos", total, "safe", "find . -name __pycache__ -exec rm -rf {} +  (in each repo)")


def suggestions(repos: Optional[list[Path]] = None, run: Callable = subprocess.run) -> list[Suggestion]:
    home = _home()
    out: list[Suggestion] = []
    for name, path, kind, cmd in cache_candidates(home):
        if path.is_dir():
            size = dir_size(path)
            if size > 0:
                s = Suggestion(name, size, kind, cmd, detail=str(path))
                if kind == "review":
                    s.top_files = largest_files(path)
                out.append(s)
    d = docker_reclaimable(run)
    if d:
        out.append(d)
    if repos:
        p = pycache_in(repos)
        if p.bytes:
            out.append(p)
    return sorted(out, key=lambda s: -s.bytes)


def render(items: list[Suggestion]) -> str:
    if not items:
        return "Nothing notable to reclaim."
    safe = sum(s.bytes for s in items if s.kind == "safe")
    lines = [f"Reclaimable without losing anything personal: {safe / GB:.1f} GB", ""]
    for s in items:
        tag = "SAFE  " if s.kind == "safe" else "REVIEW"
        lines.append(f"[{tag}] {s.name}: {s.bytes / GB:.2f} GB  ->  {s.command}")
        for path, size in s.top_files:
            lines.append(f"           {size / GB:6.2f} GB  {path}")
    lines.append("")
    lines.append("Wall-E only suggests; nothing was deleted.")
    return "\n".join(lines)

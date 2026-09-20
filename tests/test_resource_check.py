import subprocess
from pathlib import Path
from unittest import mock

import pytest

from walle.resource_check import (
    check_sibling_repos,
    default_sibling_repo_paths,
    disk_usage_for,
    git_status_for,
    python_pip_versions,
)


def test_disk_usage_for_missing_path(tmp_path):
    result = disk_usage_for(tmp_path / "nope")
    assert "error" in result


def test_disk_usage_for_real_path(tmp_path):
    result = disk_usage_for(tmp_path)
    assert result["total_bytes"] > 0
    assert 0 <= result["free_percent"] <= 100


def test_git_status_for_non_repo(tmp_path):
    result = git_status_for(tmp_path)
    assert result["is_git_repo"] is False
    assert "not a git repository" in result["error"]


def test_git_status_for_missing_path(tmp_path):
    result = git_status_for(tmp_path / "nope")
    assert result["error"] == "path does not exist"


def test_git_status_for_clean_repo(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    subprocess.run(["git", "init", "-q"], cwd=str(repo), check=True)
    subprocess.run(["git", "config", "user.email", "a@b.c"], cwd=str(repo), check=True)
    subprocess.run(["git", "config", "user.name", "test"], cwd=str(repo), check=True)
    (repo / "f.txt").write_text("hi", encoding="utf-8")
    subprocess.run(["git", "add", "."], cwd=str(repo), check=True)
    subprocess.run(["git", "commit", "-q", "-m", "init"], cwd=str(repo), check=True)

    result = git_status_for(repo)
    assert result["is_git_repo"] is True
    assert result["clean"] is True
    assert result["dirty_files"] == []


def test_git_status_for_dirty_repo(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    subprocess.run(["git", "init", "-q"], cwd=str(repo), check=True)
    subprocess.run(["git", "config", "user.email", "a@b.c"], cwd=str(repo), check=True)
    subprocess.run(["git", "config", "user.name", "test"], cwd=str(repo), check=True)
    (repo / "f.txt").write_text("hi", encoding="utf-8")

    result = git_status_for(repo)
    assert result["is_git_repo"] is True
    assert result["clean"] is False
    assert len(result["dirty_files"]) == 1


def test_python_pip_versions():
    info = python_pip_versions()
    assert info["python_version"]
    assert info["pip_version"] or info["pip_error"]


def test_check_sibling_repos_dedupes_disk_by_drive(tmp_path):
    a = tmp_path / "a"
    b = tmp_path / "b"
    a.mkdir()
    b.mkdir()
    result = check_sibling_repos({"a": a, "b": b})
    # Same drive/anchor -> disk usage results are the same object content.
    assert result["disk_usage"]["a"]["total_bytes"] == result["disk_usage"]["b"]["total_bytes"]
    assert "python_pip" in result


def test_default_sibling_repo_paths_layout():
    paths = default_sibling_repo_paths(Path("C:/fake/root"))
    assert paths["friday"] == Path("C:/fake/root/friday")
    assert paths["jarvis"] == Path("C:/fake/root/jarvis")


def test_real_sibling_repos_check():
    """Run for real against the four actual sibling repos on this machine
    and report actual disk/git-status findings."""
    paths = default_sibling_repo_paths()
    if not all(p.exists() for p in paths.values()):
        pytest.skip("sibling agent repos not found next to wall-e/ on this machine")

    result = check_sibling_repos(paths)
    assert set(result["git_status"]) == {"friday", "ultron", "alfred", "jarvis", "tars", "vision"}
    for repo, status in result["git_status"].items():
        assert status["is_git_repo"] is True, f"{repo}: {status}"
    for repo, status in result["disk_usage"].items():
        assert "error" not in status, f"{repo}: {status}"

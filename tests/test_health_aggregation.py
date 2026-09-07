import json
import subprocess
from unittest import mock

from walle.health_aggregation import run_jarvis_health, summarize_health


def _fake_completed(stdout: str, returncode: int = 0) -> subprocess.CompletedProcess:
    return subprocess.CompletedProcess(args=["jarvis", "health"], returncode=returncode, stdout=stdout, stderr="")


def test_run_jarvis_health_command_not_found():
    with mock.patch("walle.health_aggregation.shutil.which", return_value=None):
        result = run_jarvis_health()
    assert result["reachable"] is False
    assert "not found" in result["error"]


def test_run_jarvis_health_parses_json():
    payload = {
        "jarvis": {"healthy": True},
        "agents": {
            "friday": {"healthy": True},
            "ultron": {"healthy": False, "error": "not installed"},
            "alfred": {"healthy": True},
        },
    }
    with mock.patch("walle.health_aggregation.shutil.which", return_value="/usr/bin/jarvis"), \
         mock.patch("walle.health_aggregation.subprocess.run", return_value=_fake_completed(json.dumps(payload))):
        result = run_jarvis_health()

    assert result["reachable"] is True
    assert result["agents"]["ultron"]["healthy"] is False


def test_run_jarvis_health_bad_json():
    with mock.patch("walle.health_aggregation.shutil.which", return_value="/usr/bin/jarvis"), \
         mock.patch("walle.health_aggregation.subprocess.run", return_value=_fake_completed("not json", returncode=1)):
        result = run_jarvis_health()
    assert result["reachable"] is False
    assert "valid JSON" in result["error"]


def test_run_jarvis_health_timeout():
    with mock.patch("walle.health_aggregation.shutil.which", return_value="/usr/bin/jarvis"), \
         mock.patch("walle.health_aggregation.subprocess.run", side_effect=subprocess.TimeoutExpired(cmd="jarvis", timeout=30)):
        result = run_jarvis_health()
    assert result["reachable"] is False
    assert "timed out" in result["error"]


def test_summarize_health_unreachable():
    summary = summarize_health({"reachable": False, "error": "boom"})
    assert summary["reachable"] is False
    assert summary["healthy_count"] == 0
    assert summary["unhealthy"] == []


def test_summarize_health_mixed():
    payload = {
        "reachable": True,
        "jarvis": {"healthy": True},
        "agents": {
            "friday": {"healthy": True},
            "ultron": {"healthy": False, "error": "console script missing"},
            "alfred": {"healthy": False, "error": "pydantic_settings missing"},
        },
    }
    summary = summarize_health(payload)
    assert summary["reachable"] is True
    assert summary["total_count"] == 4
    assert summary["healthy_count"] == 2
    assert summary["unhealthy_count"] == 2
    agents_flagged = {e["agent"] for e in summary["unhealthy"]}
    assert agents_flagged == {"ultron", "alfred"}


def test_summarize_health_all_healthy():
    payload = {
        "reachable": True,
        "jarvis": {"healthy": True},
        "agents": {"friday": {"healthy": True}, "ultron": {"healthy": True}, "alfred": {"healthy": True}},
    }
    summary = summarize_health(payload)
    assert summary["unhealthy_count"] == 0
    assert summary["healthy_count"] == 4

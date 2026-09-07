"""Real integration test against Jarvis's actual `jarvis health` command
(not mocked) -- confirms Wall-E's health_aggregation module genuinely talks
to Jarvis's CLI, the same way jarvis's own test suite proved its MCP client
talks to Friday's real MCP server. Skips cleanly (not a failure) if the
`jarvis` console script isn't on PATH in this environment, so the rest of
the suite doesn't depend on Jarvis being installed.
"""

import shutil

import pytest

from walle.health_aggregation import run_jarvis_health, summarize_health


@pytest.mark.skipif(shutil.which("jarvis") is None, reason="jarvis console script not on PATH")
def test_real_jarvis_health_call():
    result = run_jarvis_health()
    assert result["reachable"] is True, result.get("error")
    assert "jarvis" in result
    assert isinstance(result["agents"], dict)

    summary = summarize_health(result)
    assert summary["reachable"] is True
    assert summary["total_count"] >= 1

from pathlib import Path

from walle.contract_check import (
    check_agent_yaml,
    check_agent_yamls,
    default_agent_yaml_paths,
)

VALID_YAML = """\
name: TestAgent
role: testing
default_sensitivity_tier: work
entrypoint: test-agent
health_check_command: test-agent --health
sandboxed: false
"""

MISSING_FIELD_YAML = """\
name: TestAgent
role: testing
default_sensitivity_tier: work
entrypoint: test-agent
sandboxed: false
"""

BAD_TIER_YAML = """\
name: TestAgent
role: testing
default_sensitivity_tier: super-secret
entrypoint: test-agent
health_check_command: test-agent --health
sandboxed: false
"""


def test_valid_agent_yaml(tmp_path):
    p = tmp_path / "agent.yaml"
    p.write_text(VALID_YAML, encoding="utf-8")
    result = check_agent_yaml(p)
    assert result["ok"] is True
    assert result["missing_fields"] == []
    assert result["invalid_tier"] is None


def test_missing_field_agent_yaml(tmp_path):
    p = tmp_path / "agent.yaml"
    p.write_text(MISSING_FIELD_YAML, encoding="utf-8")
    result = check_agent_yaml(p)
    assert result["ok"] is False
    assert "health_check_command" in result["missing_fields"]


def test_bad_tier_agent_yaml(tmp_path):
    p = tmp_path / "agent.yaml"
    p.write_text(BAD_TIER_YAML, encoding="utf-8")
    result = check_agent_yaml(p)
    assert result["ok"] is False
    assert result["invalid_tier"] == "super-secret"


def test_missing_file(tmp_path):
    result = check_agent_yaml(tmp_path / "does-not-exist.yaml")
    assert result["ok"] is False
    assert result["error"] == "file not found"


def test_invalid_yaml(tmp_path):
    p = tmp_path / "agent.yaml"
    p.write_text("name: [unclosed", encoding="utf-8")
    result = check_agent_yaml(p)
    assert result["ok"] is False
    assert "invalid YAML" in result["error"]


def test_check_agent_yamls_summary(tmp_path):
    good = tmp_path / "good.yaml"
    good.write_text(VALID_YAML, encoding="utf-8")
    bad = tmp_path / "bad.yaml"
    bad.write_text(MISSING_FIELD_YAML, encoding="utf-8")

    summary = check_agent_yamls({"good_agent": good, "bad_agent": bad})
    assert summary["checked_count"] == 2
    assert summary["compliant_count"] == 1
    assert set(summary["non_compliant"]) == {"bad_agent"}


def test_real_ecosystem_agent_yamls_are_compliant():
    """Run for real against the four actual sibling agent.yaml files on
    this machine. They were built to this same contract, so they should
    all pass -- if one doesn't, that's a real finding, not something to
    silently work around here."""
    paths = default_agent_yaml_paths()
    # Skip (rather than fail the whole suite) if the sibling repos aren't
    # checked out next to wall-e on whatever machine runs this.
    if not all(p.exists() for p in paths.values()):
        import pytest

        pytest.skip("sibling agent repos not found next to wall-e/ on this machine")

    summary = check_agent_yamls(paths)
    assert summary["checked_count"] == 4
    assert summary["non_compliant"] == {}, summary["non_compliant"]

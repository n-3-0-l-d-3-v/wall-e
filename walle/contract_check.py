"""Agent-contract compliance: verify each sibling's agent.yaml declares the
required fields with valid values, per the pattern established by
Friday/Ultron/Alfred/Jarvis's actual agent.yaml files.

Required fields (from reading all four existing agent.yaml files, plus
Wall-E's own): `name`, `role`, `default_sensitivity_tier`, `entrypoint`,
`health_check_command`, `sandboxed`. Note `vault_write_path` is present on
Friday/Ultron/Alfred/Wall-E but Jarvis omits it (Jarvis doesn't write vault
notes) -- so it is intentionally NOT in the required set here; only the six
fields common to all five agent.yaml files (including Wall-E's own) are
enforced.
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional

import yaml

REQUIRED_FIELDS = (
    "name",
    "role",
    "default_sensitivity_tier",
    "entrypoint",
    "health_check_command",
    "sandboxed",
)

VALID_TIERS = {"private", "personal-token", "work", "public"}


def check_agent_yaml(path: Path) -> dict:
    """Check a single agent.yaml file. Returns a result dict with `ok`,
    `path`, `missing_fields`, `invalid_tier`, and `error` (parse/read
    failure). Never raises."""
    result: dict = {
        "path": str(path),
        "ok": False,
        "missing_fields": [],
        "invalid_tier": None,
        "error": None,
        "name": None,
    }

    if not path.exists():
        result["error"] = "file not found"
        return result

    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        result["error"] = f"could not read file: {exc}"
        return result

    try:
        data = yaml.safe_load(text)
    except yaml.YAMLError as exc:
        result["error"] = f"invalid YAML: {exc}"
        return result

    if not isinstance(data, dict):
        result["error"] = "agent.yaml did not parse to a mapping"
        return result

    result["name"] = data.get("name")

    missing = [f for f in REQUIRED_FIELDS if f not in data or data[f] is None]
    result["missing_fields"] = missing

    tier = data.get("default_sensitivity_tier")
    if tier is not None and tier not in VALID_TIERS:
        result["invalid_tier"] = tier

    result["ok"] = not missing and result["invalid_tier"] is None
    return result


def check_agent_yamls(paths: dict[str, Path]) -> dict:
    """Check a mapping of {agent_key: agent.yaml path} and return a summary
    plus per-agent detail."""
    per_agent = {key: check_agent_yaml(path) for key, path in paths.items()}
    non_compliant = {k: v for k, v in per_agent.items() if not v["ok"]}
    return {
        "checked_count": len(per_agent),
        "compliant_count": len(per_agent) - len(non_compliant),
        "non_compliant": non_compliant,
        "agents": per_agent,
    }


def default_agent_yaml_paths(ecosystem_root: Optional[Path] = None) -> dict[str, Path]:
    """The four sibling agents' agent.yaml paths, assuming Wall-E's repo
    lives alongside them (this machine's actual layout, per the task
    description: friday/, ultron/, alfred/, jarvis/, wall-e/ all under the
    same parent directory). Override `ecosystem_root` for a different
    layout or in tests."""
    root = ecosystem_root or Path(__file__).resolve().parents[2]
    return {
        "friday": root / "friday" / "agent.yaml",
        "ultron": root / "ultron" / "agent.yaml",
        "alfred": root / "alfred" / "agent.yaml",
        "jarvis": root / "jarvis" / "agent.yaml",
    }

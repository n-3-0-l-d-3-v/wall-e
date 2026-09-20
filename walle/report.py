"""Assembles points 1-5 (health aggregation, audit review, contract
compliance, disk/resource check) into one structured report: a JSON dict
for `wall-e report --json`, and Markdown-with-frontmatter for the file
written to vault/Wall-E/, matching the frontmatter + section pattern
Ultron/Alfred use for their own vault notes.
"""

from __future__ import annotations

import datetime
from pathlib import Path
from typing import Optional

from walle import __version__
from walle.audit_review import read_audit_entries, summarize_audit
from walle.contract_check import check_agent_yamls, default_agent_yaml_paths
from walle.health_aggregation import run_jarvis_health, summarize_health
from walle.resource_check import check_sibling_repos, default_sibling_repo_paths


def build_report(
    ecosystem_root: Optional[Path] = None,
    jarvis_command: Optional[list[str]] = None,
    audit_db_path: Optional[Path] = None,
) -> dict:
    """Run all four checks and assemble the structured report dict. This is
    the single source of truth both `--json` output and the Markdown
    report are rendered from, so the two representations never drift."""
    now = datetime.datetime.now(datetime.timezone.utc)

    health_raw = run_jarvis_health(command=jarvis_command)
    health_summary = summarize_health(health_raw)

    audit_entries = read_audit_entries(db_path=audit_db_path)
    audit_summary = summarize_audit(audit_entries)

    agent_yaml_paths = default_agent_yaml_paths(ecosystem_root)
    contract_summary = check_agent_yamls(agent_yaml_paths)

    repo_paths = default_sibling_repo_paths(ecosystem_root)
    resource_summary = check_sibling_repos(repo_paths)

    overall_status = _overall_status(health_summary, audit_summary, contract_summary, resource_summary)

    return {
        "wall_e_version": __version__,
        "generated_at": now.isoformat(),
        "overall_status": overall_status,
        "status_reasons": status_reasons(health_summary, audit_summary, contract_summary, resource_summary),
        "agent_health": health_summary,
        "agent_health_raw": health_raw,
        "privacy_audit": audit_summary,
        "contract_compliance": contract_summary,
        "resources": resource_summary,
    }


LOW_DISK_PERCENT = 10.0
LOW_DISK_GB = 20.0


def status_reasons(health: dict, audit: dict, contract: dict, resources: dict) -> list[str]:
    """Human-readable reasons the report is not `ok` (empty list = ok)."""
    reasons: list[str] = []
    if audit.get("private_tier_violations"):
        reasons.append("PRIVACY: private-tier request routed to a non-local agent")
    if not health.get("reachable"):
        reasons.append("agent health could not be collected")
    elif health.get("unhealthy_count", 0) > 0:
        reasons.append(f"{health['unhealthy_count']} unhealthy agent(s)")
    if contract.get("non_compliant"):
        reasons.append("agent.yaml contract violations: " + ", ".join(map(str, contract["non_compliant"])))
    for repo, status in resources.get("git_status", {}).items():
        if status.get("error") or status.get("clean") is False:
            reasons.append(f"{repo}: uncommitted changes or git error")
    seen = set()
    for repo, status in resources.get("disk_usage", {}).items():
        pct, free = status.get("free_percent"), status.get("free_bytes")
        key = (pct, free)
        if key in seen:
            continue
        seen.add(key)
        low_pct = pct is not None and pct < LOW_DISK_PERCENT
        low_abs = free is not None and free / 1024**3 < LOW_DISK_GB
        if low_pct or low_abs:
            reasons.append(f"low disk space: {pct}% free ({(free or 0) / 1024**3:.0f} GB)")
    return reasons


def _overall_status(health: dict, audit: dict, contract: dict, resources: dict) -> str:
    """`critical` for a real privacy violation, `degraded` if anything in
    status_reasons() applies, else `ok`."""
    if audit.get("private_tier_violations"):
        return "critical"
    return "degraded" if status_reasons(health, audit, contract, resources) else "ok"


def render_markdown(report: dict) -> str:
    """Render the report dict as Markdown with YAML frontmatter, matching
    Ultron/Alfred's vault-note pattern: `date` and `status` (this task's
    "overall status") in frontmatter, then one section per check."""
    generated_at = report["generated_at"]
    status = report["overall_status"]

    lines: list[str] = []
    lines.append("---")
    lines.append(f"date: {generated_at}")
    lines.append(f"status: {status}")
    lines.append("agent: Wall-E")
    lines.append(f"wall_e_version: {report['wall_e_version']}")
    lines.append("---")
    lines.append("")
    lines.append(f"# Wall-E Weekly Report — {generated_at}")
    lines.append("")
    lines.append(f"**Overall status: {status.upper()}**")
    for reason in report.get("status_reasons", []):
        lines.append(f"- Reason: {reason}")
    lines.append("")

    lines.extend(_render_health_section(report["agent_health"]))
    lines.extend(_render_audit_section(report["privacy_audit"]))
    lines.extend(_render_contract_section(report["contract_compliance"]))
    lines.extend(_render_resource_section(report["resources"]))

    lines.append("## 5. Deferred for v1")
    lines.append("")
    lines.append(
        "Power/thermal management, systemd/cron scheduling, and any GUI "
        "health display are explicitly out of scope for Wall-E v1 -- see "
        "README.md. `wall-e report` is a manually-invoked one-shot command, "
        "not a background daemon."
    )
    lines.append("")

    return "\n".join(lines)


def _render_health_section(health: dict) -> list[str]:
    lines = ["## 1. Agent Health", ""]
    if not health.get("reachable"):
        lines.append(f"- **Could not reach Jarvis:** {health.get('error')}")
        lines.append("")
        return lines

    lines.append(
        f"- {health['healthy_count']}/{health['total_count']} healthy "
        f"(Jarvis + Friday + Ultron + Alfred)"
    )
    if health["unhealthy"]:
        lines.append("- Unhealthy:")
        for entry in health["unhealthy"]:
            lines.append(f"  - **{entry['agent']}**: {entry['error']}")
    lines.append("")
    return lines


def _render_audit_section(audit: dict) -> list[str]:
    lines = ["## 2. Privacy Audit Review", ""]
    lines.append(f"- Total dispatch decisions reviewed: {audit['total_entries']}")
    if audit["per_tier_counts"]:
        lines.append("- Dispatches per tier:")
        for tier, count in sorted(audit["per_tier_counts"].items()):
            lines.append(f"  - {tier}: {count}")
    else:
        lines.append("- No audit entries found (Jarvis DB empty or not yet created).")

    violations = audit["private_tier_violations"]
    if violations:
        lines.append("")
        lines.append(
            f"- **VIOLATION: {len(violations)} `private`-tier dispatch(es) "
            f"routed to a non-Ultron agent.** This should be impossible per "
            f"Jarvis's tier-conflict check -- investigate immediately:"
        )
        for row in violations:
            lines.append(
                f"  - id={row.get('id')} agent={row.get('agent')} "
                f"timestamp={row.get('timestamp')} reason={row.get('reason')!r}"
            )
    else:
        lines.append("- No private-tier-to-wrong-agent violations found.")

    fail_closed = audit["fail_closed_count"]
    lines.append(
        f"- Fail-closed (ambiguous tier classification) dispatches: {fail_closed}"
    )
    lines.append("")
    return lines


def _render_contract_section(contract: dict) -> list[str]:
    lines = ["## 3. Agent-Contract Compliance", ""]
    lines.append(
        f"- {contract['compliant_count']}/{contract['checked_count']} "
        f"agent.yaml files compliant"
    )
    if contract["non_compliant"]:
        lines.append("- Non-compliant:")
        for key, result in contract["non_compliant"].items():
            problems = []
            if result.get("error"):
                problems.append(result["error"])
            if result.get("missing_fields"):
                problems.append(f"missing fields: {result['missing_fields']}")
            if result.get("invalid_tier"):
                problems.append(f"invalid tier: {result['invalid_tier']!r}")
            lines.append(f"  - **{key}**: {'; '.join(problems)}")
    else:
        lines.append("- All checked agent.yaml files declare the required fields "
                      "with valid tier values.")
    lines.append("")
    return lines


def _render_resource_section(resources: dict) -> list[str]:
    lines = ["## 4. Disk / Resource Check", ""]
    py = resources["python_pip"]
    lines.append(f"- Python: {py['python_version']} ({py['python_executable']})")
    pip_display = py["pip_version"] or f"error: {py['pip_error']}"
    lines.append(f"- pip: {pip_display}")
    lines.append("")

    lines.append("| Repo | Disk free | Git status |")
    lines.append("|---|---|---|")
    disk = resources["disk_usage"]
    git = resources["git_status"]
    for key in sorted(set(disk) | set(git)):
        d = disk.get(key, {})
        g = git.get(key, {})
        if d.get("error"):
            disk_cell = f"error: {d['error']}"
        else:
            disk_cell = f"{d.get('free_percent')}% free"
        if g.get("error"):
            git_cell = f"error: {g['error']}"
        elif g.get("clean"):
            git_cell = "clean"
        else:
            git_cell = f"{len(g.get('dirty_files', []))} dirty file(s)"
        lines.append(f"| {key} | {disk_cell} | {git_cell} |")
    lines.append("")
    return lines


def write_report(
    report: dict,
    vault_dir: Path,
    filename: Optional[str] = None,
) -> Path:
    """Write the Markdown report to `vault_dir` and return the path
    written. Filename defaults to a date-stamped name so repeated weekly
    runs don't clobber each other."""
    vault_dir.mkdir(parents=True, exist_ok=True)
    if filename is None:
        date_str = report["generated_at"][:10]
        filename = f"wall-e-report-{date_str}.md"
    out_path = vault_dir / filename
    out_path.write_text(render_markdown(report), encoding="utf-8")
    return out_path

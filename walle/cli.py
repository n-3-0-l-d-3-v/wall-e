"""Wall-E CLI.

`wall-e --health` is an eager top-level flag (not a subcommand), matching
Friday (`friday --health`), Ultron (`ultron --health`), and Jarvis
(`jarvis --health`) -- see README.md and agent.yaml.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Optional

import click

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")

from walle import __version__
from walle.guard import network_guard
from walle.report import build_report, render_markdown, write_report


def _default_vault_dir() -> Path:
    import os
    shared = os.environ.get("VAULT_PATH")
    if shared:
        return Path(shared) / "agents" / "Wall-E"
    return Path(__file__).resolve().parents[1] / "vault" / "Wall-E"


def _print_json(data: dict) -> None:
    click.echo(json.dumps(data, indent=2, default=str))


def _self_health() -> dict:
    """Wall-E's own health: can it locate the ecosystem root (siblings'
    agent.yaml files present) and write to its own vault directory. Does
    NOT poll siblings or Jarvis -- that's `wall-e report`'s job, matching
    the same "own status only" contract Friday/Ultron/Jarvis's `--health`
    implement for themselves."""
    from walle.contract_check import default_agent_yaml_paths

    ecosystem_root = Path(__file__).resolve().parents[2]
    paths = default_agent_yaml_paths(ecosystem_root)
    found = {key: p.exists() for key, p in paths.items()}
    siblings_found = sum(found.values())

    vault_dir = _default_vault_dir()
    vault_writable = True
    vault_error = None
    try:
        vault_dir.mkdir(parents=True, exist_ok=True)
        probe = vault_dir / ".health_probe"
        probe.write_text("ok", encoding="utf-8")
        probe.unlink()
    except OSError as exc:
        vault_writable = False
        vault_error = str(exc)

    healthy = siblings_found > 0 and vault_writable
    return {
        "version": __version__,
        "healthy": healthy,
        "ecosystem_root": str(ecosystem_root),
        "sibling_agent_yamls_found": found,
        "vault_writable": vault_writable,
        "vault_error": vault_error,
    }


@click.group(invoke_without_command=True)
@click.option(
    "--health",
    "show_health",
    is_flag=True,
    default=False,
    help="Print Wall-E's own JSON health report and exit. This is the "
    "ecosystem agent contract's health_check_command -- see agent.yaml. "
    "It does not poll siblings; use `wall-e report` for that.",
)
@click.version_option(__version__, prog_name="wall-e")
@click.pass_context
def cli(ctx: click.Context, show_health: bool) -> None:
    """Wall-E: system-health and maintenance agent."""
    if show_health:
        payload = _self_health()
        _print_json(payload)
        ctx.exit(0 if payload["healthy"] else 1)
    if ctx.invoked_subcommand is None:
        click.echo(ctx.get_help())


@cli.command(name="report")
@click.option("--json", "as_json", is_flag=True, default=False, help="Print machine-readable JSON instead of the Markdown summary.")
@click.option("--no-write", "no_write", is_flag=True, default=False, help="Don't write the report file to vault/Wall-E/ (still prints the summary).")
@click.option("--vault-dir", "vault_dir_raw", default=None, help="Override the vault output directory (default: <repo>/vault/Wall-E/).")
def report_cmd(as_json: bool, no_write: bool, vault_dir_raw: Optional[str]) -> None:
    """Run agent-health aggregation, privacy-audit review, agent-contract
    compliance, and disk/resource checks; write the weekly report to
    vault/Wall-E/ and print a summary."""
    with network_guard():
        report = build_report()

    vault_dir = Path(vault_dir_raw) if vault_dir_raw else _default_vault_dir()

    written_path: Optional[Path] = None
    if not no_write:
        written_path = write_report(report, vault_dir)

    if as_json:
        payload = dict(report)
        payload["written_to"] = str(written_path) if written_path else None
        _print_json(payload)
    else:
        click.echo(render_markdown(report))
        if written_path:
            click.echo(f"\nWritten to: {written_path}")

    sys.exit(0 if report["overall_status"] != "critical" else 1)


def main() -> None:
    cli()


if __name__ == "__main__":
    main()

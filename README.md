# Wall-E

System-health and maintenance agent for the personal multi-agent developer
ecosystem. Built from `10x/docs/agents/wall-e.md` and
`10x/docs/omniroute-privacy-spec.md` in the ecosystem's umbrella repo --
read those for the design intent this implements.

## What's actually built (v1)

Five checks, assembled into one weekly report:

1. **Agent health aggregation** (`walle/health_aggregation.py`) -- shells
   out to `jarvis health` and parses its JSON, rather than re-implementing
   Jarvis's own agent-polling logic. See the module docstring for why
   shelling out was chosen over importing `jarvis.health` as a library.
2. **Privacy audit review** (`walle/audit_review.py`) -- reads Jarvis's
   sqlite audit log (`~/.jarvis/jarvis.db`, `audit_entries` table) directly
   with stdlib `sqlite3`, and:
   - counts dispatches per sensitivity tier,
   - flags any `private`-tier dispatch that was `allowed` and routed to an
     agent other than Ultron (per the privacy spec, only Ultron declares a
     `private` floor -- this should be impossible if Jarvis's own tier
     engine is working, so a hit here is a loud, real finding),
   - flags dispatches whose recorded `reason` matched Jarvis's own
     `"fail-closed default: ..."` string (ambiguous classification that
     defaulted rather than being confidently assigned).
3. **Agent-contract compliance** (`walle/contract_check.py`) -- parses all
   four sibling `agent.yaml` files and verifies each declares `name`,
   `role`, `default_sensitivity_tier`, `entrypoint`, `health_check_command`,
   `sandboxed` with a valid tier value (`private` / `personal-token` /
   `work` / `public`).
4. **Weekly report generation** (`walle/report.py`) -- assembles 1-3 plus
   the resource check below into one Markdown report with YAML frontmatter
   (`date`, `status`, `agent`, `wall_e_version`), written to
   `vault/Wall-E/wall-e-report-<date>.md` -- same "this repo owns a local
   `vault/` path, a future ecosystem bootstrap symlinks it to the real
   shared vault" pattern Ultron/Alfred already use for their own vault
   folders.
5. **Disk / basic resource check** (`walle/resource_check.py`) -- disk
   space (`shutil.disk_usage`, stdlib, OS-agnostic) on the drive each
   sibling repo lives on, Python/pip version sanity, and
   `git status --porcelain` against each of the four sibling repo paths to
   flag uncommitted changes.

## Explicitly out of scope for v1 (and why)

- **Power/thermal profile management** (`tlp`, `auto-cpufreq`, etc.) --
  this machine is currently Windows; the wider ecosystem plan's OS-level
  work targets a future Linux desktop that doesn't exist as a target yet.
  Real implementation belongs to that later phase, not stubbed here.
- **`systemd`/cron scheduling** -- `wall-e report` is a manually-invoked
  one-shot command, not a background daemon. A real recurring-schedule
  mechanism (systemd timer, Task Scheduler, cron) is a later-phase concern
  once there's an actual target OS to wire it into.
- **GUI/desktop-widget health display** -- not attempted; `wall-e report`
  is a CLI report, matching "it doesn't need a chat interface -- it needs
  a schedule and a report format" from `10x/docs/agents/wall-e.md`, minus
  the schedule part (see above).

None of these are stubbed with fake implementations -- they're simply not
present.

## Package vs. command name

`wall-e` (with a hyphen) is a valid `pip`/setuptools **console-script**
name, but Python identifiers can't contain hyphens, so the importable
package is `walle` (module `walle`, e.g. `python -m walle`). The installed
console script is still `wall-e`, matching `agent.yaml`'s
`entrypoint: wall-e` / `health_check_command: wall-e --health`. The
distribution name in `pyproject.toml` is `wall-e-agent` (distribution
names may contain hyphens; this is unrelated to the importable module
name).

## `vault/` and git

`agent.yaml` declares `default_sensitivity_tier: private` for Wall-E.
Unlike Friday/Ultron/Alfred, whose vault notes are knowledge Wall-E's
sibling agents *choose* to write, Wall-E's own vault notes are raw system
telemetry (disk usage, git dirty-file lists, health-check error text) about
this machine, generated automatically every run. Judgment call: the whole
`vault/Wall-E/` directory is gitignored (see `.gitignore`), not just a
`pending/` subfolder the way Ultron does it -- a local git repo can end up
pushed somewhere later, and there's no reviewed/unreviewed split for
generated telemetry the way there is for Ultron's draft RE findings, so the
simpler, more conservative default is "don't commit any of it." A
`.gitkeep` keeps the directory itself tracked so `vault/Wall-E/` exists
after a fresh clone.

## Network guard

Wall-E v1 makes zero network calls (see `agent.yaml`'s notes). It doesn't
need Ultron's real network-lockdown machinery, but `walle/guard.py`
provides a cheap `network_guard()` context manager (monkeypatches
`socket.socket.connect` to raise) wrapped around `wall-e report`'s body, so
a future contributor who accidentally adds a network call gets a loud
failure instead of a silent privacy regression. This is documentation-as-
code, not a security boundary.

## Install

```powershell
cd wall-e
pip install -e ".[dev]"
```

Assumes Wall-E's repo lives alongside the sibling repos
(`friday/`, `ultron/`, `alfred/`, `jarvis/`, `wall-e/` all under the same
parent directory -- this machine's actual layout). `walle/contract_check.py`
and `walle/resource_check.py` derive that layout from
`Path(__file__).resolve().parents[2]`; there is currently no env-var
override for a different layout (unlike Jarvis's `JARVIS_*_PATH` vars) --
not needed yet since Wall-E has exactly one machine to run on so far.

Jarvis's audit-log location follows the same `JARVIS_DB_PATH` env var
Jarvis itself honors (default `~/.jarvis/jarvis.db`), so pointing Wall-E at
a non-default Jarvis DB needs no new configuration on Wall-E's side.

## Usage

```powershell
# Full weekly report: health + audit + contract + disk/git, written to
# vault/Wall-E/ and printed as Markdown
wall-e report

# Same, machine-readable JSON instead of the Markdown summary
wall-e report --json

# Don't write the report file, just print it
wall-e report --no-write

# Wall-E's own status (ecosystem agent.yaml contract's health_check_command)
wall-e --health
```

`wall-e report`'s exit code is `1` if `overall_status` is `critical` (a
real private-tier-routing violation was found), `0` otherwise --
`unhealthy` siblings, non-compliant `agent.yaml`s, or dirty git trees are
surfaced in the report but do not fail the command (this is a report, not
a gate).

## Test discipline

```powershell
cd wall-e
pip install -e ".[dev]"
python -m pytest -v
```

35 tests, all passing on this machine:

- Health aggregation: mocked `jarvis health` subprocess output (command
  not found, valid JSON, malformed JSON, timeout, mixed healthy/unhealthy
  summarization) **plus one real integration test**
  (`tests/test_integration_real_jarvis.py`) that calls the actual `jarvis`
  console script -- this ran successfully on this machine (Jarvis, Friday,
  Ultron, and Alfred all reported healthy at the time of the run). Skips
  cleanly if `jarvis` isn't on PATH, so the rest of the suite doesn't
  depend on that environment existing.
- Privacy audit review: constructed fake sqlite audit-log fixtures covering
  a clean case, a real violation case (private tier routed to a
  non-Ultron agent), a refused-conflict case that must NOT be flagged, and
  a fail-closed-reason-string case.
- Agent-contract compliance: constructed fake `agent.yaml` content (valid,
  missing-field, bad-tier-value, invalid YAML, missing file), **plus a
  real run against the four actual sibling `agent.yaml` files** on this
  machine (`test_real_ecosystem_agent_yamls_are_compliant`) -- all four
  passed.
- Disk/resource/git-status check: a fake temp directory/repo (clean and
  dirty cases), **plus a real run against the four actual sibling repo
  paths** (`test_real_sibling_repos_check`) -- all four were valid git
  repos with readable disk stats at the time of the run.
- Report generation: frontmatter parses as valid YAML with the right keys,
  all five sections present, violation flagging renders, and the written
  file lands with the expected date-stamped name.

## What was actually found running for real on this machine

(Recorded here as a point-in-time observation from the build session, not
a live status -- re-run `wall-e report` for current state.)

- `jarvis health` reported all four agents (Jarvis, Friday, Ultron, Alfred)
  healthy -- an improvement over what Jarvis's own README recorded on its
  build machine (Friday/Alfred/Ultron unhealthy due to missing deps /
  broken console scripts), meaning those issues have since been resolved
  in this environment.
- All four sibling `agent.yaml` files passed the contract-compliance check
  with no missing fields and valid tier values.
- All four sibling repos (`friday`, `ultron`, `alfred`, `jarvis`) were
  clean git working trees with no uncommitted changes, and share one
  drive with double-digit percent free disk space.
- Jarvis's audit log (`~/.jarvis/jarvis.db`) had zero entries at the time
  of this build (no `jarvis ask`/`jarvis route` dispatches had been run
  yet on this machine) -- the privacy-audit section correctly reports "no
  entries found" rather than a false "no violations, all clear" claim.

"""Wall-E: system-health and maintenance agent for the personal multi-agent
developer ecosystem.

See agent.yaml and README.md for the full contract and scope. v1 covers:
agent health aggregation (via Jarvis), privacy-audit review (Jarvis's audit
log), agent.yaml contract compliance, disk/git-status checks, and weekly
Markdown report generation. Explicitly NOT covered in v1: power/thermal
management, scheduling/daemonization, GUI display -- see README.md
"Explicitly out of scope for v1".
"""

from __future__ import annotations

__version__ = "0.1.0"

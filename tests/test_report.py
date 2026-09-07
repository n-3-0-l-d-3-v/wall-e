import yaml

from walle.report import render_markdown, write_report

FAKE_REPORT = {
    "wall_e_version": "0.1.0",
    "generated_at": "2026-01-01T00:00:00+00:00",
    "overall_status": "ok",
    "agent_health": {
        "reachable": True,
        "healthy_count": 4,
        "unhealthy_count": 0,
        "total_count": 4,
        "unhealthy": [],
    },
    "privacy_audit": {
        "total_entries": 3,
        "per_tier_counts": {"work": 2, "private": 1},
        "private_tier_violations": [],
        "fail_closed_count": 0,
        "fail_closed_entries": [],
    },
    "contract_compliance": {
        "checked_count": 4,
        "compliant_count": 4,
        "non_compliant": {},
    },
    "resources": {
        "python_pip": {
            "python_version": "3.12.2",
            "python_executable": "C:\\python.exe",
            "pip_version": "pip 25.3",
            "pip_error": None,
        },
        "disk_usage": {
            "friday": {"free_percent": 40.0},
        },
        "git_status": {
            "friday": {"clean": True, "dirty_files": []},
        },
    },
}


def test_render_markdown_has_frontmatter():
    md = render_markdown(FAKE_REPORT)
    assert md.startswith("---\n")
    frontmatter_end = md.index("---\n", 4)
    frontmatter_text = md[4:frontmatter_end]
    fm = yaml.safe_load(frontmatter_text)
    assert fm["status"] == "ok"
    assert fm["agent"] == "Wall-E"
    assert str(fm["date"]) == "2026-01-01 00:00:00+00:00"


def test_render_markdown_has_all_five_sections():
    md = render_markdown(FAKE_REPORT)
    assert "## 1. Agent Health" in md
    assert "## 2. Privacy Audit Review" in md
    assert "## 3. Agent-Contract Compliance" in md
    assert "## 4. Disk / Resource Check" in md
    assert "## 5. Deferred for v1" in md


def test_render_markdown_flags_violation():
    report = dict(FAKE_REPORT)
    report["privacy_audit"] = dict(FAKE_REPORT["privacy_audit"])
    report["privacy_audit"]["private_tier_violations"] = [
        {"id": 1, "agent": "friday", "timestamp": "t1", "reason": "explicit --tier override"}
    ]
    md = render_markdown(report)
    assert "VIOLATION" in md
    assert "friday" in md


def test_write_report_creates_file(tmp_path):
    out = write_report(FAKE_REPORT, tmp_path)
    assert out.exists()
    assert out.name == "wall-e-report-2026-01-01.md"
    content = out.read_text(encoding="utf-8")
    assert "Wall-E Weekly Report" in content

from pathlib import Path
from types import SimpleNamespace

from walle import cleanup


def _mk(p: Path, size: int):
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_bytes(b"x" * size)


def test_suggestions_rank_and_never_delete(tmp_path, monkeypatch):
    monkeypatch.setenv("WALLE_HOME_OVERRIDE", str(tmp_path))
    _mk(tmp_path / "AppData/Local/pip/Cache/a.whl", 3000)
    _mk(tmp_path / "Downloads/big.iso", 5000)
    _mk(tmp_path / "Downloads/small.txt", 10)
    monkeypatch.setattr(cleanup.shutil, "which", lambda name: None)  # no docker
    items = cleanup.suggestions()
    assert [s.name for s in items] == ["Downloads", "pip cache"]
    downloads = items[0]
    assert downloads.kind == "review" and downloads.top_files[0][0].endswith("big.iso")
    assert items[1].kind == "safe"
    assert (tmp_path / "Downloads/big.iso").exists() and (tmp_path / "AppData/Local/pip/Cache/a.whl").exists()


def test_render_counts_only_safe_items():
    items = [cleanup.Suggestion("pip cache", 2 * cleanup.GB, "safe", "pip cache purge"),
             cleanup.Suggestion("Downloads", 10 * cleanup.GB, "review", "review")]
    out = cleanup.render(items)
    assert "2.0 GB" in out and "nothing was deleted" in out


def test_docker_reclaimable_parses_df(monkeypatch):
    monkeypatch.setattr(cleanup.shutil, "which", lambda name: "docker")
    stdout = '{"Type":"Images","Reclaimable":"2.3GB (33%)"}\n{"Type":"Build Cache","Reclaimable":"512MB"}\n'
    s = cleanup.docker_reclaimable(run=lambda *a, **k: SimpleNamespace(returncode=0, stdout=stdout))
    assert s and abs(s.bytes - (2.3 * cleanup.GB + 512 * 1024 ** 2)) < 1024


def test_parse_size_units():
    assert cleanup.parse_size("1KB") == 1024 and cleanup.parse_size("0B") == 0 and cleanup.parse_size("junk") == 0

from __future__ import annotations

import json
from pathlib import Path

from aots_portable_reports.cli import main
from aots_portable_reports.local_adapter import LocalSnapshotRepository


def write_snapshot_bundle(root: Path, name: str, *, status: str = "passed") -> Path:
    target = root / name
    target.mkdir(parents=True)
    (target / "manifest.json").write_text(
        json.dumps({"country": "SYN", "storm": "TRACE", "forecast_time": "20260101000000"}) + "\n"
    )
    (target / "report-snapshot.json").write_text(
        json.dumps({"country": "SYN", "storm": "TRACE", "forecast_time": "20260101000000", "report": {}}) + "\n"
    )
    (target / "comparison.json").write_text(
        json.dumps({"status": status, "certification_state": "provisional_comparison", "certifying": False}) + "\n"
    )
    (target / "comparison.md").write_text("# Comparison\n")
    (target / "site").mkdir()
    (target / "site" / "index.html").write_text("<html><title>Synthetic</title></html>")
    return target


def test_local_snapshot_repository_discovers_valid_snapshot_bundles(tmp_path: Path) -> None:
    write_snapshot_bundle(tmp_path, "case-a")
    (tmp_path / "not-a-case").mkdir()

    cases = LocalSnapshotRepository(tmp_path).list_snapshots()

    assert [case.case_name for case in cases] == ["case-a"]
    assert cases[0].country == "SYN"
    assert cases[0].storm == "TRACE"


def test_publish_command_writes_manifest_quarto_source_and_site(tmp_path: Path) -> None:
    snapshots = tmp_path / "snapshots"
    snapshots.mkdir()
    write_snapshot_bundle(snapshots, "case-a")
    write_snapshot_bundle(snapshots, "case-b")
    out_dir = tmp_path / "publication"

    exit_code = main(["publish", "--snapshots-dir", str(snapshots), "--out", str(out_dir)])

    assert exit_code == 0
    manifest = json.loads((out_dir / "publication-manifest.json").read_text())
    assert [case["case_name"] for case in manifest["snapshots"]] == ["case-a", "case-b"]
    assert manifest["publication_source"] == "snapshot_output_bundles"
    assert (out_dir / "quarto" / "index.qmd").is_file()
    assert (out_dir / "site" / "index.html").is_file()

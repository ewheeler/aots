from __future__ import annotations

import json
import shutil
from pathlib import Path

from aots_portable_reports.cli import main


FIXTURE_BASELINE = Path(__file__).parents[1] / "fixtures" / "synthetic_baseline"


def copy_fixture(tmp_path: Path) -> Path:
    baseline = tmp_path / "baseline"
    shutil.copytree(FIXTURE_BASELINE, baseline)
    return baseline


def test_snapshot_command_creates_auditable_output_bundle(tmp_path: Path) -> None:
    baseline = copy_fixture(tmp_path)
    out_dir = tmp_path / "out"

    exit_code = main(["snapshot", "--baseline", str(baseline), "--out", str(out_dir)])

    assert exit_code == 0
    assert (out_dir / "manifest.json").is_file()
    assert (out_dir / "report-snapshot.json").is_file()
    assert (out_dir / "comparison.json").is_file()
    assert (out_dir / "comparison.md").is_file()
    assert (out_dir / "quarto" / "index.qmd").is_file()
    assert (out_dir / "quarto" / "_quarto.yml").is_file()
    assert (out_dir / "site").is_dir()
    assert (out_dir / "site" / "index.html").is_file()

    comparison = json.loads((out_dir / "comparison.json").read_text())
    assert comparison["status"] == "passed"


def test_snapshot_command_fails_when_required_artifact_is_missing(tmp_path: Path, capsys) -> None:
    baseline = copy_fixture(tmp_path)
    (baseline / "artifacts" / "admin" / "admin_34.parquet").unlink()

    exit_code = main(["snapshot", "--baseline", str(baseline), "--out", str(tmp_path / "out")])

    assert exit_code == 2
    assert "missing required artifacts" in capsys.readouterr().err


def test_snapshot_command_fails_on_checksum_mismatch(tmp_path: Path, capsys) -> None:
    baseline = copy_fixture(tmp_path)
    (baseline / "artifacts" / "admin" / "admin_34.parquet").write_text("tampered\n")

    exit_code = main(["snapshot", "--baseline", str(baseline), "--out", str(tmp_path / "out")])

    assert exit_code == 2
    assert "checksum mismatch" in capsys.readouterr().err


def test_snapshot_command_fails_on_manifest_schema_mismatch(tmp_path: Path, capsys) -> None:
    baseline = copy_fixture(tmp_path)
    manifest_path = baseline / "manifest.json"
    manifest = json.loads(manifest_path.read_text())
    del manifest["country"]
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n")

    exit_code = main(["snapshot", "--baseline", str(baseline), "--out", str(tmp_path / "out")])

    assert exit_code == 2
    assert "schema mismatch" in capsys.readouterr().err


def test_snapshot_command_fails_on_artifact_row_count_mismatch(tmp_path: Path, capsys) -> None:
    baseline = copy_fixture(tmp_path)
    manifest_path = baseline / "manifest.json"
    manifest = json.loads(manifest_path.read_text())
    manifest["artifacts"][0]["row_count"] = 999
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n")

    exit_code = main(["snapshot", "--baseline", str(baseline), "--out", str(tmp_path / "out")])

    assert exit_code == 2
    assert "row count mismatch" in capsys.readouterr().err


def test_snapshot_command_fails_on_artifact_schema_hash_mismatch(tmp_path: Path, capsys) -> None:
    baseline = copy_fixture(tmp_path)
    manifest_path = baseline / "manifest.json"
    manifest = json.loads(manifest_path.read_text())
    manifest["artifacts"][0]["schema_hash"] = "wrong-schema"
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n")

    exit_code = main(["snapshot", "--baseline", str(baseline), "--out", str(tmp_path / "out")])

    assert exit_code == 2
    assert "schema mismatch" in capsys.readouterr().err

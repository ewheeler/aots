from __future__ import annotations

import json
import shutil
from pathlib import Path

from aots_portable_reports.cli import main
from aots_portable_reports.local_adapter import LocalBaselineRepository


FIXTURE_BASELINE = Path(__file__).parents[1] / "fixtures" / "synthetic_report_baseline"


def copy_case(root: Path, name: str) -> Path:
    target = root / name
    shutil.copytree(FIXTURE_BASELINE, target)
    return target


def test_local_baseline_repository_discovers_valid_baselines(tmp_path: Path) -> None:
    copy_case(tmp_path, "case-a")
    (tmp_path / "not-a-case").mkdir()

    cases = LocalBaselineRepository(tmp_path).list_baselines()

    assert [case.case_name for case in cases] == ["case-a"]
    assert cases[0].country == "SYN"
    assert cases[0].storm == "TRACE"


def test_publish_command_writes_manifest_quarto_source_and_site(tmp_path: Path) -> None:
    snapshots = tmp_path / "snapshots"
    snapshots.mkdir()
    copy_case(snapshots, "case-a")
    copy_case(snapshots, "case-b")
    out_dir = tmp_path / "publication"

    exit_code = main(["publish", "--snapshots-dir", str(snapshots), "--out", str(out_dir)])

    assert exit_code == 0
    manifest = json.loads((out_dir / "publication-manifest.json").read_text())
    assert [case["case_name"] for case in manifest["snapshots"]] == ["case-a", "case-b"]
    assert (out_dir / "quarto" / "index.qmd").is_file()
    assert (out_dir / "site" / "index.html").is_file()

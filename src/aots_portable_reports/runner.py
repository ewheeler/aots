from __future__ import annotations

from pathlib import Path

from hamilton import driver

from aots_portable_reports import dag
from aots_portable_reports.models import SnapshotOutputBundle


def run_snapshot(baseline_dir: Path, out_dir: Path) -> SnapshotOutputBundle:
    dr = driver.Builder().with_modules(dag).build()
    result = dr.execute(["snapshot_output_bundle"], inputs={"baseline_dir": baseline_dir, "out_dir": out_dir})
    return result["snapshot_output_bundle"]

from __future__ import annotations

import subprocess
from pathlib import Path

from aots_portable_reports.local_adapter import LocalSnapshotCase, LocalSnapshotRepository
from aots_portable_reports.models import PublicationManifest, PublicationSnapshotEntry


def publish_snapshot_index(snapshots_dir: Path, out_dir: Path) -> list[LocalSnapshotCase]:
    cases = LocalSnapshotRepository(snapshots_dir).list_snapshots()
    out_dir.mkdir(parents=True, exist_ok=True)
    quarto_dir = out_dir / "quarto"
    site_dir = out_dir / "site"
    quarto_dir.mkdir(parents=True, exist_ok=True)
    site_dir.mkdir(parents=True, exist_ok=True)

    manifest = PublicationManifest(
        snapshots_dir=str(snapshots_dir),
        snapshot_count=len(cases),
        snapshots=[
            PublicationSnapshotEntry(
                case_name=case.case_name,
                path=str(case.path),
                country=case.country,
                storm=case.storm,
                forecast_time=case.forecast_time,
                comparison_status=case.comparison_status,
                certification_state=case.certification_state,
                certifying=case.certifying,
            )
            for case in cases
        ],
    )
    (out_dir / "publication-manifest.json").write_text(manifest.model_dump_json(indent=2) + "\n")
    (quarto_dir / "_quarto.yml").write_text("project:\n  type: website\n  output-dir: ../site\n  render:\n    - index.qmd\n")
    (quarto_dir / "index.qmd").write_text(render_index_qmd(cases))
    subprocess.run(
        ["quarto", "render", str(quarto_dir)],
        check=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    return cases


def render_index_qmd(cases: list[LocalSnapshotCase]) -> str:
    rows = "\n".join(
        f"| {case.case_name} | {case.country} | {case.storm} | {case.forecast_time} | {case.comparison_status} | {case.certification_state} |"
        for case in cases
    )
    if not rows:
        rows = "| _No snapshots found_ |  |  |  |  |  |"
    return "\n".join(
        [
            "---",
            'title: "Portable Report Snapshots"',
            "---",
            "",
            "| Case | Country | Storm | Forecast Time | Comparison | Certification State |",
            "| --- | --- | --- | --- | --- | --- |",
            rows,
            "",
        ]
    )

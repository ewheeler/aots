from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Any

from aots_portable_reports.comparison import compare_report_payloads
from aots_portable_reports.models import (
    ArtifactManifest,
    BaselineManifest,
    ComparisonReport,
    ReportSnapshot,
    SnapshotOutputBundle,
)
from aots_portable_reports.report_wrapper import generate_report_from_baseline
from aots_portable_reports.validation import ValidatedBaseline, load_manifest, validate_baseline


def baseline_manifest(baseline_dir: Path) -> BaselineManifest:
    return load_manifest(baseline_dir)


def validated_baseline(baseline_dir: Path, baseline_manifest: BaselineManifest) -> ValidatedBaseline:
    return validate_baseline(baseline_dir, baseline_manifest)


def source_artifacts(validated_baseline: ValidatedBaseline) -> list[ArtifactManifest]:
    return validated_baseline.manifest.artifacts


def report_wrapper_output(
    validated_baseline: ValidatedBaseline, source_artifacts: list[ArtifactManifest]
) -> dict[str, Any]:
    return generate_report_from_baseline(validated_baseline)


def report_snapshot(validated_baseline: ValidatedBaseline, report_wrapper_output: dict[str, Any]) -> ReportSnapshot:
    manifest = validated_baseline.manifest
    return ReportSnapshot(
        country=manifest.country,
        storm=manifest.storm,
        forecast_time=manifest.forecast_time,
        report=report_wrapper_output,
    )


def comparison_report(validated_baseline: ValidatedBaseline, report_snapshot: ReportSnapshot) -> ComparisonReport:
    return compare_report_payloads(validated_baseline.expected_report, report_snapshot.report)


def quarto_source(report_snapshot: ReportSnapshot) -> dict[str, str]:
    title = f"{report_snapshot.country} {report_snapshot.storm} Report Snapshot"
    index = f"---\ntitle: \"{title}\"\n---\n\n```json\n{json.dumps(report_snapshot.report, indent=2)}\n```\n"
    config = "project:\n  type: website\n  output-dir: ../site\n  render:\n    - index.qmd\n"
    return {"index.qmd": index, "_quarto.yml": config}


def snapshot_output_bundle(
    out_dir: Path,
    validated_baseline: ValidatedBaseline,
    report_snapshot: ReportSnapshot,
    comparison_report: ComparisonReport,
    quarto_source: dict[str, str],
) -> SnapshotOutputBundle:
    out_dir.mkdir(parents=True, exist_ok=True)
    quarto_dir = out_dir / "quarto"
    site_dir = out_dir / "site"
    quarto_dir.mkdir(parents=True, exist_ok=True)
    site_dir.mkdir(parents=True, exist_ok=True)

    output_manifest = {
        "country": validated_baseline.manifest.country,
        "storm": validated_baseline.manifest.storm,
        "forecast_time": validated_baseline.manifest.forecast_time,
        "baseline_version": validated_baseline.manifest.baseline_version,
        "artifact_count": len(validated_baseline.manifest.artifacts),
    }
    manifest_path = out_dir / "manifest.json"
    report_snapshot_path = out_dir / "report-snapshot.json"
    comparison_json_path = out_dir / "comparison.json"
    comparison_markdown_path = out_dir / "comparison.md"

    manifest_path.write_text(json.dumps(output_manifest, indent=2) + "\n")
    report_snapshot_path.write_text(report_snapshot.model_dump_json(indent=2) + "\n")
    comparison_json_path.write_text(comparison_report.model_dump_json(indent=2) + "\n")
    comparison_markdown_path.write_text(_comparison_markdown(comparison_report))
    for name, content in quarto_source.items():
        (quarto_dir / name).write_text(content)
    subprocess.run(
        ["quarto", "render", str(quarto_dir)],
        check=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )

    return SnapshotOutputBundle(
        manifest_path=str(manifest_path),
        report_snapshot_path=str(report_snapshot_path),
        comparison_json_path=str(comparison_json_path),
        comparison_markdown_path=str(comparison_markdown_path),
        quarto_source_dir=str(quarto_dir),
        site_dir=str(site_dir),
    )


def _comparison_markdown(comparison_report: ComparisonReport) -> str:
    lines = ["# Comparison", "", f"Status: {comparison_report.status}", ""]
    if comparison_report.failures:
        lines.extend(["## Failures", ""])
        lines.extend(f"- {issue.code}: {issue.message}" for issue in comparison_report.failures)
        lines.append("")
    if comparison_report.warnings:
        lines.extend(["## Warnings", ""])
        lines.extend(f"- {issue.code}: {issue.message}" for issue in comparison_report.warnings)
        lines.append("")
    return "\n".join(lines)

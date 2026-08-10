from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Any

from aots_portable_reports.alert_contract import (
    write_alert_audit_bundle,
    write_alert_visual_assets,
    write_expected_alert_email_html,
    write_rendered_alert_html_artifact,
)
from aots_portable_reports.alert_renderer import (
    AlertProseProvider,
    AlertProseSlots,
    DEFAULT_ALERT_PROSE_PROVIDER,
    build_alert_claims,
    build_alert_context,
    build_alert_prose_slots,
    build_alert_visual_context,
    compare_alert_output,
    render_alert_visual_assets,
    render_alert_html,
)
from aots_portable_reports.comparison import compare_report_payloads
from aots_portable_reports.models import (
    ArtifactManifest,
    BaselineManifest,
    ComparisonReport,
    ReportSnapshot,
    SnapshotOutputBundle,
)
from aots_portable_reports.report_wrapper import generate_report_from_baseline, load_artifact
from aots_portable_reports.validation import ValidatedBaseline, load_manifest, validate_baseline


def baseline_manifest(baseline_dir: Path) -> BaselineManifest:
    return load_manifest(baseline_dir)


def validated_baseline(
    baseline_dir: Path, baseline_manifest: BaselineManifest
) -> ValidatedBaseline:
    return validate_baseline(baseline_dir, baseline_manifest)


def source_artifacts(validated_baseline: ValidatedBaseline) -> list[ArtifactManifest]:
    return validated_baseline.manifest.artifacts


def report_wrapper_output(
    validated_baseline: ValidatedBaseline, source_artifacts: list[ArtifactManifest]
) -> dict[str, Any]:
    return generate_report_from_baseline(validated_baseline)


def report_snapshot(
    validated_baseline: ValidatedBaseline, report_wrapper_output: dict[str, Any]
) -> ReportSnapshot:
    manifest = validated_baseline.manifest
    return ReportSnapshot(
        country=manifest.country,
        storm=manifest.storm,
        forecast_time=manifest.forecast_time,
        report=report_wrapper_output,
    )


def comparison_report(
    validated_baseline: ValidatedBaseline, report_snapshot: ReportSnapshot
) -> ComparisonReport:
    return compare_report_payloads(
        validated_baseline.expected_report,
        report_snapshot.report,
        expected_report_provenance=validated_baseline.manifest.expected_report_provenance,
    )


def alert_source_artifacts(validated_baseline: ValidatedBaseline) -> dict[str, Any]:
    return {
        artifact.name: load_artifact(validated_baseline.root, artifact)
        for artifact in validated_baseline.manifest.artifacts
        if artifact.name in _ALERT_VISUAL_ARTIFACT_NAMES
        or _is_threshold_visual_artifact(artifact.name)
    }


def alert_visual_context(
    report_snapshot: ReportSnapshot, alert_source_artifacts: dict[str, Any]
) -> dict[str, Any]:
    return build_alert_visual_context(report_snapshot, source_artifacts=alert_source_artifacts)


def alert_context(
    validated_baseline: ValidatedBaseline,
    report_snapshot: ReportSnapshot,
    alert_visual_context: dict[str, Any],
) -> dict[str, Any]:
    context = build_alert_context(report_snapshot, alert_decision=validated_baseline.alert_decision)
    context["visual_context"] = alert_visual_context
    if alert_visual_context.get("timing_rows"):
        context["timing_rows"] = alert_visual_context["timing_rows"]
    return context


def alert_claims(alert_context: dict[str, Any]) -> dict[str, Any]:
    return build_alert_claims(alert_context)


def alert_visual_assets(alert_visual_context: dict[str, Any]) -> list[dict[str, Any]]:
    return render_alert_visual_assets(alert_visual_context)


def alert_prose_provider() -> AlertProseProvider:
    return DEFAULT_ALERT_PROSE_PROVIDER


def alert_prose_slots(
    alert_context: dict[str, Any],
    alert_prose_provider: AlertProseProvider,
) -> AlertProseSlots:
    return build_alert_prose_slots(
        alert_context,
        expected_alert_html=None,
        provider=alert_prose_provider,
    )


def rendered_alert_html(
    validated_baseline: ValidatedBaseline,
    alert_context: dict[str, Any],
    alert_prose_slots: AlertProseSlots,
    alert_visual_assets: list[dict[str, Any]],
) -> str | None:
    decision = validated_baseline.alert_decision
    if decision is None:
        return None
    if decision is not None and decision.product_decision.product_type not in {"warning", "alert"}:
        return None
    return render_alert_html(
        alert_context, prose_slots=alert_prose_slots, visual_assets=alert_visual_assets
    )


def alert_comparison(
    alert_claims: dict[str, Any], rendered_alert_html: str | None
) -> ComparisonReport | None:
    if rendered_alert_html is None:
        return None
    return compare_alert_output(alert_claims, rendered_alert_html)


def quarto_source(report_snapshot: ReportSnapshot) -> dict[str, str]:
    title = f"{report_snapshot.country} {report_snapshot.storm} Report Snapshot"
    index = f'---\ntitle: "{title}"\n---\n\n```json\n{json.dumps(report_snapshot.report, indent=2)}\n```\n'
    config = "project:\n  type: website\n  output-dir: ../site\n  render:\n    - index.qmd\n"
    return {"index.qmd": index, "_quarto.yml": config}


def snapshot_output_bundle(
    out_dir: Path,
    validated_baseline: ValidatedBaseline,
    report_snapshot: ReportSnapshot,
    comparison_report: ComparisonReport,
    alert_context: dict[str, Any],
    alert_claims: dict[str, Any],
    rendered_alert_html: str | None,
    alert_comparison: ComparisonReport | None,
    alert_visual_assets: list[dict[str, Any]],
    quarto_source: dict[str, str],
) -> SnapshotOutputBundle:
    out_dir.mkdir(parents=True, exist_ok=True)
    quarto_dir = out_dir / "quarto"
    site_dir = out_dir / "site"
    quarto_dir.mkdir(parents=True, exist_ok=True)
    site_dir.mkdir(parents=True, exist_ok=True)

    manifest_path = out_dir / "manifest.json"
    report_snapshot_path = out_dir / "report-snapshot.json"
    comparison_json_path = out_dir / "comparison.json"
    comparison_markdown_path = out_dir / "comparison.md"

    report_snapshot_path.write_text(report_snapshot.model_dump_json(indent=2) + "\n")
    comparison_json_path.write_text(comparison_report.model_dump_json(indent=2) + "\n")
    comparison_markdown_path.write_text(_comparison_markdown(comparison_report))
    copied_alert_path = None
    copied_alert_context_path = None
    copied_alert_claims_path = None
    copied_rendered_alert_path = None
    copied_alert_comparison_path = None
    copied_visual_asset_paths: list[str] = []
    if validated_baseline.expected_alert_html is not None:
        copied_alert_path = write_expected_alert_email_html(
            out_dir, validated_baseline.expected_alert_html
        )
    if rendered_alert_html is not None:
        copied_rendered_alert_path = write_rendered_alert_html_artifact(
            out_dir, rendered_alert_html
        )
    if validated_baseline.alert_decision is not None or alert_comparison is not None:
        alert_audit_bundle = write_alert_audit_bundle(
            out_dir, alert_context, alert_claims, alert_comparison
        )
        copied_alert_context_path = alert_audit_bundle.alert_context_path
        copied_alert_claims_path = alert_audit_bundle.alert_claims_path
        copied_alert_comparison_path = alert_audit_bundle.alert_comparison_json_path
    if alert_visual_assets:
        copied_visual_asset_paths = [
            asset.path for asset in write_alert_visual_assets(out_dir, alert_visual_assets)
        ]
    for name, content in quarto_source.items():
        (quarto_dir / name).write_text(content)
    subprocess.run(
        ["quarto", "render", str(quarto_dir)],
        check=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )

    output_manifest = {
        "country": validated_baseline.manifest.country,
        "storm": validated_baseline.manifest.storm,
        "forecast_time": validated_baseline.manifest.forecast_time,
        "baseline_version": validated_baseline.manifest.baseline_version,
        "artifact_count": len(validated_baseline.manifest.artifacts),
        "report_snapshot_path": _bundle_relative_path(report_snapshot_path, out_dir),
        "comparison_json_path": _bundle_relative_path(comparison_json_path, out_dir),
        "comparison_markdown_path": _bundle_relative_path(comparison_markdown_path, out_dir),
        "quarto_source_dir": _bundle_relative_path(quarto_dir, out_dir),
        "site_dir": _bundle_relative_path(site_dir, out_dir),
    }
    if copied_alert_path is not None:
        output_manifest["expected_alert_html_path"] = _bundle_relative_path(
            Path(copied_alert_path), out_dir
        )
        output_manifest["expected_alert_provenance"] = (
            validated_baseline.manifest.expected_alert_provenance
        )
    if copied_rendered_alert_path is not None:
        output_manifest["rendered_alert_html_path"] = _bundle_relative_path(
            Path(copied_rendered_alert_path), out_dir
        )
    if copied_alert_context_path is not None:
        output_manifest["alert_context_path"] = _bundle_relative_path(
            Path(copied_alert_context_path), out_dir
        )
    if copied_alert_claims_path is not None:
        output_manifest["alert_claims_path"] = _bundle_relative_path(
            Path(copied_alert_claims_path), out_dir
        )
    if copied_alert_comparison_path is not None:
        output_manifest["alert_comparison_json_path"] = _bundle_relative_path(
            Path(copied_alert_comparison_path), out_dir
        )
    if copied_visual_asset_paths:
        output_manifest["alert_visual_asset_paths"] = [
            _bundle_relative_path(Path(path), out_dir) for path in copied_visual_asset_paths
        ]
    manifest_path.write_text(json.dumps(output_manifest, indent=2) + "\n")

    return SnapshotOutputBundle(
        manifest_path=str(manifest_path),
        report_snapshot_path=str(report_snapshot_path),
        comparison_json_path=str(comparison_json_path),
        comparison_markdown_path=str(comparison_markdown_path),
        expected_alert_html_path=copied_alert_path,
        alert_context_path=copied_alert_context_path,
        alert_claims_path=copied_alert_claims_path,
        rendered_alert_html_path=copied_rendered_alert_path,
        alert_comparison_json_path=copied_alert_comparison_path,
        alert_visual_asset_paths=copied_visual_asset_paths,
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


def _bundle_relative_path(path: Path, out_dir: Path) -> str:
    return str(path.relative_to(out_dir))


_ALERT_VISUAL_ARTIFACT_NAMES = {
    "admin_geometry",
    "raw_tracks",
    "impact_evolution_50",
    "alert_timing",
}


def _is_threshold_visual_artifact(name: str) -> bool:
    return any(
        name == f"{prefix}_{threshold}"
        for prefix in ("admin", "tiles")
        for threshold in (34, 50, 64)
    )

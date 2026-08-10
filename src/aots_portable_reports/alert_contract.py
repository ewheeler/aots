from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from aots_portable_reports.models import ComparisonReport


EXPECTED_ALERT_EMAIL_FILENAME = "expected-alert.html"
RENDERED_ALERT_HTML_FILENAME = "rendered-alert.html"
ALERT_CONTEXT_FILENAME = "alert-context.json"
ALERT_CLAIMS_FILENAME = "alert-claims.json"
ALERT_COMPARISON_FILENAME = "alert-comparison.json"
ALERT_PROVENANCE_LABELS = ("data", "inferred")
IGNORED_LOCAL_BASELINE_ROOT = Path("known-good-baselines")
ALERT_ASSETS_DIRNAME = "alert-assets"


@dataclass(frozen=True)
class AlertAuditBundlePaths:
    alert_context_path: str
    alert_claims_path: str
    alert_comparison_json_path: str | None


@dataclass(frozen=True)
class AlertVisualAssetPath:
    kind: str
    threshold: int
    path: str
    alt_text: str
    caption: str


def write_expected_alert_email_html(out_dir: Path, expected_alert_email_html: str) -> str:
    path = out_dir / EXPECTED_ALERT_EMAIL_FILENAME
    path.write_text(expected_alert_email_html)
    return str(path)


def write_rendered_alert_html_artifact(out_dir: Path, rendered_alert_html: str) -> str:
    path = out_dir / RENDERED_ALERT_HTML_FILENAME
    path.write_text(rendered_alert_html)
    return str(path)


def write_alert_audit_bundle(
    out_dir: Path,
    alert_context: dict[str, Any],
    alert_claims: dict[str, Any],
    alert_comparison: ComparisonReport | None,
) -> AlertAuditBundlePaths:
    alert_context_path = out_dir / ALERT_CONTEXT_FILENAME
    alert_claims_path = out_dir / ALERT_CLAIMS_FILENAME
    alert_comparison_json_path = (
        out_dir / ALERT_COMPARISON_FILENAME if alert_comparison is not None else None
    )
    alert_context_path.write_text(json.dumps(alert_context, indent=2, default=str) + "\n")
    alert_claims_path.write_text(json.dumps(alert_claims, indent=2, default=str) + "\n")
    if alert_comparison_json_path is not None and alert_comparison is not None:
        alert_comparison_json_path.write_text(alert_comparison.model_dump_json(indent=2) + "\n")
    return AlertAuditBundlePaths(
        alert_context_path=str(alert_context_path),
        alert_claims_path=str(alert_claims_path),
        alert_comparison_json_path=(
            str(alert_comparison_json_path) if alert_comparison_json_path is not None else None
        ),
    )


def write_alert_visual_assets(
    out_dir: Path, visual_assets: list[dict[str, Any]]
) -> list[AlertVisualAssetPath]:
    assets_dir = out_dir / ALERT_ASSETS_DIRNAME
    written: list[AlertVisualAssetPath] = []
    for asset in visual_assets:
        if (
            asset.get("status") != "rendered"
            or not asset.get("png_base64")
            or not asset.get("filename")
        ):
            continue
        assets_dir.mkdir(parents=True, exist_ok=True)
        path = assets_dir / str(asset["filename"])
        path.write_bytes(__import__("base64").b64decode(str(asset["png_base64"])))
        written.append(
            AlertVisualAssetPath(
                kind=str(asset.get("kind")),
                threshold=int(asset.get("threshold") or 0),
                path=str(path),
                alt_text=str(asset.get("alt_text") or ""),
                caption=str(asset.get("caption") or ""),
            )
        )
    return written

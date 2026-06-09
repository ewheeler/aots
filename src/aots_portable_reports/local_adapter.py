from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path

from pydantic import ValidationError

from aots_portable_reports.models import CertificationState, ComparisonReport, ReportSnapshot
from aots_portable_reports.validation import BaselineValidationError, load_manifest, validate_baseline


@dataclass(frozen=True)
class LocalBaselineCase:
    case_name: str
    path: Path
    country: str
    storm: str
    forecast_time: str
    artifact_count: int


class LocalBaselineRepository:
    def __init__(self, root: Path):
        self.root = root

    def list_baselines(self) -> list[LocalBaselineCase]:
        cases: list[LocalBaselineCase] = []
        if not self.root.exists():
            return cases
        for child in sorted(path for path in self.root.iterdir() if path.is_dir()):
            try:
                manifest = load_manifest(child)
                validate_baseline(child, manifest)
            except BaselineValidationError:
                continue
            cases.append(
                LocalBaselineCase(
                    case_name=child.name,
                    path=child,
                    country=manifest.country,
                    storm=manifest.storm,
                    forecast_time=manifest.forecast_time,
                    artifact_count=len(manifest.artifacts),
                )
            )
        return cases


@dataclass(frozen=True)
class LocalSnapshotCase:
    case_name: str
    path: Path
    country: str
    storm: str
    forecast_time: str
    comparison_status: str
    certification_state: CertificationState
    certifying: bool


class LocalSnapshotRepository:
    def __init__(self, root: Path):
        self.root = root

    def list_snapshots(self) -> list[LocalSnapshotCase]:
        cases: list[LocalSnapshotCase] = []
        if not self.root.exists():
            return cases
        for child in sorted(path for path in self.root.iterdir() if path.is_dir()):
            try:
                report_snapshot = ReportSnapshot.model_validate_json((child / "report-snapshot.json").read_text())
                comparison = ComparisonReport.model_validate_json((child / "comparison.json").read_text())
                required = ["manifest.json", "comparison.md", "site/index.html"]
                if any(not (child / rel_path).is_file() for rel_path in required):
                    continue
            except (OSError, ValidationError, json.JSONDecodeError):
                continue
            cases.append(
                LocalSnapshotCase(
                    case_name=child.name,
                    path=child,
                    country=report_snapshot.country,
                    storm=report_snapshot.storm,
                    forecast_time=report_snapshot.forecast_time,
                    comparison_status=comparison.status,
                    certification_state=comparison.certification_state,
                    certifying=comparison.certifying,
                )
            )
        return cases

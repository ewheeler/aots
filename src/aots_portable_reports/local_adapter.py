from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

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

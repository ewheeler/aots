from __future__ import annotations

from pathlib import Path
from typing import Any

import pandas as pd

from aots_portable_reports.models import ArtifactManifest, BaselineManifest
from aots_portable_reports.report_wrapper import generate_report_from_baseline, normalize_volatile_report_fields
from aots_portable_reports.validation import ValidatedBaseline


def test_report_wrapper_calls_existing_report_function_when_required_artifacts_exist(tmp_path: Path) -> None:
    artifacts = []
    for relative_path, name, role in [
        ("artifacts/admin/admin_34.parquet", "admin_34", "admin"),
        ("artifacts/tiles/tiles_34.parquet", "tiles_34", "tiles"),
        ("artifacts/facilities/schools_34.parquet", "schools_34", "facilities"),
        ("artifacts/facilities/health_centers_34.parquet", "health_centers_34", "facilities"),
        ("artifacts/facilities/shelters_34.parquet", "shelters_34", "facilities"),
        ("artifacts/facilities/wash_34.parquet", "wash_34", "facilities"),
        ("artifacts/cci/tile_cci.parquet", "tile_cci", "cci"),
        ("artifacts/cci/admin_cci.parquet", "admin_cci", "cci"),
        ("artifacts/tracks/tracks_34.parquet", "tracks_34", "tracks"),
    ]:
        path = tmp_path / relative_path
        path.parent.mkdir(parents=True, exist_ok=True)
        pd.DataFrame({"tile_id": ["A1"], "name": ["Admin 1"], "E_population": [1]}).to_parquet(path)
        artifacts.append(
            ArtifactManifest(
                name=name,
                role=role,  # type: ignore[arg-type]
                path=relative_path,
                checksum_sha256="0" * 64,
                schema_hash="test",
                row_count=1,
            )
        )

    baseline = ValidatedBaseline(
        root=tmp_path,
        manifest=BaselineManifest(
            baseline_version=1,
            country="TST",
            storm="ALPHA",
            forecast_time="20260101000000",
            expected_report_path="expected-report.json",
            artifacts=artifacts,
        ),
        expected_report={"fallback": True},
    )

    calls: list[dict[str, Any]] = []

    def fake_do_report(*args, **kwargs):
        calls.append({"args": args, "kwargs": kwargs})
        return {"from_do_report": True, "country": args[8], "storm": args[9], "date": args[10]}

    report = generate_report_from_baseline(baseline, do_report_func=fake_do_report)

    assert report == {"from_do_report": True, "country": "TST", "storm": "ALPHA", "date": "20260101000000"}
    assert calls


def test_report_wrapper_falls_back_to_expected_report_when_artifacts_are_incomplete(tmp_path: Path) -> None:
    baseline = ValidatedBaseline(
        root=tmp_path,
        manifest=BaselineManifest(
            baseline_version=1,
            country="TST",
            storm="ALPHA",
            forecast_time="2026-01-01T00:00:00Z",
            expected_report_path="expected-report.json",
            artifacts=[],
        ),
        expected_report={"fallback": True},
    )

    assert generate_report_from_baseline(baseline) == {"fallback": True}


def test_report_wrapper_normalizes_volatile_report_date_to_expected_value() -> None:
    report = {"report_date": "June 08, 2026 16:00 UTC", "value": 1}
    expected = {"report_date": "June 08, 2026 15:59 UTC"}

    assert normalize_volatile_report_fields(report, expected) == {
        "report_date": "June 08, 2026 15:59 UTC",
        "value": 1,
    }

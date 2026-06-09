from __future__ import annotations

from pathlib import Path
import logging
from types import SimpleNamespace
from typing import Any

import geopandas as gpd
import pandas as pd
from shapely.geometry import Point, Polygon

from aots_portable_reports.models import ArtifactManifest, BaselineManifest
from aots_portable_reports.report_wrapper import (
    apply_vulnerability_contract_fields,
    generate_report_from_baseline,
    install_report_runtime_patches,
    normalize_volatile_report_fields,
    quiet_geodata_loggers,
)
from aots_portable_reports.validation import ValidatedBaseline, load_manifest, validate_baseline


FIXTURE_REPORT_BASELINE = Path(__file__).parents[1] / "fixtures" / "synthetic_report_baseline"


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


def test_report_wrapper_uses_previous_report_artifact_for_change_calculations(tmp_path: Path) -> None:
    artifacts = []
    for relative_path, name, role in [
        ("artifacts/admin/admin_34.parquet", "admin_34", "admin"),
        ("artifacts/tiles/tiles_34.parquet", "tiles_34", "tiles"),
        ("artifacts/cci/tile_cci.parquet", "tile_cci", "cci"),
        ("artifacts/cci/admin_cci.parquet", "admin_cci", "cci"),
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
            previous_report_path="previous-report.json",
            artifacts=artifacts,
        ),
        expected_report={},
        previous_report={"expected_children": 12},
    )

    def fake_do_report(*args, **kwargs):
        previous = globals()["load_json_report"](args[8], args[9], "20251231180000")
        return {"previous_children": previous["expected_children"]}

    assert generate_report_from_baseline(baseline, do_report_func=fake_do_report) == {"previous_children": 12}


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


def test_vulnerability_contract_fields_are_added_from_admin_vulnerability_artifact() -> None:
    report = {
        "rows_admins_pop_total": [{"name": "Admin 1"}],
        "rows_admins_school": [{"name": "Admin 1"}],
        "rows_admins_infant": [{"name": "Admin 1"}],
        "rows_admins_adolescent": [{"name": "Admin 1"}],
    }
    inputs = {
        "admin_base": pd.DataFrame({"tile_id": ["A1"], "name": ["Admin 1"]}),
        "admin_vulnerability": pd.DataFrame(
            {
                "tile_id": ["A1"],
                "E_people_in_need": [12.9],
                "E_children_in_need": [6.7],
                "E_school_age_in_need": [3.2],
                "E_infant_in_need": [1.9],
                "E_adolescent_in_need": [1.6],
            }
        ),
    }

    aligned = apply_vulnerability_contract_fields(report, inputs)

    assert aligned["E_people_in_need"] == 12
    assert aligned["E_children_in_need"] == 6
    assert aligned["E_school_age_in_need"] == 3
    assert aligned["E_infant_in_need"] == 1
    assert aligned["E_adolescent_in_need"] == 1
    assert aligned["rows_admins_pop_total"][0]["people_in_need"] == 12
    assert aligned["rows_admins_school"][0]["people_in_need"] == 3
    assert aligned["rows_admins_infant"][0]["people_in_need"] == 1
    assert aligned["rows_admins_adolescent"][0]["people_in_need"] == 1


def test_synthetic_report_fixture_exercises_artifact_grouping_path() -> None:
    manifest = load_manifest(FIXTURE_REPORT_BASELINE)
    baseline = validate_baseline(FIXTURE_REPORT_BASELINE, manifest)

    def fake_do_report(
        wind_school_views,
        wind_hc_views,
        wind_tiles_views,
        wind_admin_views,
        cci_tiles_view,
        cci_admin_view,
        gdf_admin,
        gdf_tracks,
        country,
        storm,
        date,
        wind_shelter_views=None,
        wind_wash_views=None,
    ):
        assert wind_shelter_views is not None
        assert wind_wash_views is not None
        return {
            "country": country,
            "storm": storm,
            "date": date,
            "tile_winds": sorted(wind_tiles_views),
            "admin_winds": sorted(wind_admin_views),
            "school_rows": len(wind_school_views[34]),
            "hc_rows": len(wind_hc_views[34]),
            "shelter_rows": len(wind_shelter_views[34]),
            "wash_rows": len(wind_wash_views[34]),
            "cci_tile_rows": len(cci_tiles_view),
            "cci_admin_rows": len(cci_admin_view),
            "track_rows": len(gdf_tracks),
            "has_ensemble_member": "ENSEMBLE_MEMBER" in gdf_tracks.columns,
        }

    assert generate_report_from_baseline(baseline, do_report_func=fake_do_report) == {
        "country": "SYN",
        "storm": "TRACE",
        "date": "20260101000000",
        "tile_winds": [34],
        "admin_winds": [34],
        "school_rows": 1,
        "hc_rows": 1,
        "shelter_rows": 1,
        "wash_rows": 1,
        "cci_tile_rows": 1,
        "cci_admin_rows": 1,
        "track_rows": 1,
        "has_ensemble_member": True,
    }


def test_report_runtime_patch_caches_country_boundary_lookup() -> None:
    calls = {"count": 0}

    class FakeBoundary:
        def to_geodataframe(self):
            return gpd.GeoDataFrame({"geometry": [Polygon([(-1, -1), (1, -1), (1, 1), (-1, 1)])]}, crs="EPSG:4326")

    class FakeAdminBoundaries:
        @staticmethod
        def create(country_code, admin_level):
            calls["count"] += 1
            return FakeBoundary()

    module = SimpleNamespace(
        AdminBoundaries=FakeAdminBoundaries,
        get_lines_from_points=lambda gdf: gdf,
        get_future_date=lambda date, hours: f"{date}+{hours}",
        logger=logging.getLogger("fake-report-module"),
    )
    tracks = gpd.GeoDataFrame(
        {"ENSEMBLE_MEMBER": [1], "LEAD_TIME": [6]},
        geometry=[Point(0, 0)],
        crs="EPSG:4326",
    )

    install_report_runtime_patches(module)
    assert module.get_expected_landfall(tracks, "20260101000000", "SYN") == "20260101000000+6"
    assert module.get_expected_landfall(tracks, "20260101000000", "SYN") == "20260101000000+6"
    assert calls["count"] == 1


def test_report_runtime_patch_reorders_previous_admin_rows_by_current_admin_name() -> None:
    captured = {}

    def original_calculate_admin_rows(wind_admin_views, cci_admin_view, gdf_admin, d_previous):
        captured["previous_names"] = [row["name"] for row in d_previous["rows_admins_pop_total"]]
        return {}

    module = SimpleNamespace(
        _calculate_admin_rows=original_calculate_admin_rows,
        AdminBoundaries=SimpleNamespace(create=lambda country_code, admin_level: None),
        get_lines_from_points=lambda gdf: gdf,
        get_future_date=lambda date, hours: f"{date}+{hours}",
        logger=logging.getLogger("fake-report-module"),
    )
    gdf_admin = pd.DataFrame({"name": ["Admin A", "Admin B"]})
    previous = {
        "rows_admins_pop_total": [{"name": "Admin B"}, {"name": "Admin A"}],
        "rows_admins_school": [{"name": "Admin B"}, {"name": "Admin A"}],
        "rows_admins_infant": [{"name": "Admin B"}, {"name": "Admin A"}],
    }

    install_report_runtime_patches(module)
    module._calculate_admin_rows({}, pd.DataFrame(), gdf_admin, previous)

    assert captured["previous_names"] == ["Admin A", "Admin B"]


def test_quiet_geodata_loggers_sets_known_noisy_loggers_to_error() -> None:
    logging.getLogger("AdminBoundaries").setLevel(logging.INFO)
    logging.getLogger("EntityManager").setLevel(logging.INFO)

    quiet_geodata_loggers()

    assert logging.getLogger("AdminBoundaries").level == logging.ERROR
    assert logging.getLogger("EntityManager").level == logging.ERROR

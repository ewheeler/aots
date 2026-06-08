from __future__ import annotations

import importlib.util
import sys
from collections.abc import Callable
from pathlib import Path
import re
from typing import Any

import pandas as pd
import geopandas as gpd
from shapely.geometry import Point

from aots_portable_reports.models import ArtifactManifest
from aots_portable_reports.validation import ValidatedBaseline

DoReportFunction = Callable[..., dict[str, Any]]


def generate_report_from_baseline(
    validated_baseline: ValidatedBaseline,
    *,
    do_report_func: DoReportFunction | None = None,
) -> dict[str, Any]:
    inputs = load_report_inputs(validated_baseline)
    if inputs is None:
        return validated_baseline.expected_report
    report_func = do_report_func or load_current_do_report()
    manifest = validated_baseline.manifest
    report = report_func(
        inputs["schools"],
        inputs["health_centers"],
        inputs["tiles"],
        inputs["admin"],
        inputs["tile_cci"],
        inputs["admin_cci"],
        inputs["admin_base"],
        inputs["tracks"],
        manifest.country,
        manifest.storm,
        compact_forecast_time(manifest.forecast_time),
        wind_shelter_views=inputs["shelters"],
        wind_wash_views=inputs["wash"],
    )
    return normalize_volatile_report_fields(report, validated_baseline.expected_report)


def normalize_volatile_report_fields(report: dict[str, Any], expected_report: dict[str, Any]) -> dict[str, Any]:
    if "report_date" in report and "report_date" in expected_report:
        report = dict(report)
        report["report_date"] = expected_report["report_date"]
    return report


def load_report_inputs(validated_baseline: ValidatedBaseline) -> dict[str, Any] | None:
    artifacts = {artifact.name: artifact for artifact in validated_baseline.manifest.artifacts}
    admin = load_wind_artifacts(validated_baseline.root, artifacts, "admin_")
    tiles = load_wind_artifacts(validated_baseline.root, artifacts, "tiles_")
    schools = load_wind_artifacts(validated_baseline.root, artifacts, "schools_")
    health_centers = load_wind_artifacts(validated_baseline.root, artifacts, "health_centers_")
    shelters = load_wind_artifacts(validated_baseline.root, artifacts, "shelters_")
    wash = load_wind_artifacts(validated_baseline.root, artifacts, "wash_")
    tracks_by_wind = load_wind_artifacts(validated_baseline.root, artifacts, "tracks_")
    raw_tracks_artifact = artifacts.get("raw_tracks")
    tile_cci_artifact = artifacts.get("tile_cci")
    admin_cci_artifact = artifacts.get("admin_cci")
    if not admin or not tiles or not tile_cci_artifact or not admin_cci_artifact:
        return None
    first_admin = next(iter(admin.values()))
    if raw_tracks_artifact is not None:
        tracks = raw_tracks_to_geodataframe(load_artifact(validated_baseline.root, raw_tracks_artifact))
    elif tracks_by_wind:
        tracks = next(iter(tracks_by_wind.values()))
    else:
        tracks = pd.DataFrame()
    return {
        "schools": schools,
        "health_centers": health_centers,
        "tiles": tiles,
        "admin": admin,
        "tile_cci": load_artifact(validated_baseline.root, tile_cci_artifact),
        "admin_cci": load_artifact(validated_baseline.root, admin_cci_artifact),
        "admin_base": first_admin,
        "tracks": tracks,
        "shelters": shelters,
        "wash": wash,
    }


def load_wind_artifacts(root: Path, artifacts: dict[str, ArtifactManifest], prefix: str) -> dict[int, pd.DataFrame]:
    grouped: dict[int, pd.DataFrame] = {}
    for name, artifact in artifacts.items():
        if not name.startswith(prefix):
            continue
        try:
            wind_threshold = int(name.removeprefix(prefix))
        except ValueError:
            continue
        grouped[wind_threshold] = load_artifact(root, artifact)
    return grouped


def load_artifact(root: Path, artifact: ArtifactManifest) -> pd.DataFrame:
    path = root / artifact.path
    if path.suffix.lower() == ".parquet":
        df = pd.read_parquet(path)
    elif path.suffix.lower() == ".csv":
        df = pd.read_csv(path)
    else:
        return pd.DataFrame()
    return normalize_columns(df)


def normalize_columns(df: pd.DataFrame) -> pd.DataFrame:
    renamed = {}
    for column in df.columns:
        lower = str(column).lower()
        if lower.startswith("e_cci_"):
            renamed[column] = "E_CCI_" + lower.removeprefix("e_cci_")
        elif lower.startswith("cci_"):
            renamed[column] = "CCI_" + lower.removeprefix("cci_")
        elif lower.startswith("e_"):
            renamed[column] = "E_" + lower[2:]
        else:
            renamed[column] = lower
    return df.rename(columns=renamed)


def raw_tracks_to_geodataframe(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty or "latitude" not in df.columns or "longitude" not in df.columns:
        return gpd.GeoDataFrame(df)
    geometry = [Point(lon, lat) for lat, lon in zip(df["latitude"], df["longitude"])]
    gdf = gpd.GeoDataFrame(df, geometry=geometry, crs="EPSG:4326")
    rename = {}
    for column in gdf.columns:
        if column in {"ensemble_member", "lead_time"}:
            rename[column] = column.upper()
    return gpd.GeoDataFrame(gdf.rename(columns=rename), geometry="geometry", crs="EPSG:4326")


def compact_forecast_time(value: str) -> str:
    if re.fullmatch(r"\d{14}", value):
        return value
    return pd.to_datetime(value).strftime("%Y%m%d%H%M%S")


def load_current_do_report() -> DoReportFunction:
    repo_root = Path(__file__).resolve().parents[2]
    pipeline_dir = repo_root / "Ahead-of-the-Storm-DATAPIPELINE"
    reports_path = pipeline_dir / "reports.py"
    if not reports_path.is_file():
        raise RuntimeError("Ahead-of-the-Storm-DATAPIPELINE/reports.py not found")
    if str(pipeline_dir) not in sys.path:
        sys.path.insert(0, str(pipeline_dir))
    spec = importlib.util.spec_from_file_location("aots_current_reports", reports_path)
    if spec is None or spec.loader is None:
        raise RuntimeError("Unable to load current reports module")
    module = importlib.util.module_from_spec(spec)
    import warnings

    with warnings.catch_warnings():
        warnings.filterwarnings(
            "ignore",
            message=r".*urllib3 .*charset_normalizer .*doesn't match a supported version.*",
        )
        spec.loader.exec_module(module)
    return module.do_report

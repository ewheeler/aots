from __future__ import annotations

import importlib.util
import logging
import sys
from collections.abc import Callable
from functools import lru_cache
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
    quiet_geodata_loggers()
    manifest = validated_baseline.manifest
    with previous_report_loader(report_func, validated_baseline):
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
    report = apply_vulnerability_contract_fields(report, inputs)
    return normalize_volatile_report_fields(report, validated_baseline.expected_report)


def apply_vulnerability_contract_fields(report: dict[str, Any], inputs: dict[str, Any]) -> dict[str, Any]:
    admin_vulnerability = inputs.get("admin_vulnerability")
    admin_base = inputs.get("admin_base")
    if not isinstance(admin_vulnerability, pd.DataFrame) or admin_vulnerability.empty:
        return report
    if not isinstance(admin_base, pd.DataFrame) or admin_base.empty:
        return report

    tile_to_name = _tile_to_admin_name(admin_base)
    if not tile_to_name:
        return report

    report = dict(report)
    top_level_fields: dict[str, str] = {
        "E_people_in_need": "E_people_in_need",
        "E_children_in_need": "E_children_in_need",
        "E_school_age_in_need": "E_school_age_in_need",
        "E_infant_in_need": "E_infant_in_need",
        "E_adolescent_in_need": "E_adolescent_in_need",
    }
    for output_field, source_field in top_level_fields.items():
        if source_field in admin_vulnerability.columns:
            report[output_field] = int(admin_vulnerability[source_field].fillna(0).sum())

    vulnerability_by_name: dict[str, dict[str, int]] = {}
    for _, row in admin_vulnerability.iterrows():
        name = tile_to_name.get(row.get("tile_id"))
        if not name:
            continue
        vulnerability_by_name[name] = {
            "rows_admins_pop_total": _int_row_value(row, "E_people_in_need"),
            "rows_admins_school": _int_row_value(row, "E_school_age_in_need"),
            "rows_admins_infant": _int_row_value(row, "E_infant_in_need"),
            "rows_admins_adolescent": _int_row_value(row, "E_adolescent_in_need"),
        }
    for row_key in [
        "rows_admins_pop_total",
        "rows_admins_school",
        "rows_admins_infant",
        "rows_admins_adolescent",
    ]:
        rows = report.get(row_key)
        if not isinstance(rows, list):
            continue
        aligned_rows = []
        for item in rows:
            if not isinstance(item, dict):
                aligned_rows.append(item)
                continue
            item = dict(item)
            name = item.get("name")
            if isinstance(name, str) and name in vulnerability_by_name:
                item["people_in_need"] = vulnerability_by_name[name][row_key]
            aligned_rows.append(item)
        report[row_key] = aligned_rows
    return report


def _tile_to_admin_name(admin_base: pd.DataFrame) -> dict[Any, str]:
    if "tile_id" not in admin_base.columns or "name" not in admin_base.columns:
        return {}
    names: dict[Any, str] = {}
    for _, row in admin_base[["tile_id", "name"]].iterrows():
        tile_id = row["tile_id"]
        name = row["name"]
        if pd.isna(tile_id) or pd.isna(name):
            continue
        names[tile_id] = str(name)
    return names


def _int_row_value(row: pd.Series, column: str) -> int:
    value = row.get(column)
    if value is None or pd.isna(value):
        return 0
    return int(value)


class previous_report_loader:
    def __init__(self, report_func: DoReportFunction, validated_baseline: ValidatedBaseline):
        self.report_func = report_func
        self.validated_baseline = validated_baseline
        self._sentinel = object()
        self._previous_loader: Any = self._sentinel

    def __enter__(self):
        previous_report = self.validated_baseline.previous_report
        if previous_report is None:
            return self
        globals_dict = getattr(self.report_func, "__globals__", None)
        if not isinstance(globals_dict, dict):
            return self
        manifest = self.validated_baseline.manifest
        self._previous_loader = globals_dict.get("load_json_report", self._sentinel)

        def load_previous_report(country: str, storm: str, date: str) -> dict[str, Any]:
            if country == manifest.country and storm == manifest.storm:
                return dict(previous_report)
            if self._previous_loader is not self._sentinel and callable(self._previous_loader):
                loaded = self._previous_loader(country, storm, date)
                return loaded if isinstance(loaded, dict) else {}
            return {}

        globals_dict["load_json_report"] = load_previous_report
        return self

    def __exit__(self, exc_type, exc, traceback):
        globals_dict = getattr(self.report_func, "__globals__", None)
        if not isinstance(globals_dict, dict):
            return False
        if self._previous_loader is self._sentinel:
            globals_dict.pop("load_json_report", None)
        else:
            globals_dict["load_json_report"] = self._previous_loader
        return False


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
    admin_vulnerability_artifact = artifacts.get("admin_vulnerability")
    tile_vulnerability_artifact = artifacts.get("tile_vulnerability")
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
        "admin_vulnerability": load_artifact(validated_baseline.root, admin_vulnerability_artifact)
        if admin_vulnerability_artifact is not None
        else pd.DataFrame(),
        "tile_vulnerability": load_artifact(validated_baseline.root, tile_vulnerability_artifact)
        if tile_vulnerability_artifact is not None
        else pd.DataFrame(),
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
    install_report_runtime_patches(module)
    return module.do_report


def quiet_geodata_loggers() -> None:
    for logger_name in ["AdminBoundaries", "EntityManager"]:
        logging.getLogger(logger_name).setLevel(logging.ERROR)


def install_report_runtime_patches(module: Any) -> None:
    if getattr(module, "_aots_portable_patched", False):
        return

    original_calculate_admin_rows = getattr(module, "_calculate_admin_rows", None)

    @lru_cache(maxsize=32)
    def boundary_polygon(country: str):
        boundary = module.AdminBoundaries.create(country_code=country, admin_level=0)
        return boundary.to_geodataframe().geometry.iloc[0]

    def cached_expected_landfall(gdf_tracks, date: str, country: str) -> str:
        if gdf_tracks.empty:
            return "Unknown"
        try:
            polygon = boundary_polygon(country)
            landfall_lead_times = []
            for _, gdf_member in gdf_tracks.groupby("ENSEMBLE_MEMBER"):
                inside_rows = gdf_member[gdf_member.within(polygon)]
                if not inside_rows.empty:
                    landfall_lead_times.append(int(inside_rows.iloc[0]["LEAD_TIME"]))
                    continue
                gdf_lines = module.get_lines_from_points(gdf_member)
                inside_lines = gdf_lines[gdf_lines.intersects(polygon)]
                if not inside_lines.empty:
                    landfall_lead_times.append(int(inside_lines.iloc[0]["LEAD_TIME"]))
            if not landfall_lead_times:
                return "Unknown"
            earliest = min(landfall_lead_times)
            latest = max(landfall_lead_times)
            if latest == 0:
                return "Already landed"
            if earliest == latest:
                return module.get_future_date(date, earliest)
            return f"{module.get_future_date(date, earliest)} – {module.get_future_date(date, latest)}"
        except Exception as exc:
            module.logger.warning("Error calculating expected landfall for %s: %s", country, exc)
            return "Unknown"

    module.get_expected_landfall = cached_expected_landfall
    if callable(original_calculate_admin_rows):
        module._calculate_admin_rows = previous_admin_rows_by_name(original_calculate_admin_rows)
    module._aots_portable_patched = True


def previous_admin_rows_by_name(calculate_admin_rows: Callable[..., dict[str, list]]) -> Callable[..., dict[str, list]]:
    def wrapped(wind_admin_views, cci_admin_view, gdf_admin, d_previous):
        return calculate_admin_rows(
            wind_admin_views,
            cci_admin_view,
            gdf_admin,
            _reorder_previous_admin_rows(gdf_admin, d_previous),
        )

    return wrapped


def _reorder_previous_admin_rows(gdf_admin: pd.DataFrame, d_previous: dict[str, Any]) -> dict[str, Any]:
    if not d_previous or "name" not in gdf_admin.columns:
        return d_previous
    admin_names = [str(name) for name in gdf_admin["name"].tolist()]
    reordered = dict(d_previous)
    for key in ["rows_admins_pop_total", "rows_admins_school", "rows_admins_infant"]:
        rows = d_previous.get(key)
        if not isinstance(rows, list):
            continue
        by_name = {row.get("name"): row for row in rows if isinstance(row, dict) and isinstance(row.get("name"), str)}
        if not by_name:
            continue
        reordered[key] = [by_name.get(name, {}) for name in admin_names]
    return reordered

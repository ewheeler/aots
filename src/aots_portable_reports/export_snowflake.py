from __future__ import annotations

import os
import shutil
import uuid
import warnings
from dataclasses import dataclass, field
from datetime import UTC, datetime
from zoneinfo import ZoneInfo
import json
from pathlib import Path
import re
from typing import Any, Protocol

from dotenv import dotenv_values
import pandas as pd

from aots_portable_reports.alert_contract import EXPECTED_ALERT_EMAIL_FILENAME
from aots_portable_reports.validation import dataframe_schema_hash, sha256_file


REQUIRED_SNOWFLAKE_ENV = (
    "SNOWFLAKE_ACCOUNT",
    "SNOWFLAKE_USER",
    "SNOWFLAKE_PASSWORD",
    "SNOWFLAKE_WAREHOUSE",
    "SNOWFLAKE_DATABASE",
    "SNOWFLAKE_SCHEMA",
)


class SnowflakeExportError(Exception):
    pass


class QueryRunner(Protocol):
    def query(self, sql: str, params: list[Any]) -> pd.DataFrame:
        raise NotImplementedError


@dataclass(frozen=True)
class SnowflakeConfig:
    account: str
    user: str
    password: str
    warehouse: str
    database: str
    schema: str
    role: str | None = None

    def non_secret_summary(self) -> str:
        role = self.role if self.role else "<not set>"
        return "\n".join(
            [
                "Snowflake export configuration:",
                f"  account: {self.account}",
                f"  user: {self.user}",
                f"  database: {self.database}",
                f"  schema: {self.schema}",
                f"  warehouse: {self.warehouse}",
                f"  role: {role}",
            ]
        )


@dataclass(frozen=True)
class ExportRequest:
    country: str
    storm: str
    forecast_time: str
    out: Path
    overwrite: bool = False
    plan_only: bool = False
    json_output: bool = False
    env_file: Path | None = None
    wind_thresholds: tuple[int, ...] = ()
    zoom_level: int = 14
    admin_level: int = 1
    include_alert_html: bool = False


@dataclass(frozen=True)
class ExportArtifactSpec:
    name: str
    role: str
    relative_path: str
    source_table: str
    sql: str
    params: list[Any]
    required: bool = True
    geometry_encoding: str | None = None
    query_filter: dict[str, Any] = field(default_factory=dict)


def load_snowflake_config(env_file: Path | None = None) -> SnowflakeConfig:
    values: dict[str, str] = {}
    if env_file is not None:
        if not env_file.is_file():
            raise SnowflakeExportError(f"env file does not exist: {env_file}")
        values.update({k: str(v) for k, v in dotenv_values(env_file).items() if v is not None})
    values.update({key: value for key, value in os.environ.items() if key.startswith("SNOWFLAKE_")})

    missing = [key for key in REQUIRED_SNOWFLAKE_ENV if not values.get(key)]
    if missing:
        raise SnowflakeExportError("missing Snowflake configuration: " + ", ".join(missing))

    return SnowflakeConfig(
        account=values["SNOWFLAKE_ACCOUNT"],
        user=values["SNOWFLAKE_USER"],
        password=values["SNOWFLAKE_PASSWORD"],
        warehouse=values["SNOWFLAKE_WAREHOUSE"],
        database=values["SNOWFLAKE_DATABASE"],
        schema=values["SNOWFLAKE_SCHEMA"],
        role=values.get("SNOWFLAKE_ROLE"),
    )


def ensure_output_target_available(out_dir: Path, *, overwrite: bool) -> None:
    if out_dir.exists() and any(out_dir.iterdir()) and not overwrite:
        raise SnowflakeExportError(f"refusing to overwrite non-empty baseline directory: {out_dir}")


def temporary_sibling_for(out_dir: Path) -> Path:
    return out_dir.with_name(f".{out_dir.name}.tmp-{uuid.uuid4().hex}")


def export_snowflake_baseline(request: ExportRequest, query_runner: QueryRunner | None = None) -> str:
    ensure_output_target_available(request.out, overwrite=request.overwrite)
    config = load_snowflake_config(request.env_file)
    thresholds = list(request.wind_thresholds)

    if query_runner is not None and not thresholds:
        thresholds = discover_wind_thresholds(query_runner, config, request)

    specs = build_export_artifact_specs(config, request, thresholds or [34])
    summary = format_export_plan(config, request, specs, json_output=request.json_output)
    if request.plan_only:
        suffix = "\nPlan only: no Snowflake connection opened and no files written."
        return summary if request.json_output else summary + suffix
    temp_dir = temporary_sibling_for(request.out)
    if temp_dir.exists():
        shutil.rmtree(temp_dir)
    runner = query_runner if query_runner is not None else SnowflakeQueryRunner(config)
    try:
        thresholds = list(request.wind_thresholds) or discover_wind_thresholds(runner, config, request)
        if not thresholds:
            raise SnowflakeExportError("no wind thresholds found for requested country/storm/forecast")
        specs = build_export_artifact_specs(config, request, thresholds)
        artifacts = export_artifact_specs(runner, temp_dir, specs)
        timing_artifact = write_alert_timing_artifact(runner, temp_dir, request)
        if timing_artifact is not None:
            artifacts.append(timing_artifact)
        expected_alert_path = write_expected_alert_email_html(runner, config, temp_dir, request) if request.include_alert_html else None
        write_manifest(temp_dir, request, artifacts, expected_alert_path=expected_alert_path)
        expected_report_provenance = write_expected_report(temp_dir, request, artifacts)
        write_manifest(
            temp_dir,
            request,
            artifacts,
            expected_report_provenance=expected_report_provenance,
            expected_alert_path=expected_alert_path,
        )
        validate_export_layout(temp_dir)
        if request.out.exists():
            shutil.rmtree(request.out)
        temp_dir.replace(request.out)
    except Exception:
        if temp_dir.exists():
            shutil.rmtree(temp_dir)
        raise
    finally:
        close = getattr(runner, "close", None)
        if callable(close):
            close()
    total_rows = sum(int(artifact["row_count"]) for artifact in artifacts)
    alert_line = (
        f"Alert HTML exported: {EXPECTED_ALERT_EMAIL_FILENAME}"
        if request.include_alert_html
        else "Alert HTML exported: no (--include-alert-html not set)"
    )
    return "\n".join(
        [
            f"Exported Known-Good Baseline to {request.out}",
            f"Artifacts exported: {len(artifacts)}",
            f"Rows exported: {total_rows}",
            alert_line,
            "Next snapshot command:",
            f"  uv run aots-report snapshot --baseline {request.out} --out /tmp/aots-report-{request.out.name}",
        ]
    )


def discover_wind_thresholds(runner: QueryRunner, config: SnowflakeConfig, request: ExportRequest) -> list[int]:
    table = qualified_table(config, "TC_ENVELOPES_COMBINED")
    sql = f"""
    SELECT DISTINCT WIND_THRESHOLD
    FROM {table}
    WHERE TRACK_ID = %s
      AND FORECAST_TIME = %s
    ORDER BY WIND_THRESHOLD
    """
    df = runner.query(sql, [request.storm, request.forecast_time])
    if df.empty:
        return []
    return sorted(int(value) for value in df["WIND_THRESHOLD"].dropna().unique())


def build_export_artifact_specs(
    config: SnowflakeConfig, request: ExportRequest, wind_thresholds: list[int]
) -> list[ExportArtifactSpec]:
    specs: list[ExportArtifactSpec] = [
        ExportArtifactSpec(
            name="tile_cci",
            role="cci",
            relative_path="artifacts/cci/tile_cci.parquet",
            source_table=qualified_table(config, "MERCATOR_TILE_CCI_MAT"),
            sql=f"""
            SELECT *
            FROM {qualified_table(config, "MERCATOR_TILE_CCI_MAT")}
            WHERE COUNTRY = %s AND STORM = %s AND FORECAST_DATE = %s AND ZOOM_LEVEL = %s
            """,
            params=[request.country, request.storm, compact_forecast_time(request.forecast_time), request.zoom_level],
            query_filter=base_filter(request) | {"zoom_level": request.zoom_level},
        ),
        ExportArtifactSpec(
            name="admin_cci",
            role="cci",
            relative_path="artifacts/cci/admin_cci.parquet",
            source_table=qualified_table(config, "ADMIN_ALL_CCI_MAT"),
            sql=f"""
            SELECT *
            FROM {qualified_table(config, "ADMIN_ALL_CCI_MAT")}
            WHERE COUNTRY = %s AND STORM = %s AND FORECAST_DATE = %s AND ADMIN_LEVEL = %s
            """,
            params=[request.country, request.storm, compact_forecast_time(request.forecast_time), request.admin_level],
            query_filter=base_filter(request) | {"admin_level": request.admin_level},
        ),
        ExportArtifactSpec(
            name="tile_vulnerability",
            role="vulnerability",
            relative_path="artifacts/vulnerability/tile_vulnerability.parquet",
            source_table=qualified_table(config, "MERCATOR_TILE_VULNERABILITY_MAT"),
            sql=f"""
            SELECT *
            FROM {qualified_table(config, "MERCATOR_TILE_VULNERABILITY_MAT")}
            WHERE COUNTRY = %s AND STORM = %s AND FORECAST_DATE = %s AND ZOOM_LEVEL = %s
            """,
            params=[request.country, request.storm, compact_forecast_time(request.forecast_time), request.zoom_level],
            query_filter=base_filter(request) | {"zoom_level": request.zoom_level},
        ),
        ExportArtifactSpec(
            name="admin_vulnerability",
            role="vulnerability",
            relative_path="artifacts/vulnerability/admin_vulnerability.parquet",
            source_table=qualified_table(config, "ADMIN_ALL_VULNERABILITY_MAT"),
            sql=f"""
            SELECT *
            FROM {qualified_table(config, "ADMIN_ALL_VULNERABILITY_MAT")}
            WHERE COUNTRY = %s AND STORM = %s AND FORECAST_DATE = %s AND ADMIN_LEVEL = %s
            """,
            params=[request.country, request.storm, compact_forecast_time(request.forecast_time), request.admin_level],
            query_filter=base_filter(request) | {"admin_level": request.admin_level},
        ),
        ExportArtifactSpec(
            name="admin_geometry",
            role="geometry",
            relative_path="artifacts/geometry/admin_geometry.parquet",
            source_table=qualified_table(config, "BASE_ADMIN_GEOM_MAT"),
            sql=f"""
            SELECT NAME,
                   CAST(ST_ASGEOJSON(GEOMETRY) AS VARCHAR) AS GEOJSON,
                   ST_X(ST_CENTROID(GEOMETRY)) AS CENTROID_LON,
                   ST_Y(ST_CENTROID(GEOMETRY)) AS CENTROID_LAT
            FROM {qualified_table(config, "BASE_ADMIN_GEOM_MAT")}
            WHERE COUNTRY = %s AND ADMIN_LEVEL = %s
            ORDER BY NAME
            """,
            params=[request.country, request.admin_level],
            query_filter={"country": request.country, "admin_level": request.admin_level},
        ),
        ExportArtifactSpec(
            name="impact_evolution_50",
            role="visualization",
            relative_path="artifacts/visualization/impact_evolution_50.parquet",
            source_table=qualified_table(config, "MERCATOR_TILE_IMPACT_MAT"),
            sql=f"""
            SELECT FORECAST_DATE,
                   SUM(COALESCE(E_POPULATION, 0)) AS POP,
                   SUM(COALESCE(E_INFANT_POPULATION, 0)) AS INFANT,
                   SUM(COALESCE(E_SCHOOL_AGE_POPULATION, 0)) AS SCHOOL_AGE,
                   SUM(COALESCE(E_ADOLESCENT_POPULATION, 0)) AS ADOLESCENT
            FROM {qualified_table(config, "MERCATOR_TILE_IMPACT_MAT")}
            WHERE COUNTRY = %s
              AND STORM = %s
              AND FORECAST_DATE <= %s
              AND WIND_THRESHOLD = 50
              AND ZOOM_LEVEL = %s
            GROUP BY FORECAST_DATE
            ORDER BY FORECAST_DATE
            """,
            params=[request.country, request.storm, compact_forecast_time(request.forecast_time), request.zoom_level],
            query_filter=base_filter(request) | {"wind_threshold": 50, "zoom_level": request.zoom_level},
        ),
        ExportArtifactSpec(
            name="envelopes",
            role="envelopes",
            relative_path="artifacts/envelopes/envelopes.parquet",
            source_table=qualified_table(config, "TC_ENVELOPES_COMBINED"),
            sql=f"""
            SELECT TRACK_ID, FORECAST_TIME, ENSEMBLE_MEMBER, WIND_THRESHOLD,
                   ST_ASWKT(ENVELOPE_REGION) AS GEOMETRY_WKT
            FROM {qualified_table(config, "TC_ENVELOPES_COMBINED")}
            WHERE TRACK_ID = %s AND FORECAST_TIME = %s
            ORDER BY WIND_THRESHOLD, ENSEMBLE_MEMBER
            """,
            params=[request.storm, request.forecast_time],
            geometry_encoding="WKT",
            query_filter={"storm": request.storm, "forecast_time": request.forecast_time},
        ),
        ExportArtifactSpec(
            name="raw_tracks",
            role="tracks",
            relative_path="artifacts/tracks/raw_tracks.parquet",
            source_table=qualified_table(config, "TC_TRACKS"),
            sql=f"""
            SELECT FORECAST_TIME, TRACK_ID, ENSEMBLE_MEMBER, VALID_TIME, LEAD_TIME,
                   LATITUDE, LONGITUDE, PRESSURE_HPA, WIND_SPEED_KNOTS
            FROM {qualified_table(config, "TC_TRACKS")}
            WHERE TRACK_ID = %s AND FORECAST_TIME = %s
            ORDER BY ENSEMBLE_MEMBER, LEAD_TIME
            """,
            params=[request.storm, request.forecast_time],
            query_filter={"storm": request.storm, "forecast_time": request.forecast_time},
        ),
    ]

    for threshold in wind_thresholds:
        specs.extend(_threshold_specs(config, request, threshold))
    return specs


def _threshold_specs(config: SnowflakeConfig, request: ExportRequest, threshold: int) -> list[ExportArtifactSpec]:
    return [
        _threshold_spec(config, request, threshold, "admin", "admin", "ADMIN_ALL_IMPACT_MAT", "artifacts/admin/admin_{threshold}.parquet", ["ADMIN_LEVEL = %s"], [request.admin_level], {"admin_level": request.admin_level}),
        _threshold_spec(config, request, threshold, "tiles", "tiles", "MERCATOR_TILE_IMPACT_MAT", "artifacts/tiles/tiles_{threshold}.parquet", ["ZOOM_LEVEL = %s"], [request.zoom_level], {"zoom_level": request.zoom_level}),
        _threshold_spec(config, request, threshold, "schools", "facilities", "SCHOOL_IMPACT_MAT", "artifacts/facilities/schools_{threshold}.parquet"),
        _threshold_spec(config, request, threshold, "health_centers", "facilities", "HC_IMPACT_MAT", "artifacts/facilities/health_centers_{threshold}.parquet"),
        _threshold_spec(config, request, threshold, "shelters", "facilities", "SHELTER_IMPACT_MAT", "artifacts/facilities/shelters_{threshold}.parquet"),
        _threshold_spec(config, request, threshold, "wash", "facilities", "WASH_IMPACT_MAT", "artifacts/facilities/wash_{threshold}.parquet"),
        _threshold_spec(config, request, threshold, "tracks", "tracks", "TRACK_MAT", "artifacts/tracks/tracks_{threshold}.parquet"),
    ]


def _threshold_spec(
    config: SnowflakeConfig,
    request: ExportRequest,
    threshold: int,
    name_prefix: str,
    role: str,
    table_name: str,
    path_template: str,
    extra_filters: list[str] | None = None,
    extra_params: list[Any] | None = None,
    extra_filter_values: dict[str, Any] | None = None,
) -> ExportArtifactSpec:
    table = qualified_table(config, table_name)
    filters = ["COUNTRY = %s", "STORM = %s", "FORECAST_DATE = %s", "WIND_THRESHOLD = %s"]
    params: list[Any] = [request.country, request.storm, compact_forecast_time(request.forecast_time), threshold]
    if extra_filters:
        filters.extend(extra_filters)
    if extra_params:
        params.extend(extra_params)
    return ExportArtifactSpec(
        name=f"{name_prefix}_{threshold}",
        role=role,
        relative_path=path_template.format(threshold=threshold),
        source_table=table,
        sql=f"SELECT * FROM {table} WHERE " + " AND ".join(filters),
        params=params,
        query_filter=base_filter(request) | {"wind_threshold": threshold} | (extra_filter_values or {}),
    )


def export_artifact_specs(runner: QueryRunner, root: Path, specs: list[ExportArtifactSpec]) -> list[dict[str, Any]]:
    artifacts: list[dict[str, Any]] = []
    for spec in specs:
        df = runner.query(spec.sql, spec.params)
        path = root / spec.relative_path
        path.parent.mkdir(parents=True, exist_ok=True)
        df.to_parquet(path, index=False)
        artifacts.append(
            {
                "name": spec.name,
                "role": spec.role,
                "path": spec.relative_path,
                "required": spec.required,
                "checksum_sha256": sha256_file(path),
                "schema_hash": dataframe_schema_hash(df),
                "row_count": len(df),
                "source_table": spec.source_table,
                "query_filter": spec.query_filter,
                "geometry_encoding": spec.geometry_encoding,
            }
        )
    return artifacts


def write_expected_report_seed(root: Path, request: ExportRequest, artifacts: list[dict[str, Any]]) -> None:
    payload = {
        "country": request.country,
        "storm": request.storm,
        "forecast_time": request.forecast_time,
        "status": "source_artifacts_exported",
        "note": "Seed expected report pending do_report wrapper integration.",
        "artifact_count": len(artifacts),
    }
    (root / "expected-report.json").write_text(json.dumps(payload, indent=2) + "\n")


def write_expected_report(root: Path, request: ExportRequest, artifacts: list[dict[str, Any]]) -> str:
    from aots_portable_reports.models import BaselineManifest
    from aots_portable_reports.report_wrapper import generate_report_from_baseline
    from aots_portable_reports.validation import ValidatedBaseline

    manifest_payload = json.loads((root / "manifest.json").read_text())
    manifest = BaselineManifest.model_validate(manifest_payload)
    baseline = ValidatedBaseline(root=root, manifest=manifest, expected_report={})
    try:
        report = generate_report_from_baseline(baseline)
    except Exception:
        report = {}
    if not report:
        write_expected_report_seed(root, request, artifacts)
        return "seed_placeholder"
    (root / "expected-report.json").write_text(json.dumps(report, indent=2, default=str) + "\n")
    return "portable_wrapper_generated"


def write_expected_alert_email_html(
    runner: QueryRunner,
    config: SnowflakeConfig,
    root: Path,
    request: ExportRequest,
) -> str | None:
    table = qualified_table(config, "ALERT_SENT_LOG")
    sql = f"""
    SELECT EMAIL_BODY
    FROM {table}
    WHERE TRACK_ID = %s
      AND COUNTRY_CODE = %s
      AND FORECAST_TIME = %s
      AND EMAIL_BODY IS NOT NULL
    ORDER BY SENT_AT DESC
    LIMIT 1
    """
    df = runner.query(sql, [request.storm, request.country, request.forecast_time])
    if df.empty or "EMAIL_BODY" not in df.columns:
        return None
    html = df.iloc[0]["EMAIL_BODY"]
    if not isinstance(html, str) or not html.strip():
        return None
    relative_path = EXPECTED_ALERT_EMAIL_FILENAME
    (root / relative_path).write_text(html)
    return relative_path


def write_alert_timing_artifact(runner: QueryRunner, root: Path, request: ExportRequest) -> dict[str, Any] | None:
    rows: list[dict[str, Any]] = []
    timezone_name = lookup_country_timezone(runner, config=None, request=request)
    for threshold in [34, 50, 64]:
        sql = "CALL AOTS.TC_ECMWF.GET_STORM_ARRIVAL_TIMING(%s, %s, %s, %s)"
        df = runner.query(sql, [request.country, request.storm, compact_forecast_time(request.forecast_time), str(threshold)])
        if df.empty:
            continue
        raw = df.iloc[0, 0]
        if not raw:
            continue
        try:
            payload = json.loads(raw) if isinstance(raw, str) else raw
        except json.JSONDecodeError:
            continue
        if not isinstance(payload, dict) or not payload.get("has_timing"):
            continue
        add_local_timing_fields(payload, timezone_name)
        rows.append(payload)
    if not rows:
        return None
    relative_path = "artifacts/timing/alert_timing.parquet"
    path = root / relative_path
    path.parent.mkdir(parents=True, exist_ok=True)
    df = pd.DataFrame(rows)
    df.to_parquet(path, index=False)
    return {
        "name": "alert_timing",
        "role": "timing",
        "path": relative_path,
        "required": False,
        "checksum_sha256": sha256_file(path),
        "schema_hash": dataframe_schema_hash(df),
        "row_count": len(df),
        "source_table": "GET_STORM_ARRIVAL_TIMING",
        "query_filter": {
            "country": request.country,
            "storm": request.storm,
            "forecast_date": compact_forecast_time(request.forecast_time),
        },
    }


def lookup_country_timezone(runner: QueryRunner, config: SnowflakeConfig | None, request: ExportRequest) -> str:
    del config
    try:
        df = runner.query(
            "SELECT COALESCE(TIMEZONE, 'UTC') AS TIMEZONE FROM AOTS.TC_ECMWF.PIPELINE_COUNTRIES WHERE COUNTRY_CODE = %s LIMIT 1",
            [request.country],
        )
    except Exception:
        return "UTC"
    if df.empty or "TIMEZONE" not in df.columns:
        return "UTC"
    value = df.iloc[0]["TIMEZONE"]
    return str(value) if value else "UTC"


def add_local_timing_fields(payload: dict[str, Any], timezone_name: str) -> None:
    try:
        zone = ZoneInfo(timezone_name)
    except Exception:
        zone = ZoneInfo("UTC")
        timezone_name = "UTC"
    for key in ["earliest", "consensus", "latest"]:
        time_key = f"{key}_impact_time"
        local_key = f"{key}_local"
        if not payload.get(time_key):
            continue
        try:
            value = datetime.fromisoformat(str(payload[time_key]).replace(" ", "T"))
        except ValueError:
            continue
        local = value.replace(tzinfo=UTC).astimezone(zone)
        payload[local_key] = local.strftime("%b %d %H:%M")
    payload["timezone"] = timezone_name
    payload["tz_offset"] = _timezone_offset_label(zone)


def _timezone_offset_label(zone: ZoneInfo) -> str:
    offset = datetime.now(UTC).astimezone(zone).utcoffset()
    if offset is None:
        return "UTC"
    minutes = int(offset.total_seconds() // 60)
    sign = "+" if minutes >= 0 else "−"
    abs_minutes = abs(minutes)
    hours, remainder = divmod(abs_minutes, 60)
    suffix = f":{str(remainder).zfill(2)}" if remainder else ""
    return f"UTC{sign}{hours}{suffix}"


def write_manifest(
    root: Path,
    request: ExportRequest,
    artifacts: list[dict[str, Any]],
    *,
    expected_report_provenance: str = "unknown",
    expected_alert_path: str | None = None,
) -> None:
    payload = {
        "baseline_version": 1,
        "country": request.country,
        "storm": request.storm,
        "forecast_time": request.forecast_time,
        "expected_report_path": "expected-report.json",
        "expected_report_provenance": expected_report_provenance,
        "exported_at": datetime.now(UTC).isoformat(),
        "artifacts": artifacts,
    }
    if expected_alert_path is not None:
        payload["expected_alert_path"] = expected_alert_path
    (root / "manifest.json").write_text(json.dumps(payload, indent=2, default=str) + "\n")


def validate_export_layout(root: Path) -> None:
    if not (root / "manifest.json").is_file() or not (root / "expected-report.json").is_file():
        raise SnowflakeExportError("export failed validation: manifest.json or expected-report.json missing")


def format_export_plan(
    config: SnowflakeConfig, request: ExportRequest, specs: list[ExportArtifactSpec], *, json_output: bool
) -> str:
    if json_output:
        payload = {
            "snowflake": {
                "account": config.account,
                "user": config.user,
                "database": config.database,
                "schema": config.schema,
                "warehouse": config.warehouse,
                "role": config.role,
            },
            "request": {
                "country": request.country,
                "storm": request.storm,
                "forecast_time": request.forecast_time,
                "out": str(request.out),
            },
            "artifacts": [
                {
                    "name": spec.name,
                    "role": spec.role,
                    "path": spec.relative_path,
                    "source_table": spec.source_table,
                    "query_filter": spec.query_filter,
                }
                for spec in specs
            ],
        }
        return json.dumps(payload, indent=2)
    artifact_lines = [f"  - {spec.name}: {spec.source_table} -> {spec.relative_path}" for spec in specs]
    return "\n".join([config.non_secret_summary(), f"Output: {request.out}", "Artifacts:", *artifact_lines])


def qualified_table(config: SnowflakeConfig, table: str) -> str:
    return ".".join([safe_identifier(config.database), safe_identifier(config.schema), safe_identifier(table)])


def safe_identifier(value: str) -> str:
    if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", value):
        raise SnowflakeExportError(f"unsafe Snowflake identifier: {value!r}")
    return value.upper()


def base_filter(request: ExportRequest) -> dict[str, Any]:
    return {"country": request.country, "storm": request.storm, "forecast_time": compact_forecast_time(request.forecast_time)}


def compact_forecast_time(value: str) -> str:
    if re.fullmatch(r"\d{14}", value):
        return value
    parsed = pd.to_datetime(value)
    return parsed.strftime("%Y%m%d%H%M%S")


class SnowflakeQueryRunner:
    def __init__(self, config: SnowflakeConfig):
        self.config = config
        self._connection: Any | None = None

    def query(self, sql: str, params: list[Any]) -> pd.DataFrame:
        cursor = self._connect().cursor()
        try:
            cursor.execute(sql, params)
            return cursor.fetch_pandas_all()
        finally:
            cursor.close()

    def close(self) -> None:
        if self._connection is not None:
            self._connection.close()
            self._connection = None

    def _connect(self) -> Any:
        if self._connection is not None:
            return self._connection
        with warnings.catch_warnings():
            warnings.filterwarnings(
                "ignore",
                message=r".*urllib3 .*charset_normalizer .*doesn't match a supported version.*",
            )
            import snowflake.connector

        conn_params: dict[str, Any] = {
            "account": self.config.account,
            "user": self.config.user,
            "password": self.config.password,
            "warehouse": self.config.warehouse,
            "database": self.config.database,
            "schema": self.config.schema,
        }
        if self.config.role:
            conn_params["role"] = self.config.role
        self._connection = snowflake.connector.connect(**conn_params)
        return self._connection

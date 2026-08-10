from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pandas as pd
from pydantic import ValidationError

from aots_portable_reports.models import AlertDecisionEnvelope, ArtifactManifest, BaselineManifest


class BaselineValidationError(Exception):
    pass


@dataclass(frozen=True)
class ValidatedBaseline:
    root: Path
    manifest: BaselineManifest
    expected_report: dict[str, Any]
    expected_alert_html: str | None = None
    alert_decision: AlertDecisionEnvelope | None = None
    previous_report: dict[str, Any] | None = None


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def dataframe_schema_hash(df: pd.DataFrame) -> str:
    schema_payload = [
        {"name": str(col), "dtype": str(dtype)} for col, dtype in zip(df.columns, df.dtypes)
    ]
    encoded = json.dumps(schema_payload, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(encoded).hexdigest()


def artifact_metadata(path: Path, artifact: ArtifactManifest) -> tuple[int | None, str | None]:
    if path.suffix.lower() != ".parquet":
        return None, None
    df = pd.read_parquet(path)
    return len(df), dataframe_schema_hash(df)


def load_manifest(baseline_dir: Path) -> BaselineManifest:
    manifest_path = baseline_dir / "manifest.json"
    if not manifest_path.is_file():
        raise BaselineValidationError("missing required artifacts: manifest.json")
    try:
        return BaselineManifest.model_validate_json(manifest_path.read_text())
    except ValidationError as exc:
        raise BaselineValidationError(f"schema mismatch: {exc}") from exc


def validate_baseline(baseline_dir: Path, manifest: BaselineManifest) -> ValidatedBaseline:
    missing: list[str] = []
    checksum_mismatches: list[str] = []
    row_count_mismatches: list[str] = []
    schema_mismatches: list[str] = []

    expected_report_path = _resolve_baseline_path(baseline_dir, manifest.expected_report_path)
    if not expected_report_path.is_file():
        missing.append(manifest.expected_report_path)
    expected_alert_path = None
    if manifest.expected_alert_path is not None:
        expected_alert_path = _resolve_baseline_path(baseline_dir, manifest.expected_alert_path)
        if not expected_alert_path.is_file():
            missing.append(manifest.expected_alert_path)
    previous_report_path = None
    if manifest.previous_report_path is not None:
        previous_report_path = _resolve_baseline_path(baseline_dir, manifest.previous_report_path)
        if not previous_report_path.is_file():
            missing.append(manifest.previous_report_path)

    for artifact in manifest.artifacts:
        artifact_path = _resolve_baseline_path(baseline_dir, artifact.path)
        if not artifact_path.is_file():
            if artifact.required:
                missing.append(artifact.path)
            continue
        actual_checksum = sha256_file(artifact_path)
        if actual_checksum != artifact.checksum_sha256:
            checksum_mismatches.append(artifact.path)
            continue
        actual_row_count, actual_schema_hash = artifact_metadata(artifact_path, artifact)
        if actual_row_count is not None and actual_row_count != artifact.row_count:
            row_count_mismatches.append(artifact.path)
        if actual_schema_hash is not None and actual_schema_hash != artifact.schema_hash:
            schema_mismatches.append(artifact.path)

    if missing:
        raise BaselineValidationError("missing required artifacts: " + ", ".join(missing))
    if checksum_mismatches:
        raise BaselineValidationError("checksum mismatch: " + ", ".join(checksum_mismatches))
    if row_count_mismatches:
        raise BaselineValidationError("row count mismatch: " + ", ".join(row_count_mismatches))
    if schema_mismatches:
        raise BaselineValidationError("schema mismatch: " + ", ".join(schema_mismatches))

    try:
        expected_report = json.loads(expected_report_path.read_text())
    except json.JSONDecodeError as exc:
        raise BaselineValidationError(
            f"schema mismatch: {manifest.expected_report_path}: {exc}"
        ) from exc
    previous_report = None
    if previous_report_path is not None:
        try:
            previous_report = json.loads(previous_report_path.read_text())
        except json.JSONDecodeError as exc:
            raise BaselineValidationError(
                f"schema mismatch: {manifest.previous_report_path}: {exc}"
            ) from exc
    expected_alert_html = (
        expected_alert_path.read_text() if expected_alert_path is not None else None
    )
    alert_decision = _load_alert_decision(baseline_dir, manifest)

    return ValidatedBaseline(
        root=baseline_dir,
        manifest=manifest,
        expected_report=expected_report,
        expected_alert_html=expected_alert_html,
        alert_decision=alert_decision,
        previous_report=previous_report,
    )


def _resolve_baseline_path(baseline_dir: Path, relative_path: str) -> Path:
    path = Path(relative_path)
    if path.is_absolute():
        raise BaselineValidationError(
            f"schema mismatch: baseline path must be relative: {relative_path}"
        )
    root = baseline_dir.resolve()
    resolved = (root / path).resolve()
    if not resolved.is_relative_to(root):
        raise BaselineValidationError(
            f"schema mismatch: baseline path escapes baseline directory: {relative_path}"
        )
    return resolved


def _load_alert_decision(
    baseline_dir: Path, manifest: BaselineManifest
) -> AlertDecisionEnvelope | None:
    artifacts = [artifact for artifact in manifest.artifacts if artifact.role == "alert_decision"]
    if not artifacts:
        return None
    if len(artifacts) > 1:
        raise BaselineValidationError("schema mismatch: multiple alert decision artifacts")
    artifact = artifacts[0]
    path = _resolve_baseline_path(baseline_dir, artifact.path)
    if not path.is_file():
        return None
    if artifact.schema_hash != "alert-decision-contract-v1" or artifact.row_count != 1:
        raise BaselineValidationError(
            "schema mismatch: alert decision contract metadata must use "
            "schema_hash=alert-decision-contract-v1 and row_count=1"
        )
    try:
        decision = AlertDecisionEnvelope.model_validate_json(path.read_text())
    except ValidationError as exc:
        raise BaselineValidationError(f"schema mismatch: {artifact.path}: {exc}") from exc
    if decision.current_storm_state.storm_name.casefold() != manifest.storm.casefold():
        raise BaselineValidationError(
            "schema mismatch: alert decision storm does not match manifest"
        )
    if decision.country_threat_assessment.country_code.casefold() != manifest.country.casefold():
        raise BaselineValidationError(
            "schema mismatch: alert decision country does not match manifest"
        )
    if decision.country_threat_assessment.forecast_time != manifest.forecast_time:
        raise BaselineValidationError(
            "schema mismatch: alert decision forecast time does not match manifest"
        )
    return decision

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pandas as pd
from pydantic import ValidationError

from aots_portable_reports.models import ArtifactManifest, BaselineManifest


class BaselineValidationError(Exception):
    pass


@dataclass(frozen=True)
class ValidatedBaseline:
    root: Path
    manifest: BaselineManifest
    expected_report: dict[str, Any]
    expected_alert_html: str | None = None
    previous_report: dict[str, Any] | None = None


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def dataframe_schema_hash(df: pd.DataFrame) -> str:
    schema_payload = [{"name": str(col), "dtype": str(dtype)} for col, dtype in zip(df.columns, df.dtypes)]
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

    expected_report_path = baseline_dir / manifest.expected_report_path
    if not expected_report_path.is_file():
        missing.append(manifest.expected_report_path)
    expected_alert_path = None
    if manifest.expected_alert_path is not None:
        expected_alert_path = baseline_dir / manifest.expected_alert_path
        if not expected_alert_path.is_file():
            missing.append(manifest.expected_alert_path)
    previous_report_path = None
    if manifest.previous_report_path is not None:
        previous_report_path = baseline_dir / manifest.previous_report_path
        if not previous_report_path.is_file():
            missing.append(manifest.previous_report_path)

    for artifact in manifest.artifacts:
        artifact_path = baseline_dir / artifact.path
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
        raise BaselineValidationError(f"schema mismatch: {manifest.expected_report_path}: {exc}") from exc
    previous_report = None
    if previous_report_path is not None:
        try:
            previous_report = json.loads(previous_report_path.read_text())
        except json.JSONDecodeError as exc:
            raise BaselineValidationError(f"schema mismatch: {manifest.previous_report_path}: {exc}") from exc
    expected_alert_html = expected_alert_path.read_text() if expected_alert_path is not None else None

    return ValidatedBaseline(
        root=baseline_dir,
        manifest=manifest,
        expected_report=expected_report,
        expected_alert_html=expected_alert_html,
        previous_report=previous_report,
    )

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


ArtifactRole = Literal["admin", "tiles", "facilities", "cci", "tracks", "envelopes"]


class AotsModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ArtifactManifest(AotsModel):
    name: str
    role: ArtifactRole
    path: str
    required: bool = True
    checksum_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    schema_hash: str
    row_count: int = Field(ge=0)
    source_table: str | None = None
    query_filter: dict[str, Any] = Field(default_factory=dict)
    geometry_encoding: str | None = None


class BaselineManifest(AotsModel):
    baseline_version: int = Field(ge=1)
    country: str
    storm: str
    forecast_time: str
    expected_report_path: str
    exported_at: str | None = None
    artifacts: list[ArtifactManifest]


class ReportSnapshot(AotsModel):
    country: str
    storm: str
    forecast_time: str
    report: dict[str, Any]


class ComparisonIssue(AotsModel):
    severity: Literal["failure", "warning"]
    code: str
    message: str


class ComparisonReport(AotsModel):
    status: Literal["passed", "failed"]
    failures: list[ComparisonIssue] = Field(default_factory=list)
    warnings: list[ComparisonIssue] = Field(default_factory=list)


class SnapshotOutputBundle(AotsModel):
    manifest_path: str
    report_snapshot_path: str
    comparison_json_path: str
    comparison_markdown_path: str
    quarto_source_dir: str
    site_dir: str

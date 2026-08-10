from __future__ import annotations

import hashlib
import json
from typing import Any, Literal, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator


ArtifactRole = Literal[
    "admin",
    "tiles",
    "facilities",
    "cci",
    "tracks",
    "envelopes",
    "vulnerability",
    "geometry",
    "visualization",
    "timing",
    "alert_decision",
]
ExpectedReportProvenance = Literal[
    "independent_current_output",
    "portable_wrapper_generated",
    "seed_placeholder",
    "unknown",
]
CertificationState = Literal[
    "integrity_checked",
    "reproduction_ready",
    "provisional_comparison",
    "certifying_comparison",
]
AlertProductType = Literal["none", "warning", "alert", "withheld", "manual_review"]
HazardAvailabilityStatus = Literal["validated", "unavailable", "unvalidated", "incomplete"]


class AotsModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class AlertDecisionModel(AotsModel):
    model_config = ConfigDict(extra="forbid", strict=True)


class CurrentStormState(AlertDecisionModel):
    version: str
    canonical_storm_id: str
    storm_name: str
    basin: str
    provider: str
    source_authority_id: str
    source_feed_url: str
    source_public_guid: str | None = None
    source_public_link: str | None = None
    source_forecast_guid: str | None = None
    source_forecast_link: str | None = None
    source_publication_time: str | None = None
    advisory_id: str
    observed_at: str
    evaluated_at: str
    fresh_until: str
    status: str
    supported: bool
    basin_supported: bool
    is_hurricane: bool
    fresh: bool
    conflicted: bool
    sustained_wind_kt: float | None = Field(default=None, ge=0)
    sustained_wind_averaging_minutes: int | None = Field(default=None, ge=1)
    latitude: float | None = Field(default=None, ge=-90, le=90)
    longitude: float | None = Field(default=None, ge=-180, le=180)
    movement_direction: str | None = None
    movement_speed_kt: float | None = Field(default=None, ge=0)


class CountryThreatAssessment(AlertDecisionModel):
    version: str
    canonical_storm_id: str
    forecast_track_id: str
    forecast_source_version: str
    basin: str
    country_office_id: str
    country_code: str
    country_office_eligible: bool
    forecast_time: str
    horizon_hours: int = Field(ge=1)
    predicate_version: str
    qualifies: bool
    local_hazard_summary: str
    maximum_local_wind_threshold_kt: int | None = Field(default=None, ge=0)
    complete: bool
    available: bool
    reason: str
    registry_version: str
    evaluation_mode: Literal["dry_run", "operational"]
    dry_run_active: bool
    operational_approved: bool
    configured_basin_codes: list[str]
    horizon_complete: bool
    maximum_probability_34: float = Field(ge=0, le=1)
    nonzero_probability_tiles_34: int = Field(ge=0)
    expected_population_34: float = Field(ge=0)


class HazardAvailabilityFact(AlertDecisionModel):
    status: HazardAvailabilityStatus
    source: str | None = None
    detail: str

    @model_validator(mode="after")
    def validate_source(self) -> Self:
        if self.status == "validated" and not self.source:
            raise ValueError("validated hazard availability requires a source")
        return self


class HazardAvailability(AlertDecisionModel):
    version: str
    wind: HazardAvailabilityFact
    rainfall: HazardAvailabilityFact
    storm_surge: HazardAvailabilityFact


class ProductDecision(AlertDecisionModel):
    version: str
    decision_kind: Literal["classifier", "identity_review"]
    product_type: AlertProductType
    reason: str
    storm_identity_version: str
    current_storm_state_version: str
    country_threat_assessment_version: str
    hazard_availability_version: str
    policy_version: str
    contract_version: str
    classifier_version: str
    classifier_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")


class AlertDecisionEnvelope(AlertDecisionModel):
    current_storm_state: CurrentStormState
    country_threat_assessment: CountryThreatAssessment
    hazard_availability: HazardAvailability
    product_decision: ProductDecision

    @model_validator(mode="after")
    def validate_references(self) -> Self:
        state = self.current_storm_state
        threat = self.country_threat_assessment
        decision = self.product_decision
        if state.canonical_storm_id != threat.canonical_storm_id:
            raise ValueError("decision envelope storm identities do not match")
        if decision.current_storm_state_version != state.version:
            raise ValueError("decision envelope current storm state reference does not match")
        if decision.country_threat_assessment_version != threat.version:
            raise ValueError("decision envelope country threat reference does not match")
        if decision.hazard_availability_version != self.hazard_availability.version:
            raise ValueError("decision envelope hazard availability reference does not match")
        decision_identity = decision.model_dump(exclude={"version"})
        expected_decision_version = (
            "product-decision-"
            + hashlib.sha256(
                json.dumps(decision_identity, sort_keys=True, separators=(",", ":")).encode()
            ).hexdigest()
        )
        if decision.version != expected_decision_version:
            raise ValueError("decision envelope Product Decision version is not deterministic")
        if decision.decision_kind == "identity_review" and decision.product_type != "manual_review":
            raise ValueError("decision envelope identity review must be manual review")
        if decision.product_type in {"warning", "alert"}:
            if (
                not state.supported
                or not state.basin_supported
                or not state.fresh
                or state.conflicted
            ):
                raise ValueError("decision envelope product requires usable official storm state")
            if (
                not threat.country_office_eligible
                or not threat.qualifies
                or not threat.complete
                or not threat.available
                or threat.horizon_hours != 144
                or not threat.horizon_complete
                or threat.maximum_local_wind_threshold_kt != 34
                or threat.maximum_probability_34 <= 0.005
                or threat.nonzero_probability_tiles_34 < 3
                or threat.expected_population_34 <= 0
                or self.hazard_availability.wind.status != "validated"
            ):
                raise ValueError(
                    "decision envelope product requires complete qualifying country threat"
                )
        if state.supported and state.status not in {
            "hurricane",
            "tropical_storm",
            "tropical_depression",
        }:
            raise ValueError("decision envelope official status is not supported")
        if state.is_hurricane != (state.supported and state.status == "hurricane"):
            raise ValueError("decision envelope hurricane flag conflicts with official status")
        if decision.product_type == "warning" and state.is_hurricane:
            raise ValueError("decision envelope Warning conflicts with hurricane status")
        if decision.product_type == "alert" and not state.is_hurricane:
            raise ValueError("decision envelope Alert requires hurricane status")
        if decision.product_type == "none" and threat.country_office_eligible and threat.qualifies:
            raise ValueError(
                "decision envelope no-product conflicts with qualifying country threat"
            )
        if decision.product_type in {"manual_review", "withheld"}:
            if decision.decision_kind == "identity_review":
                if (
                    decision.product_type != "manual_review"
                    or not decision.reason.startswith("storm_identity_")
                    or threat.available
                ):
                    raise ValueError("decision envelope identity review is inconsistent")
                return self
            if not threat.country_office_eligible:
                raise ValueError("decision envelope review state requires eligible country threat")
            unusable_threat = not threat.complete or not threat.available
            unusable_state = (
                not state.supported
                or not state.basin_supported
                or not state.fresh
                or state.conflicted
            )
            requires_review = unusable_threat or (threat.qualifies and unusable_state)
            if not requires_review:
                raise ValueError("decision envelope review state requires unusable evidence")
        return self


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
    expected_alert_path: str | None = None
    previous_report_path: str | None = None
    expected_report_provenance: ExpectedReportProvenance = "unknown"
    expected_alert_provenance: ExpectedReportProvenance = "unknown"
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
    certification_state: CertificationState = "provisional_comparison"
    certifying: bool = False
    failures: list[ComparisonIssue] = Field(default_factory=list)
    warnings: list[ComparisonIssue] = Field(default_factory=list)


class SnapshotOutputBundle(AotsModel):
    manifest_path: str
    report_snapshot_path: str
    comparison_json_path: str
    comparison_markdown_path: str
    expected_alert_html_path: str | None = None
    alert_context_path: str | None = None
    alert_claims_path: str | None = None
    rendered_alert_html_path: str | None = None
    alert_comparison_json_path: str | None = None
    alert_visual_asset_paths: list[str] = Field(default_factory=list)
    quarto_source_dir: str
    site_dir: str


class PublicationSnapshotEntry(AotsModel):
    case_name: str
    path: str
    country: str
    storm: str
    forecast_time: str
    comparison_status: str
    certification_state: CertificationState
    certifying: bool


class PublicationManifest(AotsModel):
    publication_source: Literal["snapshot_output_bundles"] = "snapshot_output_bundles"
    snapshots_dir: str
    snapshot_count: int
    snapshots: list[PublicationSnapshotEntry]

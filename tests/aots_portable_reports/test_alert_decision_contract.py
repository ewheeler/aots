from __future__ import annotations

import hashlib
from pathlib import Path
import json
import shutil

import pytest
from pydantic import ValidationError

from aots_portable_reports.models import AlertDecisionEnvelope
from aots_portable_reports.validation import (
    BaselineValidationError,
    load_manifest,
    validate_baseline,
)


FIXTURES = Path(__file__).resolve().parents[1] / "fixtures"


def _decision_payload() -> dict[str, object]:
    return {
        "current_storm_state": {
            "version": "state-1",
            "canonical_storm_id": "AL012026",
            "storm_name": "ALPHA",
            "basin": "AL",
            "provider": "approved-provider",
            "source_authority_id": "synthetic-authority",
            "source_feed_url": "https://example.invalid/synthetic-feed.xml",
            "advisory_id": "advisory-7",
            "observed_at": "2026-01-01T00:00:00Z",
            "evaluated_at": "2026-01-01T00:00:00Z",
            "fresh_until": "2026-01-01T09:00:00Z",
            "status": "hurricane",
            "supported": True,
            "basin_supported": True,
            "is_hurricane": True,
            "fresh": True,
            "conflicted": False,
            "sustained_wind_kt": 70,
            "sustained_wind_averaging_minutes": 1,
        },
        "country_threat_assessment": {
            "version": "threat-1",
            "canonical_storm_id": "AL012026",
            "forecast_track_id": "ALPHA",
            "forecast_source_version": "ecmwf-run-20260101T0000Z",
            "basin": "AL",
            "country_office_id": "TST",
            "country_code": "TST",
            "country_office_eligible": True,
            "forecast_time": "2026-01-01T00:00:00Z",
            "horizon_hours": 144,
            "predicate_version": "threat-v1",
            "qualifies": True,
            "local_hazard_summary": "Tropical-storm-force winds are forecast locally.",
            "maximum_local_wind_threshold_kt": 34,
            "complete": True,
            "available": True,
            "reason": "qualifying_34kt_country_threat",
            "registry_version": "lacro-country-offices-v1-dry-run",
            "evaluation_mode": "dry_run",
            "dry_run_active": True,
            "operational_approved": False,
            "configured_basin_codes": ["AL"],
            "horizon_complete": True,
            "maximum_probability_34": 0.02,
            "nonzero_probability_tiles_34": 4,
            "expected_population_34": 1200,
        },
        "hazard_availability": {
            "version": "hazards-1",
            "wind": {
                "status": "validated",
                "source": "synthetic-wind-artifact",
                "detail": "Cumulative wind exposure is available through 144 hours.",
            },
            "rainfall": {
                "status": "unavailable",
                "source": None,
                "detail": "No validated rainfall impact artifact is available.",
            },
            "storm_surge": {
                "status": "unavailable",
                "source": None,
                "detail": "No validated storm-surge impact artifact is available.",
            },
        },
        "product_decision": {
            "version": "product-decision-604038f95597db4b37cb9e80273a29ffdbf5c02b9d059d02ffcf608e6b781685",
            "decision_kind": "classifier",
            "product_type": "alert",
            "reason": "qualifying_threat_with_hurricane_status",
            "storm_identity_version": "storm-identity-synthetic-1",
            "current_storm_state_version": "state-1",
            "country_threat_assessment_version": "threat-1",
            "hazard_availability_version": "hazards-1",
            "policy_version": "alert-sop-v1",
            "contract_version": "1.0.0",
            "classifier_version": "1.0.0",
            "classifier_sha256": "3177c6fdc93ce845b2e68aff65a37847ed855936702771d4a7c686456ad75744",
        },
    }


def _refresh_decision_version(payload: dict[str, object]) -> None:
    decision = payload["product_decision"]
    assert isinstance(decision, dict)
    identity = {key: value for key, value in decision.items() if key != "version"}
    decision["version"] = (
        "product-decision-"
        + hashlib.sha256(
            json.dumps(identity, sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest()
    )


def test_alert_decision_envelope_accepts_versioned_operational_decision() -> None:
    envelope = AlertDecisionEnvelope.model_validate(_decision_payload())

    assert envelope.product_decision.product_type == "alert"
    assert envelope.current_storm_state.is_hurricane is True
    assert envelope.country_threat_assessment.maximum_local_wind_threshold_kt == 34
    assert envelope.hazard_availability.rainfall.status == "unavailable"


@pytest.mark.parametrize(
    ("path", "value"),
    [
        (("product_decision", "current_storm_state_version"), "wrong-state"),
        (("product_decision", "country_threat_assessment_version"), "wrong-threat"),
        (("country_threat_assessment", "canonical_storm_id"), "different-storm"),
    ],
)
def test_alert_decision_envelope_rejects_inconsistent_fact_references(
    path: tuple[str, str], value: str
) -> None:
    payload = _decision_payload()
    section = payload[path[0]]
    assert isinstance(section, dict)
    section[path[1]] = value

    with pytest.raises(ValidationError, match="decision envelope"):
        AlertDecisionEnvelope.model_validate(payload)


@pytest.mark.parametrize(
    ("section_name", "field_name", "value"),
    [
        ("current_storm_state", "is_hurricane", False),
        ("current_storm_state", "fresh", False),
        ("current_storm_state", "supported", False),
        ("country_threat_assessment", "country_office_eligible", False),
        ("country_threat_assessment", "qualifies", False),
        ("country_threat_assessment", "complete", False),
    ],
)
def test_alert_decision_envelope_rejects_policy_inconsistent_alerts(
    section_name: str, field_name: str, value: bool
) -> None:
    payload = _decision_payload()
    section = payload[section_name]
    assert isinstance(section, dict)
    section[field_name] = value

    with pytest.raises(ValidationError, match="decision envelope"):
        AlertDecisionEnvelope.model_validate(payload)


def test_alert_decision_envelope_rejects_manual_review_with_usable_evidence() -> None:
    payload = _decision_payload()
    product_decision = payload["product_decision"]
    assert isinstance(product_decision, dict)
    product_decision["product_type"] = "manual_review"
    product_decision["reason"] = "manual_override"
    _refresh_decision_version(payload)

    with pytest.raises(ValidationError, match="review state requires unusable evidence"):
        AlertDecisionEnvelope.model_validate(payload)


@pytest.mark.parametrize(
    ("section_name", "field_name", "value"),
    [
        ("current_storm_state", "is_hurricane", "true"),
        ("current_storm_state", "sustained_wind_kt", "70"),
        ("country_threat_assessment", "horizon_hours", "144"),
        ("country_threat_assessment", "qualifies", 1),
    ],
)
def test_alert_decision_envelope_rejects_coerced_scalars(
    section_name: str, field_name: str, value: object
) -> None:
    payload = _decision_payload()
    section = payload[section_name]
    assert isinstance(section, dict)
    section[field_name] = value

    with pytest.raises(ValidationError):
        AlertDecisionEnvelope.model_validate(payload)


def test_alert_decision_envelope_rejects_status_hurricane_flag_mismatch() -> None:
    payload = _decision_payload()
    state = payload["current_storm_state"]
    assert isinstance(state, dict)
    state["status"] = "tropical_storm"

    with pytest.raises(ValidationError, match="hurricane flag conflicts"):
        AlertDecisionEnvelope.model_validate(payload)


def test_baseline_validation_loads_alert_decision_artifact() -> None:
    baseline_dir = FIXTURES / "synthetic_alert_missing_baseline"
    manifest = load_manifest(baseline_dir)

    validated = validate_baseline(baseline_dir, manifest)

    assert validated.alert_decision is not None
    assert validated.alert_decision.product_decision.product_type == "warning"


def test_baseline_validation_enforces_alert_decision_manifest_metadata(tmp_path: Path) -> None:
    baseline_dir = tmp_path / "baseline"
    shutil.copytree(FIXTURES / "synthetic_alert_missing_baseline", baseline_dir)
    manifest_path = baseline_dir / "manifest.json"
    payload = json.loads(manifest_path.read_text())
    decision_artifact = next(
        artifact for artifact in payload["artifacts"] if artifact["role"] == "alert_decision"
    )
    decision_artifact["schema_hash"] = "wrong-contract"
    manifest_path.write_text(json.dumps(payload, indent=2) + "\n")
    manifest = load_manifest(baseline_dir)

    with pytest.raises(BaselineValidationError, match="alert decision contract metadata"):
        validate_baseline(baseline_dir, manifest)


def test_optional_missing_alert_decision_artifact_stays_absent(tmp_path: Path) -> None:
    baseline_dir = tmp_path / "baseline"
    shutil.copytree(FIXTURES / "synthetic_alert_missing_baseline", baseline_dir)
    manifest_path = baseline_dir / "manifest.json"
    payload = json.loads(manifest_path.read_text())
    decision_artifact = next(
        artifact for artifact in payload["artifacts"] if artifact["role"] == "alert_decision"
    )
    decision_artifact["required"] = False
    (baseline_dir / decision_artifact["path"]).unlink()
    manifest_path.write_text(json.dumps(payload, indent=2) + "\n")
    manifest = load_manifest(baseline_dir)

    validated = validate_baseline(baseline_dir, manifest)

    assert validated.alert_decision is None


@pytest.mark.parametrize(
    "field_name",
    ["expected_report_path", "expected_alert_path", "previous_report_path"],
)
def test_baseline_validation_rejects_paths_outside_baseline(
    tmp_path: Path, field_name: str
) -> None:
    baseline_dir = tmp_path / "baseline"
    shutil.copytree(FIXTURES / "synthetic_alert_present_baseline", baseline_dir)
    manifest = load_manifest(baseline_dir)
    escaped = manifest.model_copy(update={field_name: "../outside.json"})

    with pytest.raises(BaselineValidationError, match="escapes baseline directory"):
        validate_baseline(baseline_dir, escaped)

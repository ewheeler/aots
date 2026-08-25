from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from aots_portable_reports.canonical_artifact import (
    CanonicalArtifactError,
    canonical_json_bytes,
    normalize_provisional_track_id,
    verify_content_identity,
    verify_contract_manifest,
)


ROOT = Path(__file__).resolve().parents[2]
CONTRACT_ROOT = ROOT / "Ahead-of-the-Storm-ORCHESTRATION" / "contracts" / "alert_product_v2"


def _load(path: Path) -> dict[str, object]:
    return json.loads(path.read_text(encoding="utf-8"))


def test_root_verifies_the_pinned_orchestration_contract_manifest() -> None:
    verified = verify_contract_manifest(CONTRACT_ROOT)

    manifest = _load(CONTRACT_ROOT / "manifest.json")
    assert verified == {entry["path"] for entry in manifest["files"]}  # type: ignore[index]


def test_root_recomputes_identical_v2_content_identities() -> None:
    vector_names = {
        "official-warning",
        "official-alert",
        "forecast-only-warning",
        "compatibility-profile",
        "composition-manifest",
        "stable-provisional-identity",
        "idempotent-links",
        "publication-public-safe",
    }

    for name in sorted(vector_names):
        vector = _load(CONTRACT_ROOT / "vectors" / f"{name}.json")
        document = vector["document"]
        if vector["rule"] == "stable_provisional_identity":
            documents = [run["episode"] for run in document["runs"]]  # type: ignore[index]
        elif vector["rule"] == "link_set":
            documents = document["links"]  # type: ignore[index]
        else:
            documents = [document]
        for item in documents:
            verify_content_identity(item)


def test_root_rejects_changed_content_with_a_frozen_identity() -> None:
    vector = _load(CONTRACT_ROOT / "vectors" / "official-alert.json")
    document = vector["document"]
    document["created_at"] = "2026-08-07T15:00:00Z"  # type: ignore[index]

    with pytest.raises(CanonicalArtifactError, match="content identity"):
        verify_content_identity(document)


def test_restricted_canonical_json_and_track_normalization_are_portable() -> None:
    assert canonical_json_bytes({"b": 2, "a": "caf\N{LATIN SMALL LETTER E WITH ACUTE}"}) == (
        b'{"a":"caf\xc3\xa9","b":2}'
    )
    assert normalize_provisional_track_id("  \uff107-l  ") == "07-L"

    for invalid in ("AL 07", "AL_07", "Jos\N{LATIN SMALL LETTER E WITH ACUTE}", "AL\n07"):
        with pytest.raises(CanonicalArtifactError):
            normalize_provisional_track_id(invalid)

    with pytest.raises(CanonicalArtifactError, match="null"):
        canonical_json_bytes({"value": None})


def test_root_produces_the_exact_frozen_canonical_bytes() -> None:
    fixtures = {
        "official-alert": "official-alert-product-fact-set.json",
        "compatibility-profile": "compatibility-profile.json",
        "composition-manifest": "composition-manifest.json",
        "publication-public-safe": "publication-manifest.json",
    }
    for vector_name, fixture_name in fixtures.items():
        vector = _load(CONTRACT_ROOT / "vectors" / f"{vector_name}.json")
        expected_bytes = (CONTRACT_ROOT / "canonical" / fixture_name).read_bytes()
        assert canonical_json_bytes(vector["document"]) == expected_bytes


def test_frozen_v1_external_compatibility_references_still_match() -> None:
    references = _load(CONTRACT_ROOT / "v1-conformance" / "external-compatibility-references.json")
    for reference in references["references"]:  # type: ignore[index]
        path = ROOT / reference["path"]
        actual = "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()
        assert actual == reference["file_checksum"]

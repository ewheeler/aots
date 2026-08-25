from __future__ import annotations

import hashlib
import json
import re
import unicodedata
from pathlib import Path, PurePosixPath
from typing import Any


class CanonicalArtifactError(ValueError):
    pass


_SAFE_INTEGER = 2**53 - 1
_TRACK_ID_PATTERN = re.compile(r"^[A-Z0-9]+(?:-[A-Z0-9]+)*$")
_DIGEST_PATTERN = re.compile(r"^sha256:([0-9a-f]{64})$")
_IDENTITIES = {
    "urn:aots:schema:product-decision:2": ("product_decision_id", "pd2:"),
    "urn:aots:schema:product-fact-set:2": ("fact_set_id", "pfs2:"),
    "urn:aots:schema:storm-episode:2": ("episode_id", "episode2:"),
    "urn:aots:schema:storm-episode-link:1": ("link_id", "episode-link1:"),
    "urn:aots:schema:artifact-reference:1": ("artifact_id", "artifact1:"),
    "urn:aots:schema:product-fact-set-producer-result:1": (
        "result_id",
        "producer-result1:",
    ),
    "urn:aots:schema:composition-manifest:1": ("composition_id", "cm1:"),
    "urn:aots:schema:publication-manifest:2": ("publication_id", "publication2:"),
    "urn:aots:schema:v1-policy-result-aggregate:1": ("aggregate_id", "v1-aggregate1:"),
}
_SORTED_SCALAR_FIELDS = {
    "derivation_reference_ids",
    "evidence_reference_ids",
    "input_evidence_reference_ids",
    "public_artifact_roles",
    "reason_codes",
    "source_product_reference_ids",
    "source_reference_ids",
}


def canonical_json_bytes(value: Any) -> bytes:
    _validate_canonical_value(value)
    _validate_semantic_ordering(value)
    return json.dumps(
        value,
        allow_nan=False,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")


def normalize_provisional_track_id(value: object) -> str:
    if not isinstance(value, str):
        raise CanonicalArtifactError("track identifier must be a string")
    normalized = unicodedata.normalize("NFKC", value)
    if any(unicodedata.category(character) == "Cc" for character in normalized):
        raise CanonicalArtifactError("track identifier contains control characters")
    normalized = normalized.strip()
    if not normalized or not normalized.isascii():
        raise CanonicalArtifactError("track identifier must normalize to non-empty ASCII")
    normalized = normalized.upper()
    if _TRACK_ID_PATTERN.fullmatch(normalized) is None:
        raise CanonicalArtifactError("track identifier has an unsupported shape")
    return normalized


def verify_content_identity(document: object) -> None:
    if not isinstance(document, dict):
        raise CanonicalArtifactError("content-addressed document must be an object")
    schema_id = document.get("schema_id")
    if schema_id == "urn:aots:schema:presentation-profile:1":
        projection = {key: value for key, value in document.items() if key != "content_digest"}
        expected_digest = _sha256_digest(canonical_json_bytes(projection))
        if document.get("content_digest") != expected_digest:
            raise CanonicalArtifactError("content identity mismatch")
        return
    if schema_id not in _IDENTITIES:
        raise CanonicalArtifactError(f"unsupported content-addressed schema: {schema_id!r}")

    identity_field, identity_prefix = _IDENTITIES[schema_id]
    projection = {
        key: value
        for key, value in document.items()
        if key not in {identity_field, "content_digest"}
    }
    expected_digest = _sha256_digest(canonical_json_bytes(projection))
    digest_match = _DIGEST_PATTERN.fullmatch(expected_digest)
    if digest_match is None:
        raise CanonicalArtifactError("invalid computed digest")
    expected_identity = identity_prefix + digest_match.group(1)
    if (
        document.get("content_digest") != expected_digest
        or document.get(identity_field) != expected_identity
    ):
        raise CanonicalArtifactError("content identity mismatch")


def verify_contract_manifest(contract_root: Path) -> set[str]:
    manifest_path = contract_root / "manifest.json"
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise CanonicalArtifactError("contract manifest is not readable JSON") from exc
    if not isinstance(manifest, dict) or manifest.get("provenance") != "synthetic_public_test_data":
        raise CanonicalArtifactError("contract manifest provenance is invalid")
    entries = manifest.get("files")
    if not isinstance(entries, list):
        raise CanonicalArtifactError("contract manifest files must be a list")

    verified: set[str] = set()
    resolved_root = contract_root.resolve()
    for entry in entries:
        if not isinstance(entry, dict) or set(entry) != {"path", "file_checksum"}:
            raise CanonicalArtifactError("contract manifest entry is invalid")
        relative_path = entry["path"]
        checksum = entry["file_checksum"]
        if not isinstance(relative_path, str) or not _is_safe_relative_path(relative_path):
            raise CanonicalArtifactError("contract manifest path is unsafe")
        if relative_path in verified:
            raise CanonicalArtifactError("contract manifest path is duplicated")
        path = (contract_root / relative_path).resolve()
        if not path.is_relative_to(resolved_root) or not path.is_file():
            raise CanonicalArtifactError("contract manifest path does not resolve to a file")
        actual = _sha256_digest(path.read_bytes())
        if checksum != actual:
            raise CanonicalArtifactError(f"contract manifest checksum mismatch: {relative_path}")
        verified.add(relative_path)

    present = {
        path.relative_to(contract_root).as_posix()
        for path in contract_root.rglob("*")
        if path.is_file() and path != manifest_path
    }
    if present != verified:
        raise CanonicalArtifactError("contract manifest file inventory mismatch")
    return verified


def _validate_canonical_value(value: Any) -> None:
    if value is None:
        raise CanonicalArtifactError("null JSON values are forbidden")
    if isinstance(value, bool):
        return
    if isinstance(value, int):
        if not -_SAFE_INTEGER <= value <= _SAFE_INTEGER:
            raise CanonicalArtifactError("integer is outside the interoperable safe range")
        return
    if isinstance(value, float):
        raise CanonicalArtifactError("floating-point JSON values are forbidden")
    if isinstance(value, str):
        if unicodedata.normalize("NFC", value) != value:
            raise CanonicalArtifactError("string value must already be NFC")
        return
    if isinstance(value, list):
        for item in value:
            _validate_canonical_value(item)
        return
    if isinstance(value, dict):
        for key, item in value.items():
            if not isinstance(key, str) or not key or not key.isascii():
                raise CanonicalArtifactError("object member names must be non-empty ASCII")
            _validate_canonical_value(item)
        return
    raise CanonicalArtifactError(f"unsupported canonical JSON value: {type(value)!r}")


def _validate_semantic_ordering(value: Any) -> None:
    if isinstance(value, list):
        for item in value:
            _validate_semantic_ordering(item)
        return
    if not isinstance(value, dict):
        return
    for field in _SORTED_SCALAR_FIELDS:
        items = value.get(field)
        if isinstance(items, list) and items != sorted(items):
            raise CanonicalArtifactError(f"semantic set is not sorted: {field}")
    keyed_sets: tuple[tuple[str, Any], ...] = (
        ("hazards", lambda item: item["hazard_kind"]),
        (
            "metrics",
            lambda item: (
                item["metric_code"],
                item["geography"]["type"],
                item["geography"]["id"],
                item.get("threshold_kt", -1),
            ),
        ),
        ("source_references", lambda item: item["artifact_id"]),
        ("visual_source_references", lambda item: item["visual_reference_id"]),
    )
    for field, key in keyed_sets:
        items = value.get(field)
        if isinstance(items, list) and items != sorted(items, key=key):
            raise CanonicalArtifactError(f"semantic set is not sorted: {field}")
    for item in value.values():
        _validate_semantic_ordering(item)


def _is_safe_relative_path(value: str) -> bool:
    if "\\" in value or "\x00" in value or "%2f" in value.casefold() or "%5c" in value.casefold():
        return False
    path = PurePosixPath(value)
    return (
        bool(value)
        and not path.is_absolute()
        and all(part not in {"", ".", ".."} for part in path.parts)
    )


def _sha256_digest(value: bytes) -> str:
    return "sha256:" + hashlib.sha256(value).hexdigest()

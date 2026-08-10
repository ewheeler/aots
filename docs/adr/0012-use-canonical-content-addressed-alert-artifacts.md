# Use Canonical Content-Addressed Alert Artifacts

Status: Accepted. Restricted canonical rules, checksummed vectors, Orchestration authority tests, and an independent root verifier are implemented; producer/consumer V2 runtime is not.

## Context

ProductFactSet, PresentationProfile, Storm Episode Link, and CompositionManifest cross a pinned repository boundary. Ordinary JSON serialization, runtime timestamps, storage paths, or independently reimplemented digest inputs can produce different identities for the same meaning and make provenance unverifiable.

## Decision

Use the RFC 8785-compatible restricted subset in `contracts/alert_product_v2/canonicalization.md`: non-empty ASCII object names; already-NFC strings except provisional-track NFKC normalization; integers only within the interoperable safe range; decimal quantities represented by schema-constrained strings; exact whole-second UTC timestamps; absent optional fields omitted; UTF-8 sorted compact JSON without BOM or trailing newline; and schema-defined semantic-set ordering. JSON `null`, floats, NaN/infinity, negative zero, exponent notation, and runtime-clock identity inputs are forbidden.

SHA-256 semantic digests exclude the contract's identity field and `content_digest`; PresentationProfile excludes only `content_digest`; review-failure `failure_digest` excludes itself. Use the exact ID prefixes in `canonicalization.md`. File checksums bind exact stored bytes separately from semantic content digests.

Keep schema version, producer release, adapter release, renderer release, semantic digest, stable artifact ID, schema ID, and file checksum distinct. `created_at` and `composed_at` are strict semantic timestamps covered by their content identities; runtime clocks, storage metadata, and export time never enter identities.

Orchestration tests validate all 11 schemas, 32 vectors, the checksummed manifest, null rejection, and four exact full-document files under `canonical/`. Root `canonical_artifact.py` and its focused test independently reject null and compare canonicalized official Alert ProductFactSet, compatibility profile, CompositionManifest, and PublicationManifest documents byte-for-byte with all four frozen files. This proves readiness compatibility, not ProductFactSet loading or composition/publication runtime. Unknown versions or digest mismatches fail closed.

## Consequences

- Repeated composition from identical inputs is byte-identical and idempotent.
- Profile changes do not change ProductFactSet or Product Decision identity.
- Storage moves do not change semantic identity, while altered file bytes still fail checksum validation.
- Contract evolution requires explicit schema/version review rather than permissive extra fields.

# Use Raw Provider Identity For Provisional Storm Episodes

Status: Accepted. Raw identifier retention, candidate-key normalization, schemas, vectors, and structural tests are implemented; episode runtime/persistence is not, and operational activation remains blocked on historical/provider stability evidence.

## Context

Forecast-only Warning needs identity before official genesis and must later continue into an official episode without rewriting history. Current `TRACK_ID` is not suitable: the ECMWF extractor prefers `longStormName` and falls back to raw BUFR `stormIdentifier`, so the field can represent a display name rather than provider lineage. The audit did not prove stability across Forecast Runs, basin/season uniqueness, normalization behavior, or non-reuse.

## Decision

Retain raw ECMWF BUFR `stormIdentifier` additively and preserve existing `TRACK_ID` behavior. The implemented forecast helper constructs the candidate tuple `(ecmwf-ifs-tc-track, basin, season, normalized_track_id)` but does not persist or hash it. The StormEpisode v2 schema also preserves `provider_storm_identifier_raw` as semantic content.

Normalize the candidate identifier by Unicode NFKC, reject control characters, trim Unicode edge whitespace, require non-empty ASCII, uppercase, then require `^[A-Z0-9]+(?:-[A-Z0-9]+)*$`. Basin is explicitly `AL`, `EP`, or `CP`; season is an explicit integer from 2000 through 9999. The exact authority is `contracts/alert_product_v2/canonicalization.md` and the StormEpisode/ProductFactSet schemas.

Exclude storm name, `TRACK_ID`, forecast time, ensemble member, and official ID from the provisional digest. Connect a provisional episode to official identity through immutable, evidence-bound, content-addressed link events. Identical events are idempotent; conflicting links require manual review; prior decisions are never rewritten. V2 lifecycle keys use `episode_id`.

## Consequences

- Structural raw-field retention and candidate tuple normalization are tested without asserting operational identity quality.
- Forecast-only Alert remains forbidden; provisional identity only enables Warning/no-product/review evaluation.
- Historical samples and provider documentation must still prove cross-run stability, uniqueness, normalization, and non-reuse before activation, or a stronger producer-issued identifier must replace this fallback through a new decision.
- Raw provider identity remains internal-sensitive and is excluded from public output.

## Alternatives Rejected

- Current `TRACK_ID`: failed the audit because it may be a long storm name.
- Storm name plus forecast time: changes across runs and fragments lifecycle.
- Name-only or nearest-time official join: ambiguous and rewrites evidence boundaries.
- Fabricated official identity: incorrectly promotes forecast evidence to official evidence.

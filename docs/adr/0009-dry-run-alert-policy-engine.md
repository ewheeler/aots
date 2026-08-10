# Build The Operational Alert Policy As A Non-Sending Dry-Run Engine

Status: Accepted for dry-run implementation. Operational delivery remains disabled.

## Context

The legacy Watch and Alert procedures combine forecast thresholds, product naming, prose, deduplication, and email delivery. They cannot safely implement the LACRO SOP by renaming outputs. The operational policy needs credential-free behavior tests, content-bound classifier provenance, country-level lifecycle state, recipient-aware attempts, and a path to Snowflake that cannot send during evaluation.

## Decision

Build one composable dry-run engine in Orchestration:

1. `advisory_feed.py` retrieves only the exact configured NHC/CPHC HTTPS RSS URLs with a no-redirect production opener, bounded timeout and response size, UTF-8/DTD/entity rejection, and a payload digest passed into paired Public/Forecast Advisory parsing. Public Advisory text supplies cross-checks; Forecast Advisory text supplies exact knot values and official valid time. Unsupported or unpaired products produce review events.
2. `authoritative_storm_state.py` validates source identity and normalizes HU, TS, or TD advisories into versioned Current Storm State facts with evaluation and expiry times. Policy execution uses the runtime UTC clock, revalidates the full normalized-facts digest, source/basin policy, status/wind consistency, and effective freshness, and passes stale evidence to the classifier for manual review. Other classifications also fail to manual review.
3. `storm_identity.py` accepts canonical IDs directly or an effective, explicitly approved forecast-ID mapping. Identity versions bind the complete normalized mapping registry and effective approval evidence. Name-only and ambiguous matches produce auditable in-memory manual-review Product Decisions.
4. `country_threat.py` evaluates a proposed dry-run predicate for eligible Country Offices: complete 144-hour evidence, maximum 34kt probability greater than 0.005 and no greater than 1, at least three non-zero probability tiles, and positive expected 34kt population exposure. Every qualification value, forecast source version, basin, and registry version participates in the assessment digest.
5. `warning_alert_classifier.py` receives normalized facts only. Unavailable or incomplete threat evidence requires manual review before classification.
6. `alert_lifecycle.py` creates one storm/Country Office lifecycle, permits Warning-to-Alert escalation, suppresses downgrade/non-delivery transitions, and creates recipient-aware attempts that cannot leave dry-run mode.
7. `product_facts.py` assembles versioned deterministic Summary, Situation, and Forecast facts. It requires complete validated cumulative 144-hour wind evidence, exact local-threshold exposure, typed hazard sources, and separately versioned wind-integrated PiN/CHiN with `CHiN <= PiN`.
8. `policy_engine.py` composes these modules and refuses `dry_run=False`.

The Portable Report Package does not yet consume the operational Product Facts object directly. It independently renders from the versioned Alert Decision plus baseline report artifacts, and it must not substitute legacy 50kt totals for missing local 34kt evidence. A future shared Product Facts artifact is required before claiming one end-to-end content contract.

The proposed Country Office registry seeds existing LAC-facing pipeline countries for dry-run evaluation only. `OPERATIONAL_APPROVED` defaults to false for every row.

## Snowflake Boundary

- `04_data/09_alert_policy_tables.sql` creates separate registry, identity, state, threat, decision, and recipient-delivery stores.
- `build_alert_policy_release.py` materializes a content-addressed local release, verifies every copied module, emits `PUT ... OVERWRITE=FALSE`, and creates an inline Snowflake UDF entrypoint that hashes the imported classifier against the release manifest before invocation. The generated script invokes a smoke classification before granting usage. Privileged stage/UDF replacement remains an operational control, so the release is content-addressed rather than inherently immutable.
- Policy table schemas and explicit mutation revokes are implemented, but no Snowflake writer procedure is shipped. Review showed that a safe writer must independently recompute Current Storm State, identity, threat, Product Decision, event, lifecycle transition, Product Facts, and recipient-attempt identities before writing atomically. That boundary remains future work requiring isolated-account malformed-payload, concurrency, and privacy tests.
- Local evaluation contains no email-sending path and emits recipient attempts only as `SUPPRESSED_DRY_RUN`. Policy table schemas separate public decisions from private recipient attempts, but no writer is shipped and no dry-run result is persisted automatically. Legacy procedures remain unchanged until an explicit operational cutover.

Snowflake primary-key declarations are not treated as enforcement. A future writer must independently recompute deterministic IDs and use transaction plus lifecycle-head compare-and-set controls; those behaviors remain isolated-account test requirements rather than implemented claims.

## Evidence Boundaries

- RSS publication time is provenance only; official observation time comes from the advisory product.
- Rounded Public Advisory mph values are not converted back to knots. Exact wind and movement knots require the matching Forecast Advisory.
- A complete cumulative 144-hour product is not a period-indexed outlook.
- Legacy 50kt fields and visuals remain labeled 50kt unless threshold-specific artifacts are present.
- Forecast-conditioned PiN/CHiN integrate available wind bands and are not attached to a 50kt threshold.
- Rainfall and storm surge remain unavailable until validated upstream producers exist.

## Consequences

- Live RSS access still requires approved deployment networking and monitoring. Exact URL and TLS validation are transport controls, not signed-product authentication.
- Country Office seed rows, the dry-run threat predicate, and Southeast Pacific boundary policy still require stakeholder approval.
- The old send procedures must not be enabled alongside a future delivery procedure.
- `WATCH_SENT_LOG` remains legacy evidence; grouped records are not rewritten as country/recipient lifecycle facts without independent evidence.
- Operational delivery, downgrade, closure, and all-clear remain separate approval gates.

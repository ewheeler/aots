# Repository Map

This is the semantic routing map for the Ahead of the Storm integration workspace. It identifies owning interfaces, implementation seams, focused tests, submodule boundaries, and generated or sensitive outputs. It is not an exhaustive source tree.

Start at the narrowest owner below. Expand through imports and tests only when the documented seam crosses modules.

## Authority Order

Use these sources according to the question being answered:

1. `AGENTS.md` defines repository working rules and required checks.
2. `CONTEXT.md` defines canonical project terminology.
3. `docs/adr/` records durable architecture decisions and their status.
4. `src/aots_portable_reports/`, `tests/aots_portable_reports/`, `pyproject.toml`, and `.github/workflows/ci.yml` establish implemented behavior.
5. `docs/architecture.qmd` explains the current architecture.
6. `plan.md` and `docs/snowflake-agnostic-report-publication.qmd` mix current status with future direction.

Treat target, candidate, and future language in plans as proposed until source and tests implement it.

## Architectural Shape

```text
Pinned source submodules or Snowflake
  -> read-only Known-Good Baseline export
  -> baseline integrity validation
  -> thin existing-report wrapper
  -> Hamilton materialization DAG
  -> report comparison + alert audit + Quarto output
  -> Snapshot Output Bundle
  -> publication manifest and index
```

The root package owns cross-submodule integration. It should remain artifact-oriented rather than becoming a fork of forecast, impact, dashboard, or orchestration logic.

## Root Package Seams

| Path | Responsibility | Focused test |
|---|---|---|
| `src/aots_portable_reports/cli.py` | Public `snapshot`, `export-snowflake`, and `publish` command contracts. | `tests/aots_portable_reports/test_snapshot_cli.py`, `tests/aots_portable_reports/test_export_snowflake_cli.py`, `tests/aots_portable_reports/test_publication.py` |
| `src/aots_portable_reports/models.py` | Baseline, report snapshot, Alert Decision, comparison, and publication Pydantic contracts; planned home of strict ProductFactSet/Profile consumer contracts. | `tests/aots_portable_reports/test_alert_decision_contract.py`, then the nearest consumer test. |
| `src/aots_portable_reports/validation.py` | Baseline manifest, checksum, schema-hash, and row-count integrity. | `tests/aots_portable_reports/test_snapshot_cli.py` |
| `src/aots_portable_reports/export_snowflake.py` | Read-only Snowflake extraction, query filters, artifact layout, and safe output replacement. | `tests/aots_portable_reports/test_export_snowflake_cli.py`, `tests/aots_portable_reports/test_export_snowflake_live_path.py` |
| `src/aots_portable_reports/report_wrapper.py` | Thin adaptation around existing `do_report(...)` behavior and bounded runtime compatibility patches. | `tests/aots_portable_reports/test_report_wrapper.py` |
| `src/aots_portable_reports/dag.py` | Hamilton snapshot dataflow and Snapshot Output Bundle materialization. | `tests/aots_portable_reports/test_snapshot_cli.py` |
| `src/aots_portable_reports/runner.py` | Hamilton driver execution boundary. | `tests/aots_portable_reports/test_snapshot_cli.py` |
| `src/aots_portable_reports/comparison.py` | Report comparison and certification-state semantics. | `tests/aots_portable_reports/test_comparison.py` |
| `src/aots_portable_reports/alert_contract.py` | Alert audit filenames and bundle persistence contracts. | `tests/aots_portable_reports/test_alert_renderer.py` |
| `src/aots_portable_reports/alert_renderer.py` | Structured alert facts, bounded prose, HTML, visual assets, and claim-based parity. | `tests/aots_portable_reports/test_alert_renderer.py` |
| `src/aots_portable_reports/local_adapter.py` | Local Snapshot Output Bundle discovery. | `tests/aots_portable_reports/test_publication.py` |
| `src/aots_portable_reports/publication.py` | Multi-snapshot publication manifest and Quarto index generation. | `tests/aots_portable_reports/test_publication.py` |

`report_wrapper.py` dynamically loads `Ahead-of-the-Storm-DATAPIPELINE/reports.py`. Report calculations remain owned by that submodule; the root wrapper owns adaptation and explicitly named normalization only.

## Submodule Boundaries

| Path | Upstream responsibility |
|---|---|
| `TC-ECMWF-Forecast-Pipeline/` | Forecast ingestion and transformation. |
| `Ahead-of-the-Storm-DATAPIPELINE/` | Impact artifacts and existing report calculations. |
| `Ahead-of-the-Storm/` | Dash and FastAPI presentation. |
| `Ahead-of-the-Storm-ORCHESTRATION/` | Snowflake-native operational orchestration. |

These directories are pinned gitlinks declared in `.gitmodules`. Changes inside them belong to their upstream repositories and require an intentional submodule revision update here. Do not assign the Portable Report Flow to any single submodule.

Current Orchestration alert-policy routes:

| Path | Responsibility | Focused test |
|---|---|---|
| `Ahead-of-the-Storm-ORCHESTRATION/07b_alert_agent/warning_alert_classifier.py` | Side-effect-free country-level Warning/Alert/no-product/manual-review decision core. | `Ahead-of-the-Storm-ORCHESTRATION/tests/test_warning_alert_classifier.py` |
| `Ahead-of-the-Storm-ORCHESTRATION/07b_alert_agent/authoritative_storm_state.py` | Proposed dry-run LACRO basin authority configuration and strict NHC/CPHC advisory normalization. | `Ahead-of-the-Storm-ORCHESTRATION/tests/test_authoritative_storm_state.py` |
| `Ahead-of-the-Storm-ORCHESTRATION/07b_alert_agent/advisory_feed.py` | No-redirect, bounded exact-URL NHC/CPHC RSS retrieval; digest-bound paired advisory parsing; review-event production. | `Ahead-of-the-Storm-ORCHESTRATION/tests/test_advisory_feed.py` |
| `Ahead-of-the-Storm-ORCHESTRATION/07b_alert_agent/storm_identity.py` | Exact or explicitly approved forecast-to-official storm identity reconciliation. | `Ahead-of-the-Storm-ORCHESTRATION/tests/test_storm_identity.py` |
| `Ahead-of-the-Storm-ORCHESTRATION/07b_alert_agent/country_threat.py` | Proposed dry-run Country Office eligibility and complete 144-hour 34kt threat predicate. | `Ahead-of-the-Storm-ORCHESTRATION/tests/test_country_threat.py` |
| `Ahead-of-the-Storm-ORCHESTRATION/07b_alert_agent/policy_engine.py` | Non-sending composition of identity, threat, classifier, lifecycle, delivery attempts, and product facts. | `Ahead-of-the-Storm-ORCHESTRATION/tests/test_policy_engine.py` |
| `Ahead-of-the-Storm-ORCHESTRATION/07b_alert_agent/alert_lifecycle.py` | Country lifecycle transitions and recipient-aware dry-run attempts. | `Ahead-of-the-Storm-ORCHESTRATION/tests/test_alert_lifecycle.py` |
| `Ahead-of-the-Storm-ORCHESTRATION/07b_alert_agent/product_facts.py` | Implemented V1 deterministic Summary/Situation/Forecast assembly; it is not the planned semantic ProductFactSet v2 shape. | `Ahead-of-the-Storm-ORCHESTRATION/tests/test_product_facts.py` |
| `Ahead-of-the-Storm-ORCHESTRATION/04_data/09_alert_policy_tables.sql` | Registry, identity, official state, threat, decision, lifecycle-head, and recipient-delivery schema contracts; no writer is shipped. | `Ahead-of-the-Storm-ORCHESTRATION/tests/test_alert_policy_sql.py` |

These modules are implemented and credential-free. Content-addressed classifier release SQL and read-only policy table schemas are authored and locally tested. No persistence writer is shipped; Snowflake identity-recomputing persistence, compile/deployment smoke coverage, scheduled ingestion, legacy-procedure cutover, actual delivery, and operational approval remain proposed.

Proposed next-stage seam, governed by `docs/adr/0010-separate-semantic-alert-facts-from-presentation.md`:

```text
Orchestration semantic ProductFactSet v2 artifact
  -> root strict artifact validation
  -> root PresentationProfile v1
  -> root CompositionManifest v1
  -> Snapshot Output Bundle publication artifacts
```

The exact Orchestration producer path remains to be selected during the first tracer. Preserve `product_facts.py` V1 and add V2 alongside it rather than rewriting current dry-run fixtures.

## Contracts And Test Routing

- CLI or bundle behavior: start with the command-specific test named above.
- Live exporter query or artifact changes: use the fake query runner in `test_export_snowflake_live_path.py`; tests must not require live credentials.
- Contract-field or artifact-role changes: update `models.py`, producer, consumer, fixture manifests, and the nearest focused tests together.
- Report behavior mismatches: first decide whether ownership is the upstream calculation or root adaptation; do not add new calculations to `report_wrapper.py`.
- DAG dependency or bundle-layout changes: update `dag.py`, snapshot tests, architecture docs, and the generated DAG image together.
- Alert changes: keep structured facts, bounded prose, presentation, visual generation, and persistence as distinct review seams.
- ProductFactSet/Profile changes: update the Orchestration producer or V1 adapter, root contract/validation, artifact-role fixture manifests, compatibility-profile renderer, claim-parity tests, architecture docs, and this map together.
- Certification changes: update comparison tests and architecture documentation or an ADR when trust semantics change.

Run focused tests first:

```bash
uv run pytest tests/aots_portable_reports/<focused-test-file>.py
```

Run `uv run --frozen pre-commit run --all-files` and `uv run --frozen pytest` before handoff when shared behavior changes.

## Durable Inputs And Generated Boundaries

Durable reviewed inputs include source modules, typed contracts, tests, synthetic fixtures, ADRs, Quarto source, `pyproject.toml`, and `uv.lock`.

Generated or reproducible outputs include:

- Snapshot Output Bundle reports, comparisons, alert audit files, `alert-assets/`, Quarto source, and rendered `site/` output.
- Publication manifests, generated indexes, and rendered publication sites.
- `docs/assets/architecture/portable-report-hamilton-dag.png`, generated from `dag.py`.
- `docs/_site/`, `.quarto/`, caches, and temporary output directories.

Comparison screenshots under `docs/assets/comparison-cases/` are deliberately committed review evidence, not calculation authority.

Real `known-good-baselines/`, `.env`, credentials, keys, and certificates are local-only. Real baselines may contain facility-level, beneficiary, geospatial, or operational data. Normal committed baseline data belongs under `tests/fixtures/` and must be synthetic.

`.repo-familiar/bootstrap.yml` records provenance and checksums for Vendored Generated Assets such as `AGENTS.md`, `.agents/`, and selected scaffold files. Project-owned source and this repository map remain the implementation authority.

## Implemented Versus Proposed

Implemented behavior includes the three public commands, integrity validation, the Hamilton snapshot DAG, the thin existing-report wrapper, provisional and certifying comparison states, Alert Decision validation, decision-driven Warning/Alert rendering, non-renderable decision auditing, and publication from Snapshot Output Bundles. Orchestration also contains a credential-free local feed/parser, state normalization, storm identity, country threat, classifier, lifecycle, recipient suppression, and Product Facts composition with focused tests.

Proposed or incomplete architecture includes semantic ProductFactSet v2 and V1 adapter, PresentationProfile/CompositionManifest contracts, forecast-only episode linkage, typed official warning/rain/surge facts, scheduled/monitored authoritative advisory retrieval, Snowflake classifier and persistence deployment, operational lifecycle/delivery, explicit repository/store interfaces, a fully typed Report Contract, complete file/blob adapters, extra-field allowlisting, broad public report publication, and removal of Snowflake coupling from the live dashboard or orchestration stack.

## Change Locality

- Start at the semantic owner above and its focused tests.
- Preserve Snapshot Output Bundles, not raw baselines, as the publication source of truth.
- Keep independent expected output provenance separate from wrapper-generated or seed output.
- Keep secrets out of CLI arguments, logs, fixtures, and committed artifacts.
- Keep `cli.py`, `pyproject.toml`, usage documentation, and command tests aligned when public commands change.
- Update this map in the same change that moves ownership or adds a high-leverage seam.

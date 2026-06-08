# Ahead of the Storm Plan

Generated with repo-familiar.

## Goals

- Define the first useful slice of the project.
- Keep implementation and documentation moving together.
- Record architectural decisions when they are hard to reverse, surprising without context, and the result of real tradeoffs.

## Agent Harnesses

- `opencode`
- `paseo`

## Model Profiles

- `default-coding`

## Tool Profiles

- `cq`
- `a11y-scanner`
- `browser-automation`
- `headroom-context-compression`
- `headroom-mcp`
- `headroom-proxy`
- `opencode-context7-mcp`
- `opencode-cq-mcp`
- `opencode-headroom-mcp`
- `opencode-homebrew-path`
- `opencode-playwright-mcp`

## Memory Profiles

- `memory-local`

## Prompt Profiles

- `prompt-migration-gpt55`
- `prompt-evals-dag`

## Safety Profiles

- `prompt-output-safety`

## Privacy Profiles



## Repo Map Profiles

- `hamilton-dag`

## Sandbox Profiles

- `sandbox-light`

## Secrets Profiles

- `dotenv-local`
- `kvenv-azure-keyvault`

## Design Profiles



## Worktree Profiles

- `parallel-worktrees`

## Skills

- `grill-with-docs`
- `prompt-migration`
- `prompt-eval-design`
- `prompt-output-safety`
- `cq`
- `session-focus`
- `diagnose`
- `security-audit`
- `to-prd`
- `to-issues`
- `a11y-web-scan`
- `caveman`
- `get-api-docs`
- `improve-codebase-architecture`
- `liteparse`
- `tdd`
- `zoom-out`

## First Milestones

- Confirm project goals and non-goals.
- Fill in usage and architecture documentation.
- Implement the smallest end-to-end feature or workflow.

## Snowflake-Agnostic Report Publication Track

### Current Assessment

- Feasible: a Snowflake-agnostic version is practical for report generation and publication first.
- Prudent: keep Snowflake as one optional backend while adding a parallel file/blob-backed path; do not replace the live Snowflake/Dash/orchestration stack in the first slice.
- Best first slice: generate a static report package for one country, one storm, and one forecast run from local/blob artifacts, then publish it as a Quarto site.
- Avoid initially: replacing live Dash callbacks, the tile server, Snowflake tasks/streams, materialized tables, alerts, and Cortex agent workflows.

### Evidence From The Submodules

- `Ahead-of-the-Storm-DATAPIPELINE` already separates artifact storage through `DATA_PIPELINE_DB=LOCAL|BLOB|SNOWFLAKE` and writes report JSON plus impact view files.
- `TC-ECMWF-Forecast-Pipeline` can run with `DATA_PIPELINE_DB=LOCAL`, keeping transformed TC CSVs and wind-envelope CSVs instead of loading Snowflake.
- `Ahead-of-the-Storm` can read preprocessed impact views through the `STAGE` path, but still uses Snowflake for storm discovery, country metadata, thresholds, and some report-map queries.
- `Ahead-of-the-Storm-ORCHESTRATION` is intentionally Snowflake-native: SPCS jobs, streams, tasks, materialized-table refresh, alerts, and Snowflake Intelligence are not good first migration targets.

### Target Shape

- Introduce explicit provider interfaces rather than letting Snowflake utility modules be the implicit system boundary.
- Keep the existing geospatial processing behavior initially; wrap it before rewriting it.
- Use `uv` for the shared Python environment, `pydantic` for typed report/publication artifacts, `hamilton` for a report materialization DAG, and Quarto for static publication.
- Use `polars` selectively for tabular manifest/index work; keep GeoPandas/Shapely/GigaSpatial for geospatial joins until benchmarks justify a deeper rewrite.

### Candidate Interfaces

- `ForecastRepository`: lists storms, forecast times, tracks, envelopes, and wind thresholds.
- `CountryRegistry`: lists active countries, boundaries, zoom settings, and display metadata.
- `ImpactArtifactStore`: reads and writes generated impact view artifacts from local filesystem, blob storage, or Snowflake stage.
- `ReportArtifactStore`: reads and writes typed report inputs, report JSON/YAML, rendered assets, and previous-report snapshots.
- `PublicationStore`: writes Quarto source pages, static site outputs, and a publication manifest.

### First Tracer Bullet

1. Select one known country/storm/forecast tuple that already has Snowflake-backed report outputs.
2. Export or point to equivalent local/blob TC forecast and impact artifacts.
3. Build a file-backed `ForecastRepository` that can provide the envelope and track data needed by the report path.
4. Wrap the existing report-generation function to regenerate the report artifact with minimal behavior drift.
5. Build typed `pydantic` models for the report artifact and publication manifest around observed baseline behavior.
6. Use a Hamilton DAG to materialize report inputs, report JSON, Quarto page source, and the publication manifest.
7. Render a Quarto site and compare the generated report JSON against the Snowflake-backed report for the same tuple.

### Resolved Planning Decisions

- First portable product: one static Report Snapshot for a single country/storm/forecast tuple.
- Next product: generalize to a multi-snapshot publication site only after the artifact model and validation comparison are stable.
- First input baseline: exported known-good Snowflake-backed artifacts.
- Next input adapter: add local TC/impact pipeline outputs only after the Report Snapshot matches the known-good baseline.
- Complete Known-Good Baseline export: include both the final expected report output and the minimum source artifacts needed to regenerate it.
- Implementation location: create the portable Report Snapshot package/workspace at the repository root, not inside any single submodule.
- Candidate implementation path: `src/aots_portable_reports/`, with tests under `tests/aots_portable_reports/`.
- First public command: `uv run aots-report snapshot --baseline <path> --out <path>`.
- First command responsibility: validate a Known-Good Baseline export, regenerate the Report Snapshot artifact, render Quarto source/site output, and write a comparison report against the baseline.
- Include a read-only Snowflake exporter command in the first implementation so users do not need to know how to manually export the Known-Good Baseline.
- Snowflake exporter credentials: support existing `SNOWFLAKE_*` environment variables first, plus optional `--env-file <path>`; do not accept positional secrets or command-line password flags.
- Snowflake exporter overwrite policy: fail if `<baseline>` exists and is non-empty unless `--overwrite` is passed; write to a temporary sibling directory, validate manifest/checksums, then atomically move into place.
- Baseline artifact format policy: use Parquet for tabular/geospatial source artifacts where possible, JSON for manifests/report/comparison outputs, and Markdown only for human-readable summaries.
- Report-generation strategy: wrap the existing report-generation function first, then progressively extract and normalize the typed contract after baseline comparison is stable.
- Wrapper boundary: keep the wrapper thin; it may adapt baseline artifacts into existing function inputs and adapt outputs into `ReportSnapshot`, but it must not add new report calculations.
- Materialization strategy: require Hamilton from the start, but keep the first DAG small and boring.
- Comparison report failures: missing required artifacts, manifest checksum mismatch, schema mismatch, or numeric report fields outside tolerance.
- Comparison report warnings: presentation-only Quarto differences, optional facility layers absent for a country, or extra non-contract fields in source artifacts.
- Numeric comparison tolerance: exact match for integer counts and categorical fields; absolute tolerance of `1e-9` for raw probabilities and `0.01` for rendered percentages.
- Rounding rules: encode display rounding in the Pydantic model or comparison layer, not hidden in Quarto templates.
- Snapshot output layout: create a self-auditing, easy-to-diff output bundle with generated manifest, regenerated snapshot artifact, comparison outputs, Quarto source, and rendered site output.
- Commit policy: do not commit rendered HTML/site outputs; it is fine to commit intermediate JSON/Markdown artifacts and Quarto source when they are useful as fixtures or review artifacts.
- Known-Good Baseline layout: keep `manifest.json` at the baseline root, make artifact paths relative to that root, and group source artifacts under `artifacts/` by role.
- Baseline storage policy: keep real exported Known-Good Baselines outside the repo by default; add a tiny synthetic in-repo fixture later for tests.

### Known-Good Baseline Export Contents

- Current report JSON for the selected country/storm/forecast tuple.
- Admin impact artifacts by wind threshold.
- Tile impact artifacts by wind threshold.
- Facility impact artifacts for schools, health centers, shelters, and WASH where available.
- CCI tile and admin artifacts.
- Track and envelope artifacts.
- Export manifest with country, storm, forecast time, source table/file names, row counts, schema hashes, and checksums.

### Known-Good Baseline Directory Layout

```text
<baseline>/
  manifest.json
  expected-report.json
  artifacts/
    admin/
    tiles/
    facilities/
    cci/
    tracks/
    envelopes/
```

- `manifest.json` is the baseline contract.
- `expected-report.json` is the trusted report output for comparison.
- All artifact paths in `manifest.json` are relative to the baseline root.
- `artifacts/` groups regenerable source artifacts by role so the export is portable, diffable, and straightforward for `aots-report snapshot --baseline <path>` to validate.

Artifact format policy:

- Use Parquet for tabular and geospatial source artifacts where possible.
- Preserve geometry in WKT or WKB columns when GeoParquet compatibility is uncertain.
- Use JSON for `manifest.json`, `expected-report.json`, generated report snapshots, and machine-readable comparison output.
- Use Markdown only for human-readable summaries such as `comparison.md`.
- Keep diffability and auditability in the manifest and comparison files rather than relying on raw Parquet diffs.

Storage policy:

- Keep real exported Known-Good Baselines outside the repository by default, because they may contain large geospatial files or sensitive operational data.
- Use an ignored local directory such as `known-good-baselines/` only for temporary local exports.
- Add a tiny synthetic baseline fixture in-repo later for automated tests, with no real locations or beneficiary-sensitive values.

### First CLI Shape

```bash
uv run aots-report snapshot --baseline <path> --out <path>
```

The command should:

- Validate the Known-Good Baseline export before doing any generation work.
- Regenerate the Report Snapshot artifact from the baseline source artifacts.
- Render Quarto source and static site output for the Report Snapshot.
- Write a comparison report that checks regenerated outputs against the baseline report JSON and manifest metadata.
- Fail clearly when baseline artifacts are missing, schemas do not match, checksums fail, or unsupported fields would otherwise be silently defaulted.

Initial scaffold status:

- `src/aots_portable_reports/` contains the root package scaffold.
- `aots-report snapshot --baseline <path> --out <path>` is wired as the first CLI command.
- `tests/fixtures/synthetic_baseline/` provides a tiny synthetic baseline fixture with a valid Parquet source artifact.
- `tests/aots_portable_reports/test_snapshot_cli.py` covers output bundle creation, rendered Quarto site output, missing artifact, checksum mismatch, manifest schema mismatch, row-count mismatch, and artifact schema-hash mismatch failures.
- `tests/aots_portable_reports/test_comparison.py` covers exact integer/categorical comparison, raw probability tolerance, rendered percentage tolerance, missing fields, and extra fields.
- `src/aots_portable_reports/report_wrapper.py` groups exported artifacts and calls the existing `do_report(...)` path when enough artifacts are present, with a seed fallback for incomplete synthetic fixtures.
- `tests/aots_portable_reports/test_report_wrapper.py` covers the injected `do_report(...)` wrapper path and fallback behavior.
- `tests/fixtures/synthetic_report_baseline/` provides a richer synthetic baseline with admin, tile, facility, CCI, and raw track artifacts.
- The richer fixture verifies wrapper grouping into wind-keyed inputs without committing real locations or beneficiary-sensitive values.

### Autonomous Milestone Sequence

- Milestone 1 complete: committed the scaffold, docs, CI, tests, and tool configuration in `dc40d17`.
- Milestone 2 complete: added a richer committed synthetic fixture that exercises the report wrapper artifact-grouping path without real data.
- Milestone 3 complete: added `--case-name`, `--dry-run`, JSON planning, and clearer export summaries with artifact counts, row counts, and the next snapshot command.
- Milestone 4 complete: report generation now quiets known noisy geodata loggers and patches the loaded report module with a cached country-boundary lookup for landfall calculation.
- Milestone 5 complete: added a local baseline repository adapter and `aots-report publish` command that writes a publication manifest and renders a Quarto index for multiple local baselines.

### Snowflake Baseline Exporter

Include a companion command for creating the Known-Good Baseline export from Snowflake-backed data:

```bash
uv run aots-report export-snowflake \
  --country <iso3> \
  --storm <storm-id> \
  --forecast-time <forecast-time> \
  --out <baseline>
```

The exporter should:

- Be read-only against Snowflake.
- Use existing `SNOWFLAKE_*` environment variables and an optional `--env-file <path>` if needed.
- Avoid positional secrets or command-line password flags because shell history can leak them.
- Print the non-secret Snowflake account, database, schema, and warehouse it will read from before export.
- Ask for confirmation only if it later detects production-like settings.
- Export `expected-report.json`, source artifacts, and root `manifest.json` in the agreed Known-Good Baseline layout.
- Record source tables/files, query filters, row counts, schema hashes, checksums, and export timestamp in `manifest.json`.
- Fail before writing partial outputs if required Snowflake configuration is missing.
- Avoid requiring users to run ad hoc Snowflake SQL manually.
- Refuse to overwrite an existing non-empty baseline directory unless `--overwrite` is passed.
- Write exports to a temporary sibling directory first, validate the generated manifest and checksums, then atomically move the validated export into place.

The exporter exists to improve usability. It should not become the source of truth for the portable flow; `aots-report snapshot --baseline <path> --out <path>` remains the validation and regeneration command.

Initial exporter scaffold status:

- `aots-report export-snowflake ...` is wired as a public command.
- The command supports `SNOWFLAKE_*` environment variables plus `--env-file <path>`.
- The command refuses existing non-empty output directories unless `--overwrite` is passed.
- The command includes `--plan-only` for connection-free configuration previews.
- `--plan-only --json` prints a machine-readable, non-secret artifact plan.
- `--dry-run` is an alias for `--plan-only`.
- `--case-name <name>` writes to `known-good-baselines/<name>` when `--out` is omitted.
- Successful exports print artifact count, row count, and the next `aots-report snapshot` command.
- Live Snowflake extraction is implemented behind read-only scoped queries for source artifacts.
- The exporter writes Parquet source artifacts, `expected-report.json`, and `manifest.json` through a temporary sibling directory before the final move.
- `tests/aots_portable_reports/test_export_snowflake_cli.py` covers missing configuration, overwrite protection, and non-secret config previews.
- `tests/aots_portable_reports/test_export_snowflake_live_path.py` covers live-export behavior with a fake query runner, not live credentials.
- `src/aots_portable_reports/local_adapter.py` discovers valid local baseline directories from a filesystem root.
- `src/aots_portable_reports/publication.py` writes `publication-manifest.json`, Quarto source, and rendered site output for a multi-snapshot index.
- `tests/aots_portable_reports/test_publication.py` covers local baseline discovery and `aots-report publish` output.

Current live-baseline status:

- A real Known-Good Baseline was created locally at `known-good-baselines/melissa-jam`; this directory is ignored and should not be committed.
- The Melissa/JAM baseline snapshot comparison passes with `comparison.json` status `passed`.
- The exporter uses compact `FORECAST_DATE` values for impact MAT tables and timestamp `FORECAST_TIME` values for track/envelope tables.
- The exporter writes a generated `expected-report.json` through the existing `do_report(...)` path when enough artifacts are present.
- The snapshot command normalizes volatile `report_date` to the baseline value before comparison.
- The report wrapper caches country-boundary lookups in-process and quiets `AdminBoundaries`/`EntityManager` logs to reduce repeated GADM/GigaSpatial noise.

Exported Snowflake source artifact groups:

- `ADMIN_ALL_IMPACT_MAT` to `artifacts/admin/admin_<wind>.parquet`.
- `MERCATOR_TILE_IMPACT_MAT` to `artifacts/tiles/tiles_<wind>.parquet`.
- `SCHOOL_IMPACT_MAT`, `HC_IMPACT_MAT`, `SHELTER_IMPACT_MAT`, and `WASH_IMPACT_MAT` to `artifacts/facilities/`.
- `MERCATOR_TILE_CCI_MAT` and `ADMIN_ALL_CCI_MAT` to `artifacts/cci/`.
- `TRACK_MAT` to `artifacts/tracks/tracks_<wind>.parquet`.
- `TC_TRACKS` to `artifacts/tracks/raw_tracks.parquet` for landfall calculation.
- `TC_ENVELOPES_COMBINED` to `artifacts/envelopes/envelopes.parquet` with WKT geometry.

### Report-Generation Wrapper Boundary

- Keep the existing report-generation wrapper thin.
- The wrapper may adapt baseline artifacts into the current function's expected inputs.
- The wrapper may adapt the current function's output into `ReportSnapshot`.
- The wrapper must not add new report calculations.
- New calculations belong upstream in artifact generation or downstream in a clearly named normalization/comparison step.

### Hamilton Materialization Flow

Use Hamilton from the start for the snapshot materialization flow, but keep the DAG small and explicit:

```text
baseline validation
  -> source artifact loading
  -> report wrapper
  -> ReportSnapshot model
  -> comparison
  -> Quarto source
```

This makes dependencies explicit and matches the target stack without over-engineering the first Report Snapshot slice.

### Comparison Report Semantics

Failure conditions:

- Missing required artifacts.
- Manifest checksum mismatch.
- Schema mismatch.
- Numeric report fields outside tolerance.

Numeric tolerance policy:

- Integer counts and categorical fields must match exactly.
- Raw probabilities use absolute tolerance `1e-9`.
- Rendered percentages use absolute tolerance `0.01`.
- Report display rounding must be represented in the Pydantic model or comparison layer, not in Quarto-only presentation logic.

Warning conditions:

- Presentation-only Quarto differences.
- Optional facility layers absent for a country.
- Extra non-contract fields in source artifacts.

### Snapshot Output Layout

`aots-report snapshot --out <path>` should create:

```text
<out>/
  manifest.json
  report-snapshot.json
  comparison.json
  comparison.md
  quarto/
    index.qmd
    _quarto.yml
  site/
```

- `manifest.json` records generated snapshot metadata.
- `report-snapshot.json` is the regenerated typed artifact.
- `comparison.json` and `comparison.md` explain pass/fail status and warnings.
- `quarto/` contains source files used to render the snapshot.
- `site/` contains rendered output.

Commit policy:

- Commit intermediate JSON and Markdown artifacts when they are useful as golden fixtures or review artifacts.
- Commit Quarto source when it is part of a reproducible fixture or example.
- Do not commit rendered HTML files or `site/` outputs by default; regenerate them in CI or publication workflows.

### Risks And Open Questions

- Local TC forecast outputs are not yet a complete drop-in replacement for Snowflake tables; they need normalized schemas and a forecast manifest.
- Snowflake currently provides operational state: dedupe logs, completion signals, materialized-table refresh, and alert/email state.
- Some code paths still hard-code Snowflake, especially report-map image generation and dashboard metadata discovery.
- Performance must be measured before replacing materialized tables or geospatial joins with file-backed processing.
- The first Report Snapshot still needs exact export filters and naming conventions for each baseline artifact.

### Recommended Non-Goals For The First Slice

- Do not remove Snowflake dependencies from the live Dash app.
- Do not replace Snowflake orchestration, streams, tasks, alerts, or Cortex agent procedures.
- Do not rewrite the geospatial impact engine in Polars before proving the file-backed report path.
- Do not change production credentials, deployment settings, or data-sharing contracts.
- Do not begin by modifying one submodule as if it owns the whole portable report flow; the first slice crosses forecast, impact, report, and publication boundaries.

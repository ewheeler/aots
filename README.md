# Ahead of the Storm Workspace

This repository is the integration workspace for the Ahead of the Storm tropical cyclone impact-reporting system. It brings together the application, data pipeline, forecast pipeline, and orchestration repositories as submodules, and adds a root Python package for portable report and alert generation.

The current focus is to make impact reports and alert emails reproducible from portable artifacts instead of requiring live Snowflake access at publication time. Snowflake remains a supported source system, but generated Snapshot Output Bundles are the intended handoff format for audit, comparison, browser review, and future publication.

## Intentions

- Reproduce one country/storm/forecast report from a Known-Good Baseline of exported source artifacts.
- Distinguish baseline integrity from certification: a passing comparison is certifying only when the expected output came from an independent trusted current artifact.
- Publish from Snapshot Output Bundles, not from raw baseline directories.
- Replace the current Snowflake alert-agent email path over time with a portable hybrid Alert Renderer.
- Keep deterministic facts, tables, caveats, provenance labels, and visual assets outside unrestricted LLM output.
- Allow future LLM use through bounded Alert Prose Provider slots rather than whole-email generation.
- Keep real baselines local and ignored; committed fixtures are synthetic only.

## Current Progress

Implemented in the root `aots_portable_reports` package:

- `aots-report snapshot` validates a baseline, regenerates a report snapshot, compares it with expected output, and renders a Quarto audit site.
- `aots-report export-snowflake` performs read-only Snowflake exports into local Known-Good Baseline directories.
- `aots-report publish` builds a publication index from Snapshot Output Bundles.
- Certifying comparison support is in place for independent expected report JSON.
- Previous-report artifacts and vulnerability artifacts support change-from-previous and people-in-need fields.
- Alert-agent email export is supported through `ALERT_SENT_LOG.EMAIL_BODY` as `expected-alert.html`.
- Local alert generation emits `rendered-alert.html`, `alert-context.json`, `alert-claims.json`, and `alert-comparison.json`.
- Alert visual assets are generated as PNG files under `alert-assets/` and embedded inline in `rendered-alert.html` for email portability.
- Synthetic fixtures cover smoke snapshots, report-wrapper paths, alert-present/alert-missing/sparse cases, and visual alert assets.

Verified milestones so far:

- Melissa/Jamaica report reproduction reaches `certifying_comparison` when the baseline uses an independent current report, previous report, and vulnerability artifacts.
- Melissa/Jamaica alert-agent email can be exported from Snowflake and browser-reviewed as an independent expected artifact.
- Local alert HTML renders with structured claims, provenance labels, caveats, tables, and generated PNG visual sections without requiring exact prose or pixel parity.
- Real JAM/CUB/PHL comparison cases are documented in `docs/comparison-cases.qmd`, including committed Playwright screenshots for JAM and CUB expected-vs-rendered alert emails.

## Repository Layout

```text
.
├── src/aots_portable_reports/        # Root portable report/alert package
├── tests/aots_portable_reports/      # Package tests
├── tests/fixtures/                   # Synthetic committed baselines only
├── docs/                             # Quarto project docs
├── docs/adr/                         # Architecture decision records
├── CONTEXT.md                        # Project glossary and domain language
├── plan.md                           # Current implementation plan/status notes
├── Ahead-of-the-Storm/               # Application submodule
├── Ahead-of-the-Storm-DATAPIPELINE/  # Data pipeline submodule
├── Ahead-of-the-Storm-ORCHESTRATION/ # Snowflake/orchestration submodule
└── TC-ECMWF-Forecast-Pipeline/       # Forecast pipeline submodule
```

`known-good-baselines/` is intentionally ignored. Use it for real local exports, but do not commit it.

## Prerequisites

- Python 3.11
- `uv`
- Quarto on `PATH`
- Snowflake credentials only for real `export-snowflake` runs

Install the Python environment:

```bash
uv sync --dev
```

Initialize or update submodules:

```bash
git submodule update --init --recursive
```

Render project docs:

```bash
quarto render docs
```

Run tests:

```bash
uv run pytest
```

## Snapshot Workflow

Run a smoke snapshot from the tiny synthetic fixture:

```bash
uv run aots-report snapshot \
  --baseline tests/fixtures/synthetic_baseline \
  --out /tmp/aots-report-smoke
```

Run a richer alert snapshot with synthetic visual assets:

```bash
uv run aots-report snapshot \
  --baseline tests/fixtures/synthetic_alert_present_baseline \
  --out /tmp/aots-alert-smoke
```

Important output files:

- `manifest.json`: generated snapshot metadata and relative artifact paths.
- `report-snapshot.json`: regenerated report payload.
- `comparison.json` / `comparison.md`: report comparison status.
- `expected-alert.html`: independent Snowflake alert email when exported.
- `rendered-alert.html`: local portable alert email artifact.
- `alert-context.json`: structured alert inputs.
- `alert-claims.json`: normalized factual claims.
- `alert-comparison.json`: claim/DOM-present alert parity results.
- `alert-assets/*.png`: generated visual assets for audit/debug; also embedded inline in `rendered-alert.html`.
- `quarto/` and `site/`: audit-site source and rendered output.

Read `comparison.json` before trusting output. A report comparison is certifying only when:

```json
{
  "status": "passed",
  "certification_state": "certifying_comparison",
  "certifying": true
}
```

Alert parity is intentionally not byte-for-byte HTML, exact prose, or pixel parity. It fails on significant factual differences or omissions, including missing required visual sections when source data exists.

## Snowflake Export Workflow

Preview a read-only export plan without connecting:

```bash
uv run aots-report export-snowflake \
  --country JAM \
  --storm MELISSA \
  --forecast-time '2025-10-28 00:00:00' \
  --case-name melissa-jam \
  --env-file .env \
  --dry-run \
  --json
```

Run a real local export:

```bash
uv run aots-report export-snowflake \
  --country JAM \
  --storm MELISSA \
  --forecast-time '2025-10-28 00:00:00' \
  --case-name melissa-jam \
  --env-file .env \
  --overwrite
```

Include the Snowflake alert-agent email HTML when a matching alert exists:

```bash
uv run aots-report export-snowflake \
  --country JAM \
  --storm MELISSA \
  --forecast-time '2025-10-28 00:00:00' \
  --case-name melissa-jam \
  --env-file .env \
  --include-alert-html \
  --overwrite
```

Credentials come from `SNOWFLAKE_*` environment variables or `--env-file`; never pass passwords as positional CLI arguments.

Exported artifact groups include impact MAT tables, facility impact tables, CCI artifacts, vulnerability artifacts, tracks, envelopes, admin geometry, and alert visualization aggregates. See `docs/usage.qmd` and `docs/snowflake-agnostic-report-publication.qmd` for details.

## Publication Workflow

Generate one or more Snapshot Output Bundles:

```bash
uv run aots-report snapshot \
  --baseline known-good-baselines/melissa-jam \
  --out /tmp/aots-snapshots/melissa-jam
```

Publish an index over those bundles:

```bash
uv run aots-report publish \
  --snapshots-dir /tmp/aots-snapshots \
  --out /tmp/aots-publication
```

`publish` consumes Snapshot Output Bundles, not raw baselines.

## Development Checks

Before handing off changes, run:

```bash
uv run pytest
quarto render docs
```

For alert or HTML changes, also load generated HTML in a real browser or Playwright when practical. Check visible headings, semantic sections, table/image presence, alt text, captions, and console errors. A missing `favicon.ico` in local preview is currently an acceptable warning.

## Safety and Data Handling

- Do not commit real baselines, `/tmp` outputs, screenshots, Playwright scratch directories, `.env` files, or credentials unless there is an explicit data-sharing decision. The JAM/CUB comparison screenshots in `docs/assets/comparison-cases/` are an approved exception.
- Real baseline exports may contain operationally sensitive facility or beneficiary-related data.
- Synthetic fixtures under `tests/fixtures/` are safe to commit and should be used for regression tests.
- Treat accessibility, privacy, dignity, and public-interest review as part of publication readiness, not polish.

## More Documentation

- `docs/usage.qmd`: command walkthroughs and troubleshooting.
- `docs/snowflake-agnostic-report-publication.qmd`: architecture and current status.
- `docs/comparison-cases.qmd`: real comparison case summaries and expected-vs-rendered alert screenshots.
- `docs/alert-email-design.qmd`: target section order, visual hierarchy, and intentional design differences for portable alert emails.
- `docs/architecture.qmd`: repository architecture notes.
- `docs/adr/`: accepted architecture decisions.
- `CONTEXT.md`: glossary for project terminology.
- `plan.md`: implementation history, current status, and open follow-ups.

# Ahead of the Storm

Generated with repo-familiar.

This repository was generated with `repo-familiar`.

## Generated Assets

- `AGENTS.md` contains agent-facing repository instructions.
- `.agents/models.yml` contains selected non-secret model/provider profiles.
- `.agents/tools.yml` contains selected non-secret tool setup guidance.
- `.agents/memory.yml` contains selected memory guidance.
- `.agents/prompts.yml` contains selected prompt migration and evaluation guidance.
- `.agents/safety.yml` contains selected prompt/output safety guidance.
- `.agents/privacy.yml` contains selected data and privacy review guidance.
- `.agents/public-interest.yml` contains selected public-interest digital guidance.
- `.agents/repomap.yml` contains selected codebase graph guidance.
- `.agents/sandbox.yml` contains selected sandbox guidance.
- `.agents/secrets.yml` contains selected local environment and secret-loading guidance.
- `.agents/design.yml` contains selected design guidance.
- `.agents/worktrees.yml` contains selected worktree guidance.
- `.agents/skills/` contains selected vendored skills.
- `docs/` contains the Quarto documentation scaffold.
- `plan.md` records initial goals, milestones, and open questions.
- `.repo-familiar/bootstrap.yml` records generation provenance.

## Documentation

Render docs with:

```bash
quarto render docs
```

If `quarto` is installed outside your shell `PATH` on macOS, try `/usr/local/bin/quarto render docs`.

## Portable Report Snapshots

The root package provides a Snowflake-agnostic report snapshot flow for one country/storm/forecast tuple.

Generate and compare a smoke snapshot from the tiny fixture:

```bash
uv run aots-report snapshot \
  --baseline tests/fixtures/synthetic_baseline \
  --out /tmp/aots-report-snapshot
```

This fixture proves command wiring and output-bundle layout, not independent report reproduction. A Snapshot Output Bundle contains `manifest.json`, `report-snapshot.json`, `comparison.json`, `comparison.md`, Quarto source under `quarto/`, and rendered site output under `site/`.

Generate a real local Snapshot Output Bundle after exporting a baseline:

```bash
uv run aots-report snapshot \
  --baseline known-good-baselines/<case-name> \
  --out /tmp/aots-snapshots/<case-name>
```

Check `comparison.json`. A passing comparison is certifying only when `certifying` is `true` and `certification_state` is `certifying_comparison`.

Publish a simple index from local Snapshot Output Bundles:

```bash
uv run aots-report publish \
  --snapshots-dir /tmp/aots-snapshots \
  --out /tmp/aots-report-publication
```

Preview a read-only Snowflake baseline export plan without connecting or writing files:

```bash
uv run aots-report export-snowflake \
  --country TST \
  --storm ALPHA \
  --forecast-time 2026-01-01T00:00:00Z \
  --case-name alpha-tst \
  --env-file .env.snowflake \
  --wind-threshold 34 \
  --dry-run \
  --json
```

For a real export, provide `SNOWFLAKE_*` environment variables or `--env-file <path>`. Do not pass passwords on the command line. Real Known-Good Baseline exports should stay outside the repo; `known-good-baselines/` is the ignored local baseline root. Use `--case-name <name>` to write to `known-good-baselines/<name>` or pass `--out <path>` explicitly. Add `--include-alert-html` to export the independent Snowflake alert-agent email from `ALERT_SENT_LOG.EMAIL_BODY` as `expected-alert.html`; snapshots keep that file separate from the local `rendered-alert.html` artifact, the JSON alert audit bundle (`alert-context.json`, `alert-claims.json`, `alert-comparison.json`), and generated `alert-assets/*.png` when visual source data is available.

See `docs/usage.qmd` for setup, fixture meanings, certification states, and troubleshooting.

## Development Checks

```bash
uv run pytest
quarto render docs
```

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



## Public Interest Profiles



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

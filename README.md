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

Generate and compare a snapshot from a Known-Good Baseline export:

```bash
uv run aots-report snapshot \
  --baseline tests/fixtures/synthetic_baseline \
  --out /tmp/aots-report-snapshot
```

The output bundle contains `manifest.json`, `report-snapshot.json`, `comparison.json`, `comparison.md`, Quarto source under `quarto/`, and rendered site output under `site/`.

Publish a simple index from local baseline directories:

```bash
uv run aots-report publish \
  --snapshots-dir known-good-baselines \
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

For a real export, provide `SNOWFLAKE_*` environment variables or `--env-file <path>`. Do not pass passwords on the command line. Real Known-Good Baseline exports should stay outside the repo; `known-good-baselines/` is ignored. Use `--case-name <name>` to write to `known-good-baselines/<name>` or pass `--out <path>` explicitly.

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

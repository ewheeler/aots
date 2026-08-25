# Ahead of the Storm Agent Instructions

This integration workspace was bootstrapped with `repo-familiar`.

## Working Defaults

- Treat documentation as part of the implementation.
- Preserve the canonical project language and evidence boundaries in `CONTEXT.md`.
- Keep agent runtime configuration in `.agents/` and generator provenance in `.repo-familiar/bootstrap.yml`.
- Keep fixes narrow and prefer built-in, well-supported framework or library features.
- Use red/green TDD for behavior changes when practical and add a regression test for user-reported bugs.

## Repository Routing

- Read `docs/agents/repository-map.md` before broad code search or architectural work.
- Use `CONTEXT.md` for terminology, `docs/adr/` for durable decisions, `docs/explanation/architecture.qmd` for current architecture, `docs/project/status.qmd` for current status, and `plan.md` for open work.
- Route changes through the owning root-package module, adjacent contracts or configuration, and nearest focused tests before widening the search.
- Treat the four submodule directories as pinned upstream repositories, not root-package implementation authority.
- Treat Snapshot Output Bundles, rendered sites, generated images, real baselines, and caches according to the durable/generated boundaries in the repository map.
- Update the repository map when ownership moves or a high-leverage seam is added.

## Change-Type Checks

| Change type | Required checks |
|---|---|
| Behavior change or bug fix | Run the nearest focused test first; add a regression for reported bugs; run `uv run --frozen pytest` when shared behavior changes. |
| Baseline contract, validation, checksum, schema, or artifact-role change | Update the producer, consumer, fixture manifest, and focused snapshot tests together. |
| Snowflake export query, filter, artifact layout, or write-safety change | Keep exports read-only; run both exporter test files; never require live credentials in tests. |
| Existing report integration change | Keep `report_wrapper.py` limited to adaptation and explicit normalization; put report calculations in their owning upstream repository. |
| Hamilton DAG dependency or Snapshot Output Bundle change | Update DAG tests and architecture docs; regenerate the DAG image when graph structure changes. |
| Comparison or certification change | Preserve independent expected-output provenance; update comparison tests and document trust-semantics changes. |
| Alert facts, prose, HTML, visual assets, or parity change | Keep deterministic facts separate from bounded prose; distinguish Alert Presentation Self-Check from independently sourced Alert Parity; run alert renderer tests and snapshot integration coverage. |
| Visible report, alert, or documentation change | Follow the contributor check matrix in `docs/contributor/documentation-guide.qmd`. |
| Python source, tests, or scripts | Run `uv run --frozen pre-commit run --all-files`; expand the Ruff and mypy ratchet rather than weakening it. |
| Third-party API, SDK, or library integration | Use `get-api-docs` before implementation and keep credentials in the environment. |

## Portable Report Invariants

- Publish from Snapshot Output Bundles, not raw Known-Good Baselines.
- Do not treat baseline integrity as certification. A Certifying Comparison requires independent trusted-current expected output.
- Keep wrapper-generated, seed, unknown-provenance, and independent expected outputs distinct.
- Keep deterministic alert facts, tables, caveats, provenance labels, layout, and visual assets outside unrestricted LLM output.
- Keep the root package artifact-oriented; do not move forecast, impact, dashboard, or orchestration ownership into it by convenience.

## Data And Public-Interest Defaults

- Real baselines may contain facility-level, beneficiary, geospatial, or operational data; keep them local and ignored.
- Commit synthetic fixtures only unless an explicit data-sharing decision documents an exception.
- Never put Snowflake passwords or other secrets in CLI arguments, logs, fixtures, screenshots, or committed configuration.
- Treat privacy, dignity, accessibility, inclusion, and maintainability as publication requirements, not polish.
- Use browser automation for visible output, but treat automated accessibility scans as a baseline rather than proof.

## Documentation Defaults

- Follow `docs/contributor/documentation-guide.qmd` for page purpose, canonical ownership, front matter, navigation, legacy URLs, and contributor checks.

## Agent Skills And Guardrails

- Before implementation or retrying an unexpected error, load the vendored `cq` skill and query the knowledge commons.
- Use relevant workflows from `.agents/skills/` rather than recreating them.
- Use `repository-map` when semantic ownership or focused-test routing changes.
- Use `privacy-review` before broadening publication or handling real baseline artifacts.
- Before task completion, run `uv run --frozen pre-commit run --all-files` and fix reported issues.

## Agent Harnesses

- `opencode`
- `paseo`

## Model Profiles

Selected model profiles are defined in `.agents/models.yml`:

- `default-coding`

## Tool Profiles

Selected non-secret tool guidance is defined in `.agents/tools.yml`:

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
- `python-guardrails`

## Memory And Prompt Profiles

Selected guidance is defined in `.agents/memory.yml` and `.agents/prompts.yml`:

- `memory-local`
- `prompt-migration-gpt55`
- `prompt-evals-dag`

## Safety And Privacy Profiles

Selected guidance is defined in `.agents/safety.yml` and `.agents/privacy.yml`:

- `prompt-output-safety`
- `data-privacy-review`

## Repository Map Profiles

Selected guidance is defined in `.agents/repomap.yml`:

- `hamilton-dag`
- `semantic-routing-map`

## Sandbox, Secrets, And Worktree Profiles

Selected guidance is defined in `.agents/sandbox.yml`, `.agents/secrets.yml`, and `.agents/worktrees.yml`:

- `sandbox-light`
- `dotenv-local`
- `kvenv-azure-keyvault`
- `parallel-worktrees`

## Skills

Selected skills are vendored under `.agents/skills/`:

- `cq`
- `session-focus`
- `grill-with-docs`
- `get-api-docs`
- `diagnose`
- `tdd`
- `security-audit`
- `improve-codebase-architecture`
- `repository-map`
- `setup-python-guardrails`
- `playwright-cli`
- `a11y-web-scan`
- `privacy-review`
- `prompt-migration`
- `prompt-eval-design`
- `prompt-output-safety`
- `liteparse`
- `to-prd`
- `to-issues`
- `zoom-out`
- `caveman`

Skill source provenance is recorded in `.agents/skill-sources.yml`.

# Ahead of the Storm Agent Instructions

This repository was generated with `repo-familiar`.

## Working Defaults

- Treat documentation as part of the implementation.
- Preserve project-specific terminology in `CONTEXT.md` when present.
- Keep agent runtime configuration in `.agents/`.
- Keep generator provenance in `.repo-familiar/bootstrap.yml`.

## Engineering Defaults

- Use red/green TDD for behavior changes whenever practical.
- For user-reported bugs, add or update a regression test that would have caught the issue.
- Prefer focused tests first, then run the project's documented test command before handoff when shared behavior changes.
- Keep fixes narrow and preserve existing content/workflows unless the task explicitly asks for broader refactoring.
- Prefer built-in, well-supported framework/library features before custom implementations.
- For site, layout, navigation, or browser-sensitive changes, verify behavior in a real browser flow when browser tooling is available.
- Browser checks should assert visible behavior when relevant: layout, viewport position, scrolling, interactability, and geometry, not only DOM presence.
- For layout-sensitive work, check more than one viewport width when practical.
- Ensure web markup and rendered content are accessible to screen readers and keyboard users: semantic structure, headings, landmarks, labels, alt text, focus order, and visible focus states matter.
- Anchor web and learning-facing experiences in Universal Design for Learning (UDL): provide multiple ways to perceive information, navigate/interact, and understand or act on content.
- Treat automated accessibility scans as a baseline, not proof of accessibility; pair them with manual review of keyboard flow, screen reader semantics, contrast, zoom/reflow, and error messaging.
- Design layouts and UI primitives with future internationalization in mind, including right-to-left language support: prefer logical CSS properties, avoid hard-coded left/right assumptions, and keep text expansion in mind.

## Public Interest Digital Defaults

- Treat safety, dignity, privacy, accessibility, inclusion, and maintainability as product requirements, not optional review passes.
- Prefer data minimization, transparent user-facing behavior, and clear human escalation or correction paths when decisions affect people.
- Design for constrained environments: low connectivity, low-end devices, shared devices, varied literacy, multiple languages, assistive technology, and intermittent access.
- Avoid dark patterns, manipulative engagement mechanics, unnecessary profiling, and surveillance-like defaults.
- Prefer boring, well-supported technology and document operational assumptions so partners or local teams can inherit the system.

## Agent Harnesses

- `opencode`
- `paseo`

## Model Profiles

Selected model profiles are defined in `.agents/models.yml`:

- `default-coding`

## Tool Profiles

Selected non-secret tool setup guidance is defined in `.agents/tools.yml`:

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

Selected memory guidance is defined in `.agents/memory.yml`:

- `memory-local`

## Prompt Profiles

Selected prompt migration and evaluation guidance is defined in `.agents/prompts.yml`:

- `prompt-migration-gpt55`
- `prompt-evals-dag`

## Safety Profiles

Selected prompt/output safety guidance is defined in `.agents/safety.yml`:

- `prompt-output-safety`

## Privacy Profiles

Selected data and privacy review guidance is defined in `.agents/privacy.yml`:



## Repo Map Profiles

Selected repository map and codebase graph guidance is defined in `.agents/repomap.yml`:

- `hamilton-dag`

## Sandbox Profiles

Selected sandbox guidance is defined in `.agents/sandbox.yml`:

- `sandbox-light`

## Secrets Profiles

Selected local environment and secret-loading guidance is defined in `.agents/secrets.yml`:

- `dotenv-local`
- `kvenv-azure-keyvault`

## Design Profiles

Selected design guidance is defined in `.agents/design.yml`:



## Worktree Profiles

Selected worktree guidance is defined in `.agents/worktrees.yml`:

- `parallel-worktrees`

## Public Interest Profiles

Selected public-interest digital guidance is defined in `.agents/public-interest.yml`:



## Skills

Selected skills are vendored under `.agents/skills/`:

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

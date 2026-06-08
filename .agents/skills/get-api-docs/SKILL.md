---
name: get-api-docs
description: Fetch current third-party API, SDK, and library documentation before writing integration code.
---

# Get API Docs

Use this skill when a task depends on current third-party API, SDK, or library behavior.

## Workflow

1. Run `chub --help` and follow its current instructions.
2. Search for the relevant documentation with `chub search "<keywords>" --json`.
3. Fetch the best matching documentation with `chub get <id> --lang py` or the relevant language.
4. Use the fetched docs instead of relying on memorized API shapes.
5. If `chub` is unavailable, record the blocker and use the most direct official documentation source available.

## Rules

- Prefer current docs over training-data memory.
- Include the documentation source in implementation notes when it affects a decision.
- Do not put secrets, private architecture details, or proprietary source code in `chub annotate` or feedback.
- Keep annotations concise, generalizable, and actionable.

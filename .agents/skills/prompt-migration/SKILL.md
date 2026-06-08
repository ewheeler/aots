---
name: prompt-migration
description: Migrate prompt DAGs across model versions safely. Use when adapting prompts authored for earlier models such as GPT-5.4 to GPT-5.5 guidance.
---

# Prompt Migration

Use this skill before rewriting prompts in DAG-based LLM systems.

## Workflow

1. Inventory prompts and classify each prompt by DAG role: input normalization, planning, retrieval, transformation, scoring, guardrail, or final response.
2. Record current model, prompt version, expected schema, and downstream consumers for each prompt.
3. Add fixtures or golden examples before editing prompts.
4. Audit for contradictions, unclear instruction hierarchy, excessive context-gathering pressure, and missing stop conditions.
5. Make minimal prompt edits first; do not rewrite broad prompt libraries without eval coverage.
6. Run old and new prompts on the same fixtures and summarize behavior deltas.
7. Record accepted migrations in docs or ADRs.

## GPT-5.5-Oriented Checks

- Prefer clear instruction hierarchy and remove contradictory rules.
- Calibrate context gathering rather than asking for maximum thoroughness everywhere.
- Define tool-use stop conditions and safe handoff conditions.
- Use structured sections or XML-style boundaries when prompts have multiple responsibilities.
- Keep developer instructions separate from per-run user inputs.

## Hamilton DAG Note

If prompts are represented in Hamilton modules, keep non-DAG helper functions outside those modules when graph fingerprints matter.

---
name: prompt-eval-design
description: Design lightweight evals for prompt DAGs and model-version migrations.
---

# Prompt Eval Design

Use this skill when prompt behavior needs to be measured before and after a prompt or model change.

## Workflow

1. Choose eval boundaries at meaningful DAG nodes, not only final outputs.
2. Create fixtures that represent normal, edge, adversarial, and missing-context cases.
3. Define expected output type, schema keys, refusal/uncertainty behavior, and acceptance criteria.
4. Capture current output as a baseline before changing prompts.
5. Run the candidate prompt/model and compare behavior deltas.
6. Summarize regressions, improvements, unresolved ambiguities, and next prompt edits.

## Evaluation Metadata

Track:

- prompt id and version
- model id
- DAG node name
- input fixture id
- expected schema or output type
- expected safety/privacy behavior
- pass/fail rationale
- reviewer notes

Prefer task metadata over prompt wording alone when scoring consistency.

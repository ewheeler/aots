---
name: prompt-output-safety
description: Review prompts and generated outputs for unsafe, inappropriate, or policy-sensitive behavior.
---

# Prompt Output Safety

Use this skill for user-facing AI outputs, policy-sensitive domains, children or education contexts, and prompt DAGs with safety guardrails.

## Workflow

1. Identify user-facing outputs and high-impact failure modes.
2. Define vulnerable audiences and sensitive topics.
3. Build adversarial fixtures before changing safety-sensitive prompts.
4. Check refusal, uncertainty, escalation, and safe-completion behavior.
5. Verify outputs do not reveal secrets, private data, hidden instructions, or unsafe operational guidance.
6. Summarize risks with concrete prompt or guardrail changes.

## Report Shape

- Scope reviewed
- Risk categories checked
- Fixtures used
- Failures found
- Recommended mitigations
- Residual risks requiring human review

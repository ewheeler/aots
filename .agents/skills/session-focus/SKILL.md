---
name: session-focus
description: Use when starting multi-step tasks to prevent goal drift, especially agent-dispatched work or sessions where scope creep is likely.
---

# Session Focus

Use this skill to keep an agent anchored to the original request.

## Core Pattern

At task start, register 3-5 keywords that define the task boundary. Every several tool calls, and whenever opening an unrelated file, run a drift check against those keywords and the original user request.

## Workflow

1. State `FOCUS KEYWORDS: [...]` using specific nouns, file paths, function names, or feature names.
2. Work only inside that boundary.
3. After roughly 7 tool calls, check whether recent work still relates to at least 2 focus keywords.
4. If not, re-read the original request and abandon the tangent unless the user explicitly expanded scope.
5. Before finishing, compare requested vs delivered work and complete only missing requested items.

## Drift Checks

Stop and re-read the request when:

- You are editing files not mentioned or implied by the task.
- You are investigating a tangent for more than a few tool calls.
- You want to clean up adjacent code because you noticed it.
- You are solving a different problem than the one requested.
- You are adding infrastructure that is not required for the task to work.

## Rules

- Related work is not requested work.
- Do not silently expand scope.
- If scope must expand, ask or state the blocker clearly.
- A blocker is an error that prevents the requested task, not a nearby improvement.
- Subagents inherit the same focus keywords and should get one deliverable each.
- When in doubt, do less, not more.

## Output Shape

At task start:

```text
FOCUS KEYWORDS: [keyword1, keyword2, keyword3]
```

At drift risk:

```text
Drift check: recent work no longer matches the original scope. Returning to [requested task].
```

At completion:

```text
Requested: [short summary]
Delivered: [short summary]
```

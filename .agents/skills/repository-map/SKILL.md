---
name: repository-map
description: Create or refresh a selective semantic repository routing map. Use when architecture work needs reliable ownership and test entry points, or when module seams have changed.
---

# Repository Map

Create or update `docs/agents/repository-map.md` as project-owned navigation, not a generated source tree.

## Workflow

1. Read repository-level agent instructions, product and plan documents, domain context, ADRs, and existing architecture docs. Resolve their authority order before mapping code.
2. Inspect top-level packages, entry points, imports, configuration, schemas, tests, and generated-output boundaries. Identify where each important behavior is owned.
3. Write the narrowest useful routes: owning interface, implementation seam, adapter, adjacent configuration, and nearest focused test.
4. Distinguish implemented behavior from accepted or proposed architecture. Never infer implementation from plans or ADRs alone.
5. Link the map from repository-level agent instructions and the documentation index when those entry points exist.
6. Validate every concrete path in the map. Remove stale routes or mark future paths as proposed.

## Required Sections

- Authority order
- Architectural shape
- Top-level modules or product seams
- Contracts, configuration, and test routing
- Durable inputs and generated boundaries
- Implemented versus proposed architecture when plans extend beyond code
- Change locality and maintenance policy

Omit a section only when it has no meaningful content.

## Rules

- Map semantic ownership, not every file.
- Prefer package-level routes plus high-leverage interfaces over node or helper inventories.
- Follow imports and tests when a documented seam crosses packages.
- Keep generated artifacts out of implementation authority.
- Update the map in the same change that moves ownership or adds a high-leverage seam.

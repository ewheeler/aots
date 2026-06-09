# Publication Source Of Truth

The publication path will use Snapshot Output Bundles as the source of truth, not raw Known-Good Baseline directories. Baselines are source/reference inputs. Snapshot Output Bundles contain regenerated report artifacts, comparison outputs, Quarto source, and rendered site output, so they are the appropriate unit for publication manifests.

## Considered Options

- Publish directly from baseline directories because they are already discoverable.
- Keep baseline cataloging as the publication command and clarify the name later.
- Make `aots-report publish` consume Snapshot Output Bundles and treat baseline cataloging as a separate development concern.

## Consequences

- `publication-manifest.json` now records snapshot output bundles and comparison/certification state.
- Existing baseline directories must first be processed with `aots-report snapshot` before publication.
- If baseline cataloging remains useful, it should become a separate command or documentation concept, not the publication manifest.

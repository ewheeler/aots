# Root Portable Report Package

The portable report implementation will live at the repository root, with `src/aots_portable_reports/` as the candidate package path, instead of being added to one of the forecast, impact, dashboard, or orchestration submodules. The first Report Snapshot slice crosses those submodule boundaries, so a root package keeps the integration layer explicit while avoiding premature ownership changes inside the existing upstream repositories.

## Considered Options

- Add the portable report flow to `Ahead-of-the-Storm-DATAPIPELINE`, because it already generates report JSON and impact artifacts.
- Add the portable report flow to `Ahead-of-the-Storm`, because it owns the report page and presentation layer.
- Add a root-level package that coordinates exported artifacts from multiple submodules.

## Consequences

- The root package can validate a Known-Good Baseline without changing production submodule behavior.
- The package boundary must stay thin and artifact-oriented so it does not become a hidden fork of the submodules.

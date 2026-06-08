# Wrap Existing Report Generation First

The first portable Report Snapshot implementation will wrap the existing report-generation function rather than immediately re-modeling the report logic in the root package. This reduces behavior drift while the Known-Good Baseline comparison is being established; once the baseline comparison is stable, the report contract can be progressively extracted and normalized behind typed models.

The wrapper boundary is intentionally thin: it may adapt baseline artifacts into the current function's expected inputs and adapt the function output into `ReportSnapshot`, but it must not add new report calculations. New calculations belong upstream in artifact generation or downstream in explicit normalization/comparison steps.

## Considered Options

- Re-model the report logic directly in the new portable report package.
- Wrap the existing report-generation function first, then extract a cleaner contract incrementally.

## Consequences

- The first tracer bullet is more likely to match the current Snowflake-backed report behavior.
- The root package must keep the wrapper thin so it does not permanently entangle portable reports with legacy implementation details.

# Use Hamilton For First Report Materialization Flow

Status: Accepted.

The first portable Report Snapshot implementation will use Hamilton for the materialization flow rather than starting with ad hoc Python orchestration. The initial DAG will stay small and explicit: baseline validation, source artifact loading, report wrapper, `ReportSnapshot` model, comparison, and Quarto source. This keeps the target stack visible from the first slice while avoiding an over-generalized pipeline design.

## Considered Options

- Start with plain Python orchestration and add Hamilton after the boundaries stabilize.
- Use Hamilton from the start, but constrain the DAG to the minimal Report Snapshot flow.

## Consequences

- Dependencies between report materialization steps are explicit early.
- The first DAG must remain intentionally small so Hamilton does not become ceremony before the artifact contract is stable.

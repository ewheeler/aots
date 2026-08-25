# Baseline Artifact Formats

Status: Accepted.

Known-Good Baseline source artifacts will use Parquet for tabular and geospatial data where possible, with WKT or WKB geometry columns when GeoParquet compatibility is uncertain. JSON will be used for manifests, expected report output, generated report snapshots, and machine-readable comparison output; Markdown will be used only for human-readable summaries. This preserves source-data types while keeping the baseline contract and comparison results auditable through diffable JSON/Markdown files.

## Considered Options

- Store all exported artifacts as CSV/JSON for easier text diffs.
- Store source artifacts as Parquet and make the manifest/comparison layers responsible for auditability.

## Consequences

- Source artifacts keep stronger typing and more efficient geospatial/tabular storage.
- Reviewers should inspect `manifest.json`, `comparison.json`, and `comparison.md` rather than relying on raw source-artifact diffs.

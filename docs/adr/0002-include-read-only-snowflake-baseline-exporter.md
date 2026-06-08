# Include Read-Only Snowflake Baseline Exporter

The first portable report implementation will include a read-only `aots-report export-snowflake` command instead of requiring users to manually export baseline artifacts from Snowflake. This keeps the portable report flow grounded in a Known-Good Baseline while acknowledging that manual Snowflake export would be error-prone for users who are not familiar with Snowflake; `aots-report snapshot` remains the command of record for validation, regeneration, rendering, and comparison.

The exporter will read credentials from existing `SNOWFLAKE_*` environment variables or an optional `--env-file <path>`. It will not accept positional secrets or command-line password flags, because shell history and process listings can leak command-line secrets.

The exporter will also refuse to overwrite an existing non-empty baseline directory unless `--overwrite` is passed. It will write to a temporary sibling directory first, validate the manifest and checksums, then atomically move the validated export into place.

## Considered Options

- Keep baseline export manual and document the directory contract only.
- Include a read-only Snowflake exporter command in the first implementation.

## Consequences

- Users can create a Known-Good Baseline without writing ad hoc Snowflake SQL.
- The exporter must be clearly scoped as read-only so it does not become another orchestration path or mutate production state.

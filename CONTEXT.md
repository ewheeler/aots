# Ahead of the Storm

Ahead of the Storm turns tropical cyclone forecast data into impact information that can support preparedness decisions. This glossary names the planning concepts used when discussing portable report generation and publication.

## Language

**Forecast Run**:
A single issued tropical cyclone forecast for a storm at a specific issue time.
_Avoid_: Run, batch, date when the storm and issue time matter.

**Impact Artifact**:
A generated dataset that estimates exposure or risk for a forecast run, country, wind threshold, and geography or facility type.
_Avoid_: View, table, file when the storage backend is not important.

**Impact Report**:
A human-readable summary of expected impacts for one country, storm, and forecast run.
_Avoid_: Dashboard, alert, situation report unless those products are explicitly meant.

**Report Snapshot**:
The immutable inputs and outputs for one generated impact report at a specific point in time.
_Avoid_: Live report, latest report.

**Snapshot Output Bundle**:
The generated directory containing a report snapshot, manifest, comparison results, Quarto source, and rendered site output.
_Avoid_: Build directory, export folder, site output.

**Publication Manifest**:
An index of report snapshots and rendered outputs that a publication surface can expose without querying operational systems.
_Avoid_: Log, catalog, directory listing.

**Known-Good Baseline**:
A trusted exported set of source artifacts, expected outputs, and manifest metadata for one report snapshot.
_Avoid_: Test fixture, sample data, local rerun.

**Baseline Manifest**:
The root manifest that defines a known-good baseline and references all source artifacts by relative path.
_Avoid_: File list, metadata blob, config.

**Baseline Exporter**:
A read-only command that creates a known-good baseline from the current Snowflake-backed system.
_Avoid_: Migration tool, pipeline runner, Snowflake job.

**Exporter Credential Policy**:
The rule that baseline export credentials come from environment variables or an env file, never positional CLI secrets.
_Avoid_: Password flag, manual login instructions.

**Exporter Write Policy**:
The rule that baseline exports are written safely through a validated temporary directory before replacing an output directory.
_Avoid_: Overwrite mode, save behavior.

**Synthetic Baseline Fixture**:
A small artificial baseline used for tests without real locations or beneficiary-sensitive values.
_Avoid_: Sample export, anonymized production baseline.

**Artifact Format Policy**:
The rule that source artifacts use typed data formats while audit and comparison outputs remain human- or machine-readable.
_Avoid_: File extension convention, serialization detail.

**Portable Report Flow**:
A report generation and publication path that can run from local or blob-backed artifacts without requiring Snowflake credentials.
_Avoid_: Snowflake-free rewrite, local dashboard.

**Portable Report Package**:
The root-level package that owns the portable report flow across submodule boundaries.
_Avoid_: Data pipeline extension, dashboard plugin, orchestration module.

**Report Contract**:
The typed shape of a report snapshot that the portable report flow can validate and publish.
_Avoid_: JSON schema, report template, function signature.

**Report Wrapper**:
The adapter that calls existing report-generation logic and converts its inputs and outputs for the portable report flow.
_Avoid_: New report engine, report rewrite.

**Report Materialization Flow**:
The ordered process that turns a known-good baseline into a report snapshot, comparison results, and publication source.
_Avoid_: Pipeline, job, DAG when the user-facing report production concept is meant.

## Relationships

- A **Forecast Run** can produce many **Impact Artifacts**.
- An **Impact Report** is generated from one **Report Snapshot**.
- A **Report Snapshot** references the **Impact Artifacts** used to produce the report.
- A **Snapshot Output Bundle** contains one regenerated **Report Snapshot** and its audit trail.
- A **Publication Manifest** lists one or more **Report Snapshots**.
- A **Known-Good Baseline** is used to validate the first **Report Snapshot**.
- A **Report Wrapper** produces an initial **ReportSnapshot** without changing report calculations.
- A **Report Materialization Flow** produces a **Snapshot Output Bundle** from a **Known-Good Baseline**.
- A **Report Contract** is normalized from known-good behavior before it replaces existing report-generation logic.
- A **Baseline Manifest** is the contract for a **Known-Good Baseline**.
- A **Baseline Exporter** creates a **Known-Good Baseline** but does not validate the **Portable Report Flow** by itself.
- An **Exporter Credential Policy** protects secrets while making the **Baseline Exporter** usable for non-Snowflake experts.
- An **Exporter Write Policy** protects existing **Known-Good Baselines** from accidental overwrite or partial export output.
- An **Artifact Format Policy** makes **Known-Good Baselines** reproducible without requiring raw data files to be directly diffable.
- A **Synthetic Baseline Fixture** can test the **Portable Report Flow** without storing real exported baseline data in the repo.
- The **Portable Report Flow** publishes **Impact Reports** while keeping Snowflake as an optional backend.
- The **Portable Report Package** implements the **Portable Report Flow** without assigning ownership to a single submodule.

## Example dialogue

> **Dev:** "Should the first portable milestone reproduce the full dashboard?"
> **Domain expert:** "No. Start with a **Portable Report Flow** that renders one **Impact Report** from a known **Report Snapshot** and records it in a **Publication Manifest**."

## Flagged ambiguities

- "Snowflake-agnostic" means the report publication path can run without Snowflake credentials when equivalent local or blob artifacts exist; it does not mean removing Snowflake support from the production system.
- "First portable product" means one **Report Snapshot** for one country/storm/forecast tuple; a multi-report publication site comes later.
- "Known-good" means exported artifacts from the current trusted Snowflake-backed path, not freshly regenerated local pipeline outputs.
- A **Known-Good Baseline** includes the expected report output and the minimum source artifacts needed to regenerate it.
- A **Baseline Manifest** uses paths relative to its baseline root so the export can be moved and validated as a unit.
- A **Baseline Exporter** is read-only against Snowflake and exists so users do not need to manually run Snowflake SQL.
- The **Exporter Credential Policy** allows `SNOWFLAKE_*` environment variables and an env file, but not CLI password arguments.
- The **Exporter Write Policy** fails on existing non-empty output directories unless overwrite is explicit.
- The **Artifact Format Policy** uses Parquet for source artifacts, JSON for contracts and machine-readable outputs, and Markdown for human summaries.
- Real **Known-Good Baselines** stay outside the repository; committed fixtures should be **Synthetic Baseline Fixtures**.
- "Root package" means the **Portable Report Package** lives in this repository root and coordinates submodule artifacts; it does not mean moving code out of the submodules yet.
- The first **Report Contract** should wrap current report-generation behavior before extracting a cleaner contract.
- A **Report Wrapper** adapts inputs and outputs only; new calculations belong outside the wrapper.
- The first **Report Materialization Flow** is intentionally small: validate baseline, load artifacts, wrap report generation, model the snapshot, compare, and generate publication source.

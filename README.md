# Ahead of the Storm Workspace

Ahead of the Storm turns tropical cyclone forecasts into impact information for preparedness decisions. This integration workspace pins the application, forecast, impact, and orchestration repositories and provides the root `aots_portable_reports` package for reproducible report and alert artifacts.

The portable path publishes from Snapshot Output Bundles rather than querying Snowflake at publication time. Snowflake remains a supported read-only baseline source.

## Safe Quick Start

Prerequisites are Python 3.11, `uv`, Quarto, and initialized submodules. No credentials are needed for the synthetic workflow.

```bash
git submodule update --init --recursive
uv sync --dev
uv run aots-report snapshot \
  --baseline tests/fixtures/synthetic_alert_present_baseline \
  --out /tmp/aots-portable-snapshot
```

Open `/tmp/aots-portable-snapshot/site/index.html` and inspect `comparison.json`. Synthetic fixture success proves the local workflow, not independent certification.

Follow the [first portable snapshot tutorial](docs/tutorials/first-portable-snapshot.qmd) for the guided path or use the [CLI reference](docs/reference/cli.qmd) for exact options.

## Safety

- Keep real Known-Good Baselines, credentials, `.env` files, and local outputs uncommitted.
- Treat facility, beneficiary, geospatial, and operational data as potentially sensitive.
- Publish only from Snapshot Output Bundles with an appropriate comparison state and completed publication gates.
- Treat `alert-comparison.json` as an Alert Presentation Self-Check. Alert Parity requires independently sourced expected facts or output.
- Use synthetic fixtures for development and regression tests.

## Documentation

- [Documentation home](docs/index.qmd)
- [Tutorials](docs/tutorials/first-portable-snapshot.qmd)
- [How-to guides](docs/how-to/set-up-development.qmd)
- [Reference](docs/reference/cli.qmd)
- [Explanation](docs/explanation/architecture.qmd)
- [Decisions](docs/adr/index.qmd)
- [Project status and roadmap](docs/project/status.qmd)
- [Contributor guide and checks](docs/contributor/documentation-guide.qmd)
- [Canonical terminology](CONTEXT.md)

Agent configuration is owned by `AGENTS.md`, `.agents/`, and `.repo-familiar/bootstrap.yml`. Open implementation work is tracked concisely in `plan.md`.

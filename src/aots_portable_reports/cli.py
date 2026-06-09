from __future__ import annotations

import argparse
import sys
from pathlib import Path

from aots_portable_reports.alert_contract import IGNORED_LOCAL_BASELINE_ROOT
from aots_portable_reports.export_snowflake import ExportRequest, SnowflakeExportError, export_snowflake_baseline
from aots_portable_reports.publication import publish_snapshot_index
from aots_portable_reports.runner import run_snapshot
from aots_portable_reports.validation import BaselineValidationError


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="aots-report")
    subparsers = parser.add_subparsers(dest="command", required=True)
    snapshot = subparsers.add_parser("snapshot", help="Generate and compare one Report Snapshot.")
    snapshot.add_argument("--baseline", required=True, type=Path)
    snapshot.add_argument("--out", required=True, type=Path)
    export = subparsers.add_parser("export-snowflake", help="Export a read-only Snowflake Known-Good Baseline.")
    export.add_argument("--country", required=True)
    export.add_argument("--storm", required=True)
    export.add_argument("--forecast-time", required=True)
    export.add_argument("--out", type=Path)
    export.add_argument("--case-name", help=f"Write to {IGNORED_LOCAL_BASELINE_ROOT}/<case-name> when --out is omitted.")
    export.add_argument("--env-file", type=Path)
    export.add_argument("--wind-threshold", type=int, action="append", default=[])
    export.add_argument("--zoom-level", type=int, default=14)
    export.add_argument("--admin-level", type=int, default=1)
    export.add_argument("--include-alert-html", action="store_true", help="Export ALERT_SENT_LOG.EMAIL_BODY as expected-alert.html when available.")
    export.add_argument("--overwrite", action="store_true")
    export.add_argument("--plan-only", action="store_true", help="Validate config and print the export plan without connecting.")
    export.add_argument("--dry-run", action="store_true", help="Alias for --plan-only.")
    export.add_argument("--json", action="store_true", help="Print the export plan as JSON with no secrets.")
    publish = subparsers.add_parser("publish", help="Publish an index of local Report Snapshot baselines.")
    publish.add_argument("--snapshots-dir", required=True, type=Path)
    publish.add_argument("--out", required=True, type=Path)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.command == "snapshot":
        try:
            run_snapshot(args.baseline, args.out)
        except BaselineValidationError as exc:
            print(str(exc), file=sys.stderr)
            return 2
        return 0
    if args.command == "export-snowflake":
        out = args.out or (IGNORED_LOCAL_BASELINE_ROOT / args.case_name if args.case_name else None)
        if out is None:
            print("either --out or --case-name is required", file=sys.stderr)
            return 2
        try:
            message = export_snowflake_baseline(
                ExportRequest(
                    country=args.country,
                    storm=args.storm,
                    forecast_time=args.forecast_time,
                    out=out,
                    overwrite=args.overwrite,
                    plan_only=args.plan_only or args.dry_run,
                    json_output=args.json,
                    env_file=args.env_file,
                    wind_thresholds=tuple(args.wind_threshold),
                    zoom_level=args.zoom_level,
                    admin_level=args.admin_level,
                    include_alert_html=args.include_alert_html,
                )
            )
        except SnowflakeExportError as exc:
            print(str(exc), file=sys.stderr)
            return 2
        print(message)
        return 0
    if args.command == "publish":
        cases = publish_snapshot_index(args.snapshots_dir, args.out)
        print(f"Published {len(cases)} snapshot entries to {args.out}")
        return 0
    parser.error(f"unknown command: {args.command}")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pandas as pd

from aots_portable_reports.alert_contract import EXPECTED_ALERT_EMAIL_FILENAME
from aots_portable_reports.export_snowflake import ExportRequest, export_snowflake_baseline


class FakeQueryRunner:
    def __init__(self) -> None:
        self.calls: list[tuple[str, list[Any]]] = []

    def query(self, sql: str, params: list[Any]) -> pd.DataFrame:
        self.calls.append((sql, params))
        if "DISTINCT WIND_THRESHOLD" in sql:
            return pd.DataFrame({"WIND_THRESHOLD": [34]})
        if "ALERT_SENT_LOG" in sql:
            return pd.DataFrame({"EMAIL_BODY": ["<html><body><h1>Storm Alert</h1></body></html>"]})
        return pd.DataFrame({"COUNTRY": ["TST"], "STORM": ["ALPHA"], "VALUE": [1]})


def write_env_file(tmp_path: Path) -> Path:
    env_file = tmp_path / ".env.snowflake"
    env_file.write_text(
        "\n".join(
            [
                "SNOWFLAKE_ACCOUNT=test-account",
                "SNOWFLAKE_USER=test-user",
                "SNOWFLAKE_PASSWORD=super-secret",
                "SNOWFLAKE_WAREHOUSE=AOTS_WH",
                "SNOWFLAKE_DATABASE=AOTS",
                "SNOWFLAKE_SCHEMA=TC_ECMWF",
            ]
        )
        + "\n"
    )
    return env_file


def test_export_snowflake_writes_baseline_manifest_expected_report_and_artifacts(tmp_path: Path, monkeypatch) -> None:
    for key in list(__import__("os").environ):
        if key.startswith("SNOWFLAKE_"):
            monkeypatch.delenv(key, raising=False)
    out_dir = tmp_path / "baseline"
    fake = FakeQueryRunner()

    message = export_snowflake_baseline(
        ExportRequest(
            country="TST",
            storm="ALPHA",
            forecast_time="2026-01-01T00:00:00Z",
            out=out_dir,
            env_file=write_env_file(tmp_path),
        ),
        query_runner=fake,
    )

    assert "Exported Known-Good Baseline" in message
    assert "Artifacts exported:" in message
    assert "Rows exported:" in message
    assert "uv run aots-report snapshot" in message
    assert (out_dir / "manifest.json").is_file()
    assert (out_dir / "expected-report.json").is_file()
    manifest = json.loads((out_dir / "manifest.json").read_text())
    roles = {artifact["role"] for artifact in manifest["artifacts"]}
    assert {"admin", "tiles", "facilities", "cci", "tracks", "envelopes", "vulnerability"}.issubset(roles)
    assert all((out_dir / artifact["path"]).is_file() for artifact in manifest["artifacts"])
    assert any("MERCATOR_TILE_IMPACT_MAT" in sql for sql, _ in fake.calls)
    assert any("TC_ENVELOPES_COMBINED" in sql for sql, _ in fake.calls)


def test_export_snowflake_can_include_alert_html_from_sent_log(tmp_path: Path, monkeypatch) -> None:
    for key in list(__import__("os").environ):
        if key.startswith("SNOWFLAKE_"):
            monkeypatch.delenv(key, raising=False)
    out_dir = tmp_path / "baseline"
    fake = FakeQueryRunner()

    message = export_snowflake_baseline(
        ExportRequest(
            country="TST",
            storm="ALPHA",
            forecast_time="2026-01-01T00:00:00Z",
            out=out_dir,
            env_file=write_env_file(tmp_path),
            include_alert_html=True,
        ),
        query_runner=fake,
    )

    manifest = json.loads((out_dir / "manifest.json").read_text())
    assert manifest["expected_alert_path"] == EXPECTED_ALERT_EMAIL_FILENAME
    assert (out_dir / EXPECTED_ALERT_EMAIL_FILENAME).read_text() == "<html><body><h1>Storm Alert</h1></body></html>"
    assert f"Alert HTML exported: {EXPECTED_ALERT_EMAIL_FILENAME}" in message
    assert any("ALERT_SENT_LOG" in sql for sql, _ in fake.calls)

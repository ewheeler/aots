from __future__ import annotations

from pathlib import Path
import json

from aots_portable_reports.cli import main


SNOWFLAKE_ENV_KEYS = [
    "SNOWFLAKE_ACCOUNT",
    "SNOWFLAKE_USER",
    "SNOWFLAKE_PASSWORD",
    "SNOWFLAKE_WAREHOUSE",
    "SNOWFLAKE_DATABASE",
    "SNOWFLAKE_SCHEMA",
]


def clear_snowflake_env(monkeypatch) -> None:
    for key in SNOWFLAKE_ENV_KEYS:
        monkeypatch.delenv(key, raising=False)


def test_export_snowflake_fails_before_writing_when_required_env_is_missing(
    tmp_path: Path, monkeypatch, capsys
) -> None:
    clear_snowflake_env(monkeypatch)
    out_dir = tmp_path / "baseline"

    exit_code = main(
        [
            "export-snowflake",
            "--country",
            "TST",
            "--storm",
            "ALPHA",
            "--forecast-time",
            "2026-01-01T00:00:00Z",
            "--out",
            str(out_dir),
        ]
    )

    assert exit_code == 2
    assert not out_dir.exists()
    assert "missing Snowflake configuration" in capsys.readouterr().err


def test_export_snowflake_refuses_existing_non_empty_output_before_connecting(
    tmp_path: Path, monkeypatch, capsys
) -> None:
    clear_snowflake_env(monkeypatch)
    out_dir = tmp_path / "baseline"
    out_dir.mkdir()
    (out_dir / "keep.txt").write_text("do not overwrite\n")

    exit_code = main(
        [
            "export-snowflake",
            "--country",
            "TST",
            "--storm",
            "ALPHA",
            "--forecast-time",
            "2026-01-01T00:00:00Z",
            "--out",
            str(out_dir),
        ]
    )

    assert exit_code == 2
    assert (out_dir / "keep.txt").read_text() == "do not overwrite\n"
    assert "refusing to overwrite" in capsys.readouterr().err


def test_export_snowflake_loads_env_file_and_prints_non_secret_config(
    tmp_path: Path, monkeypatch, capsys
) -> None:
    clear_snowflake_env(monkeypatch)
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

    exit_code = main(
        [
            "export-snowflake",
            "--country",
            "TST",
            "--storm",
            "ALPHA",
            "--forecast-time",
            "2026-01-01T00:00:00Z",
            "--out",
            str(tmp_path / "baseline"),
            "--env-file",
            str(env_file),
            "--plan-only",
        ]
    )

    captured = capsys.readouterr()
    assert exit_code == 0
    assert "test-account" in captured.out
    assert "AOTS" in captured.out
    assert "TC_ECMWF" in captured.out
    assert "AOTS_WH" in captured.out
    assert "super-secret" not in captured.out


def test_export_snowflake_plan_only_json_lists_artifacts_without_secrets(
    tmp_path: Path, monkeypatch, capsys
) -> None:
    clear_snowflake_env(monkeypatch)
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

    exit_code = main(
        [
            "export-snowflake",
            "--country",
            "TST",
            "--storm",
            "ALPHA",
            "--forecast-time",
            "2026-01-01T00:00:00Z",
            "--out",
            str(tmp_path / "baseline"),
            "--env-file",
            str(env_file),
            "--wind-threshold",
            "34",
            "--plan-only",
            "--json",
        ]
    )

    captured = capsys.readouterr()
    plan = json.loads(captured.out)
    assert exit_code == 0
    assert plan["snowflake"]["account"] == "test-account"
    assert plan["artifacts"]
    assert "super-secret" not in captured.out

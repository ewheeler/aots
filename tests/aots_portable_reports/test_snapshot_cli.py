from __future__ import annotations

import json
import hashlib
import shutil
from pathlib import Path

from aots_portable_reports.alert_contract import (
    ALERT_ASSETS_DIRNAME,
    ALERT_CLAIMS_FILENAME,
    ALERT_COMPARISON_FILENAME,
    ALERT_CONTEXT_FILENAME,
    EXPECTED_ALERT_EMAIL_FILENAME,
    RENDERED_ALERT_HTML_FILENAME,
)
from aots_portable_reports.cli import main
from aots_portable_reports.runner import run_snapshot


FIXTURE_ROOT = Path(__file__).parents[1] / "fixtures"
FIXTURE_BASELINE = FIXTURE_ROOT / "synthetic_baseline"


def copy_fixture(tmp_path: Path, fixture_name: str = "synthetic_baseline") -> Path:
    baseline = tmp_path / "baseline"
    shutil.copytree(FIXTURE_ROOT / fixture_name, baseline)
    return baseline


def test_snapshot_command_creates_auditable_output_bundle(tmp_path: Path) -> None:
    baseline = copy_fixture(tmp_path)
    out_dir = tmp_path / "out"

    exit_code = main(["snapshot", "--baseline", str(baseline), "--out", str(out_dir)])

    assert exit_code == 0
    assert (out_dir / "manifest.json").is_file()
    assert (out_dir / "report-snapshot.json").is_file()
    assert (out_dir / "comparison.json").is_file()
    assert (out_dir / "comparison.md").is_file()
    assert (out_dir / "quarto" / "index.qmd").is_file()
    assert (out_dir / "quarto" / "_quarto.yml").is_file()
    assert (out_dir / "site").is_dir()
    assert (out_dir / "site" / "index.html").is_file()

    comparison = json.loads((out_dir / "comparison.json").read_text())
    assert comparison["status"] == "passed"


def test_snapshot_command_copies_expected_alert_html_when_present(tmp_path: Path) -> None:
    baseline = copy_fixture(tmp_path)
    (baseline / EXPECTED_ALERT_EMAIL_FILENAME).write_text(
        "<html><body><h1>Storm ALPHA — TST</h1><p>Situation Summary</p>"
        "<p>AI system based on probabilistic model outputs</p><code>data</code></body></html>"
    )
    manifest_path = baseline / "manifest.json"
    manifest = json.loads(manifest_path.read_text())
    manifest["expected_alert_path"] = EXPECTED_ALERT_EMAIL_FILENAME
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n")
    out_dir = tmp_path / "out"

    exit_code = main(["snapshot", "--baseline", str(baseline), "--out", str(out_dir)])

    assert exit_code == 0
    assert "Storm ALPHA" in (out_dir / EXPECTED_ALERT_EMAIL_FILENAME).read_text()


def test_expected_html_without_decision_does_not_create_local_alert_audit(
    tmp_path: Path,
) -> None:
    baseline = copy_fixture(tmp_path)
    (baseline / EXPECTED_ALERT_EMAIL_FILENAME).write_text(
        "<html><body><h1>Storm ALPHA — TST</h1>"
        "<section><h2>Situation Summary</h2><p>Synthetic expected prose.</p></section>"
        "<p>AI system based on probabilistic model outputs</p><code>data</code><code>inferred</code>"
        "</body></html>"
    )
    manifest_path = baseline / "manifest.json"
    manifest = json.loads(manifest_path.read_text())
    manifest["expected_alert_path"] = EXPECTED_ALERT_EMAIL_FILENAME
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n")
    out_dir = tmp_path / "out"

    exit_code = main(["snapshot", "--baseline", str(baseline), "--out", str(out_dir)])

    assert exit_code == 0
    assert (out_dir / EXPECTED_ALERT_EMAIL_FILENAME).is_file()
    assert not (out_dir / ALERT_CONTEXT_FILENAME).exists()
    assert not (out_dir / ALERT_CLAIMS_FILENAME).exists()
    assert not (out_dir / ALERT_COMPARISON_FILENAME).exists()
    assert not (out_dir / RENDERED_ALERT_HTML_FILENAME).exists()


def test_snapshot_command_keeps_expected_email_rendered_alert_and_audit_files_separate(
    tmp_path: Path,
) -> None:
    baseline = copy_fixture(tmp_path)
    (baseline / EXPECTED_ALERT_EMAIL_FILENAME).write_text(
        "<html><body><h1>Storm ALPHA — TST</h1>"
        "<section><h2>Situation Summary</h2><p>Synthetic expected prose.</p></section>"
        "<p>AI system based on probabilistic model outputs</p><code>data</code><code>inferred</code>"
        "</body></html>"
    )
    manifest_path = baseline / "manifest.json"
    manifest = json.loads(manifest_path.read_text())
    manifest["expected_alert_path"] = EXPECTED_ALERT_EMAIL_FILENAME
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n")
    out_dir = tmp_path / "out"

    exit_code = main(["snapshot", "--baseline", str(baseline), "--out", str(out_dir)])

    assert exit_code == 0
    assert (out_dir / EXPECTED_ALERT_EMAIL_FILENAME).is_file()
    assert not (out_dir / RENDERED_ALERT_HTML_FILENAME).exists()
    assert not list(out_dir.glob("alert-*.json"))


def test_snapshot_command_uses_structured_alert_inputs_for_claims_and_rendering(
    tmp_path: Path,
) -> None:
    baseline = copy_fixture(tmp_path, "synthetic_alert_present_baseline")
    expected_report_path = baseline / "expected-report.json"
    expected_report_path.write_text(
        json.dumps(
            {
                "country": "TST",
                "storm": "ALPHA",
                "forecast_time": "2026-01-01T00:00:00Z",
                "expected_pop": 123,
                "expected_children": 45,
                "expected_hcs": 6,
                "expected_shelters": 2,
                "expected_wash": 7,
                "E_people_in_need": 90,
                "E_children_in_need": 30,
                "expected_pop_34": 200,
                "expected_children_34": 80,
                "rows_admins_pop_total": [{"name": "North District", "50": 70}],
            },
            indent=2,
        )
        + "\n"
    )
    (baseline / EXPECTED_ALERT_EMAIL_FILENAME).write_text(
        "<html><body><h1>Storm HTML-ONLY - XXX</h1>"
        "<section><h2>Situation Summary</h2><p>Replay only prose.</p></section>"
        "<section><h2>Expected Impact - 50kt</h2><p>Snowflake-only population 9999.</p></section>"
        "<p>AI system based on probabilistic model outputs</p><code>data</code><code>inferred</code>"
        "</body></html>"
    )
    manifest_path = baseline / "manifest.json"
    manifest = json.loads(manifest_path.read_text())
    manifest["expected_alert_path"] = EXPECTED_ALERT_EMAIL_FILENAME
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n")
    out_dir = tmp_path / "out"

    exit_code = main(["snapshot", "--baseline", str(baseline), "--out", str(out_dir)])

    assert exit_code == 0
    context = json.loads((out_dir / ALERT_CONTEXT_FILENAME).read_text())
    claims = json.loads((out_dir / ALERT_CLAIMS_FILENAME).read_text())
    rendered = (out_dir / RENDERED_ALERT_HTML_FILENAME).read_text()
    assert context["identity"] == {
        "country": "TST",
        "storm": "ALPHA",
        "forecast_time": "2026-01-01T00:00:00Z",
    }
    assert context["main_threshold"] == {"wind_threshold": 50, "label": "50kt"}
    assert context["impact_totals"]["population"] == 123
    assert context["people_in_need"] == {"population": 90, "children": 30}
    assert context["top_admin_areas"] == [{"name": "North District", "population": 70}]
    assert context["cross_threshold_rows"] == [
        {"wind_threshold": 34, "population": 200, "children": 80}
    ]
    assert context["required_caveats"] == [
        {
            "id": "ai_probabilistic_model_outputs",
            "text": "AI system based on probabilistic model outputs",
            "provenance_labels": ["inferred"],
        }
    ]
    assert claims["identity"] == context["identity"]
    assert claims["impact_totals"] == [
        {"metric": "population", "value": 123, "provenance_labels": ["data"]},
        {"metric": "children", "value": 45, "provenance_labels": ["data"]},
        {"metric": "health_centers", "value": 6, "provenance_labels": ["data"]},
        {"metric": "shelters", "value": 2, "provenance_labels": ["data"]},
        {"metric": "wash", "value": 7, "provenance_labels": ["data"]},
    ]
    assert claims["people_in_need_values"] == [
        {"metric": "population", "value": 90, "provenance_labels": ["inferred"]},
        {"metric": "children", "value": 30, "provenance_labels": ["inferred"]},
    ]
    assert claims["top_admin_areas"] == [
        {
            "name": "North District",
            "population": 70,
            "provenance_labels": ["data", "inferred"],
        }
    ]
    assert claims["cross_threshold_rows"] == [
        {"wind_threshold": 34, "population": 200, "children": 80, "provenance_labels": ["data"]}
    ]
    assert "Storm ALPHA - TST" in rendered
    assert "Replay only prose." not in rendered
    assert "No bounded summary prose was available." in rendered
    assert "North District" in rendered
    assert "123" in rendered
    assert "HTML-ONLY" not in rendered
    assert "Snowflake-only population 9999." not in rendered


def test_snapshot_command_uses_committed_alert_present_fixture(tmp_path: Path) -> None:
    baseline = copy_fixture(tmp_path, "synthetic_alert_present_baseline")
    out_dir = tmp_path / "out"

    exit_code = main(["snapshot", "--baseline", str(baseline), "--out", str(out_dir)])

    assert exit_code == 0
    assert (out_dir / EXPECTED_ALERT_EMAIL_FILENAME).is_file()
    assert (out_dir / RENDERED_ALERT_HTML_FILENAME).is_file()
    comparison = json.loads((out_dir / ALERT_COMPARISON_FILENAME).read_text())
    rendered = (out_dir / RENDERED_ALERT_HTML_FILENAME).read_text()
    assert comparison["status"] == "passed"
    assert comparison["warnings"] == []
    assert "AI system based on probabilistic model outputs" in rendered


def test_snapshot_command_writes_reviewable_rendered_alert_html(tmp_path: Path) -> None:
    baseline = copy_fixture(tmp_path, "synthetic_alert_present_baseline")
    out_dir = tmp_path / "out"

    exit_code = main(["snapshot", "--baseline", str(baseline), "--out", str(out_dir)])

    assert exit_code == 0
    rendered = (out_dir / RENDERED_ALERT_HTML_FILENAME).read_text()
    assert "Active Forecast" in rendered
    assert ">Summary<" in rendered
    assert ">Situation<" in rendered
    assert ">Forecast<" in rendered
    assert "Forecast Exposure" in rendered
    assert "Wind Exposure Probability - 50kt" in rendered
    assert "Highest-Exposure Administrative Areas" in rendered
    assert "Threshold Exposure" in rendered
    assert "Required Caveats" in rendered
    assert '<th scope="col">Fact</th>' in rendered
    assert '<th scope="col">Area</th>' in rendered
    assert '<th scope="col">Wind Threshold</th>' in rendered


def test_snapshot_command_uses_committed_alert_missing_fixture(tmp_path: Path) -> None:
    baseline = copy_fixture(tmp_path, "synthetic_alert_missing_baseline")
    out_dir = tmp_path / "out"

    exit_code = main(["snapshot", "--baseline", str(baseline), "--out", str(out_dir)])

    assert exit_code == 0
    assert not (out_dir / EXPECTED_ALERT_EMAIL_FILENAME).exists()
    assert (out_dir / RENDERED_ALERT_HTML_FILENAME).exists()
    assert (out_dir / ALERT_CONTEXT_FILENAME).exists()
    assert (out_dir / ALERT_CLAIMS_FILENAME).exists()
    assert (out_dir / ALERT_COMPARISON_FILENAME).exists()
    assert "Storm Warning" in (out_dir / RENDERED_ALERT_HTML_FILENAME).read_text()


def test_snapshot_bundle_manifest_records_alert_artifact_paths_when_emitted(tmp_path: Path) -> None:
    baseline = copy_fixture(tmp_path, "synthetic_alert_present_baseline")
    out_dir = tmp_path / "out"

    bundle = run_snapshot(baseline, out_dir)

    manifest = json.loads((out_dir / "manifest.json").read_text())
    assert manifest["expected_alert_html_path"] == EXPECTED_ALERT_EMAIL_FILENAME
    assert manifest["expected_alert_provenance"] == "seed_placeholder"
    assert manifest["rendered_alert_html_path"] == RENDERED_ALERT_HTML_FILENAME
    assert manifest["alert_context_path"] == ALERT_CONTEXT_FILENAME
    assert manifest["alert_claims_path"] == ALERT_CLAIMS_FILENAME
    assert manifest["alert_comparison_json_path"] == ALERT_COMPARISON_FILENAME
    assert manifest["alert_visual_asset_paths"]
    assert bundle.expected_alert_html_path == str(out_dir / EXPECTED_ALERT_EMAIL_FILENAME)
    assert bundle.rendered_alert_html_path == str(out_dir / RENDERED_ALERT_HTML_FILENAME)
    assert bundle.alert_context_path == str(out_dir / ALERT_CONTEXT_FILENAME)
    assert bundle.alert_claims_path == str(out_dir / ALERT_CLAIMS_FILENAME)
    assert bundle.alert_comparison_json_path == str(out_dir / ALERT_COMPARISON_FILENAME)
    assert bundle.alert_visual_asset_paths


def test_snapshot_bundle_writes_visual_png_assets_and_inline_images_when_source_data_exists(
    tmp_path: Path,
) -> None:
    baseline = copy_fixture(tmp_path, "synthetic_alert_present_baseline")
    out_dir = tmp_path / "out"

    bundle = run_snapshot(baseline, out_dir)

    manifest = json.loads((out_dir / "manifest.json").read_text())
    rendered = (out_dir / RENDERED_ALERT_HTML_FILENAME).read_text()
    asset_paths = manifest["alert_visual_asset_paths"]
    assert asset_paths
    for relative_path in asset_paths:
        path = out_dir / relative_path
        assert path.is_file()
        assert path.parent.name == ALERT_ASSETS_DIRNAME
        assert path.read_bytes().startswith(b"\x89PNG")
    assert bundle.alert_visual_asset_paths
    assert "data:image/png;base64," in rendered
    assert (
        "Forecast Evolution" in rendered
        or "Wind Exposure Probability by Wind Threshold" in rendered
    )


def test_snapshot_bundle_manifest_records_local_alert_paths_without_expected_alert(
    tmp_path: Path,
) -> None:
    baseline = copy_fixture(tmp_path, "synthetic_alert_missing_baseline")
    out_dir = tmp_path / "out"

    bundle = run_snapshot(baseline, out_dir)

    manifest = json.loads((out_dir / "manifest.json").read_text())
    assert "expected_alert_html_path" not in manifest
    assert manifest["rendered_alert_html_path"] == RENDERED_ALERT_HTML_FILENAME
    assert manifest["alert_context_path"] == ALERT_CONTEXT_FILENAME
    assert manifest["alert_claims_path"] == ALERT_CLAIMS_FILENAME
    assert manifest["alert_comparison_json_path"] == ALERT_COMPARISON_FILENAME
    assert bundle.expected_alert_html_path is None
    assert bundle.rendered_alert_html_path == str(out_dir / RENDERED_ALERT_HTML_FILENAME)
    assert bundle.alert_context_path == str(out_dir / ALERT_CONTEXT_FILENAME)
    assert bundle.alert_claims_path == str(out_dir / ALERT_CLAIMS_FILENAME)
    assert bundle.alert_comparison_json_path == str(out_dir / ALERT_COMPARISON_FILENAME)
    assert [Path(path).name for path in bundle.alert_visual_asset_paths] == [
        "people-in-need-composition.png"
    ]


def test_manual_review_decision_persists_audit_without_product_html(tmp_path: Path) -> None:
    baseline = copy_fixture(tmp_path, "synthetic_alert_missing_baseline")
    decision_path = baseline / "artifacts" / "alert" / "alert-decision.json"
    decision = json.loads(decision_path.read_text())
    decision["current_storm_state"]["supported"] = False
    decision["product_decision"]["product_type"] = "manual_review"
    decision["product_decision"]["reason"] = "official_status_unsupported"
    decision_identity = {
        key: value for key, value in decision["product_decision"].items() if key != "version"
    }
    decision["product_decision"]["version"] = (
        "product-decision-"
        + hashlib.sha256(
            json.dumps(decision_identity, sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest()
    )
    decision_path.write_text(json.dumps(decision, indent=2) + "\n")
    manifest_path = baseline / "manifest.json"
    manifest = json.loads(manifest_path.read_text())
    decision_artifact = next(
        artifact for artifact in manifest["artifacts"] if artifact["role"] == "alert_decision"
    )
    decision_artifact["checksum_sha256"] = hashlib.sha256(decision_path.read_bytes()).hexdigest()
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n")
    out_dir = tmp_path / "out"

    bundle = run_snapshot(baseline, out_dir)

    assert not (out_dir / RENDERED_ALERT_HTML_FILENAME).exists()
    assert not (out_dir / ALERT_COMPARISON_FILENAME).exists()
    assert (out_dir / ALERT_CONTEXT_FILENAME).exists()
    assert (out_dir / ALERT_CLAIMS_FILENAME).exists()
    claims = json.loads((out_dir / ALERT_CLAIMS_FILENAME).read_text())
    assert claims["product_decision"]["product_type"] == "manual_review"
    assert bundle.rendered_alert_html_path is None
    assert bundle.alert_comparison_json_path is None


def test_snapshot_command_uses_committed_sparse_alert_fixture(tmp_path: Path) -> None:
    baseline = copy_fixture(tmp_path, "synthetic_alert_sparse_baseline")
    out_dir = tmp_path / "out"

    exit_code = main(["snapshot", "--baseline", str(baseline), "--out", str(out_dir)])

    assert exit_code == 0
    comparison = json.loads((out_dir / ALERT_COMPARISON_FILENAME).read_text())
    rendered = (out_dir / RENDERED_ALERT_HTML_FILENAME).read_text()
    assert comparison["status"] == "passed"
    assert comparison["failures"] == []
    assert comparison["warnings"] == []
    assert "Sparse fixture summary." not in rendered
    assert "No bounded summary prose was available." in rendered
    assert "AI system based on probabilistic model outputs" in rendered


def test_snapshot_command_fails_when_required_artifact_is_missing(tmp_path: Path, capsys) -> None:
    baseline = copy_fixture(tmp_path)
    (baseline / "artifacts" / "admin" / "admin_34.parquet").unlink()

    exit_code = main(["snapshot", "--baseline", str(baseline), "--out", str(tmp_path / "out")])

    assert exit_code == 2
    assert "missing required artifacts" in capsys.readouterr().err


def test_snapshot_command_fails_on_checksum_mismatch(tmp_path: Path, capsys) -> None:
    baseline = copy_fixture(tmp_path)
    (baseline / "artifacts" / "admin" / "admin_34.parquet").write_text("tampered\n")

    exit_code = main(["snapshot", "--baseline", str(baseline), "--out", str(tmp_path / "out")])

    assert exit_code == 2
    assert "checksum mismatch" in capsys.readouterr().err


def test_snapshot_command_fails_on_manifest_schema_mismatch(tmp_path: Path, capsys) -> None:
    baseline = copy_fixture(tmp_path)
    manifest_path = baseline / "manifest.json"
    manifest = json.loads(manifest_path.read_text())
    del manifest["country"]
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n")

    exit_code = main(["snapshot", "--baseline", str(baseline), "--out", str(tmp_path / "out")])

    assert exit_code == 2
    assert "schema mismatch" in capsys.readouterr().err


def test_snapshot_command_fails_on_artifact_row_count_mismatch(tmp_path: Path, capsys) -> None:
    baseline = copy_fixture(tmp_path)
    manifest_path = baseline / "manifest.json"
    manifest = json.loads(manifest_path.read_text())
    manifest["artifacts"][0]["row_count"] = 999
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n")

    exit_code = main(["snapshot", "--baseline", str(baseline), "--out", str(tmp_path / "out")])

    assert exit_code == 2
    assert "row count mismatch" in capsys.readouterr().err


def test_snapshot_command_fails_on_artifact_schema_hash_mismatch(tmp_path: Path, capsys) -> None:
    baseline = copy_fixture(tmp_path)
    manifest_path = baseline / "manifest.json"
    manifest = json.loads(manifest_path.read_text())
    manifest["artifacts"][0]["schema_hash"] = "wrong-schema"
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n")

    exit_code = main(["snapshot", "--baseline", str(baseline), "--out", str(tmp_path / "out")])

    assert exit_code == 2
    assert "schema mismatch" in capsys.readouterr().err

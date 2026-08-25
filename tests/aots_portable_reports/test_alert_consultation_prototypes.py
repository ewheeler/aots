from __future__ import annotations

import hashlib
import importlib.util
import json
import shutil
from pathlib import Path
from types import ModuleType

import pytest

ROOT = Path(__file__).parents[2]
CONSULTATION_SOURCE = ROOT / "docs" / "project" / "alert-packaging-consultation"
SCENARIOS = CONSULTATION_SOURCE / "scenarios"
TEMPLATES = CONSULTATION_SOURCE / "prototype-templates"
STYLESHEET = CONSULTATION_SOURCE / "prototype.css"
SCREENSHOT_EVIDENCE = ROOT / "docs" / "assets" / "alert-packaging-consultation"


def _load_generator() -> ModuleType:
    path = ROOT / "scripts" / "build_alert_packaging_consultation.py"
    spec = importlib.util.spec_from_file_location("alert_consultation_generator", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"could not load consultation generator from {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


GENERATOR = _load_generator()
ConsultationInputError = GENERATOR.ConsultationInputError
build_consultation_pack = GENERATOR.build_consultation_pack


def test_build_writes_complete_consultation_output_matrix(tmp_path: Path) -> None:
    manifest = build_consultation_pack(
        scenario_dir=SCENARIOS,
        template_dir=TEMPLATES,
        stylesheet_path=STYLESHEET,
        output_dir=tmp_path,
    )

    outputs = {entry["path"] for entry in manifest["outputs"]}
    assert len(outputs) == 15
    assert "consultation-index.qmd" in outputs
    assert "prototype.css" in outputs
    assert "emails/official-alert--combined-long.html" in outputs
    assert "emails/official-warning--concise-linked-report.html" in outputs
    assert "emails/forecast-only-warning--concise-linked-report.html" in outputs
    assert "reports/forecast-only-warning--technical-report.html" in outputs
    assert (tmp_path / "manifest.json").exists()


def test_repeated_builds_are_byte_identical(tmp_path: Path) -> None:
    first = tmp_path / "first"
    second = tmp_path / "second"

    build_consultation_pack(SCENARIOS, TEMPLATES, STYLESHEET, first)
    build_consultation_pack(SCENARIOS, TEMPLATES, STYLESHEET, second)

    first_files = {
        path.relative_to(first): path.read_bytes() for path in first.rglob("*") if path.is_file()
    }
    second_files = {
        path.relative_to(second): path.read_bytes() for path in second.rglob("*") if path.is_file()
    }
    assert first_files == second_files


def test_outputs_preserve_semantic_and_safety_boundaries(tmp_path: Path) -> None:
    build_consultation_pack(SCENARIOS, TEMPLATES, STYLESHEET, tmp_path)

    html_outputs = sorted(tmp_path.glob("*/*.html"))
    assert len(html_outputs) == 12
    for path in html_outputs:
        html = path.read_text()
        assert "CONSULTATION PROTOTYPE - NOT OPERATIONAL" in html
        assert "Synthetic public test data" in html
        assert "Modeled exposure - not observed impact" in html
        assert "Forecast-conditioned PiN/CHiN - not observed need" in html
        assert "Prototype wording - not approved action guidance" in html
        assert "Complete cumulative 144-hour local threat at 34 kt" in html
        assert "50 kt local threat" not in html
        assert "Rainfall unavailable" in html
        assert "Storm surge unavailable" in html
        assert "http://" not in html
        assert "https://" not in html
        assert "<script" not in html.lower()
        for prohibited in (
            "recipient_email",
            "private contact",
            "profile_id",
            "provider_id",
            "source_url",
            "latitude",
            "longitude",
            "observed affected population",
            "observed damage",
        ):
            assert prohibited not in html.lower()

    forecast_only = (
        tmp_path / "emails" / "forecast-only-warning--concise-linked-report.html"
    ).read_text()
    assert "Supplied Product Decision: Warning" in forecast_only
    assert "Official status unavailable" in forecast_only
    assert "Supplied Product Decision: Alert" not in forecast_only


def test_numeric_fact_changes_do_not_reclassify_the_supplied_decision(tmp_path: Path) -> None:
    scenario_dir = tmp_path / "scenarios"
    shutil.copytree(SCENARIOS, scenario_dir)
    path = scenario_dir / "official-alert.json"
    scenario = json.loads(path.read_text())
    scenario["display_name"] = "Cyclone Aurora & Beacon"
    scenario["local_threat"]["expected_population"] = 999
    scenario["local_threat"]["expected_children"] = 333
    path.write_text(json.dumps(scenario))

    output_dir = tmp_path / "out"
    build_consultation_pack(scenario_dir, TEMPLATES, STYLESHEET, output_dir)
    rendered = (output_dir / "emails" / "official-alert--concise-email.html").read_text()

    assert "Supplied Product Decision: Alert" in rendered
    assert "Modeled exposure at 34 kt is 999 people" in rendered
    assert "Cyclone Aurora &amp; Beacon" in rendered
    assert "Cyclone Aurora & Beacon" not in rendered


def test_generator_rejects_undeclared_or_sensitive_input_fields(tmp_path: Path) -> None:
    scenario_dir = tmp_path / "scenarios"
    scenario_dir.mkdir()
    source = json.loads((SCENARIOS / "official-alert.json").read_text())
    source["recipient_email"] = "private@example.invalid"
    (scenario_dir / "invalid.json").write_text(json.dumps(source))

    with pytest.raises(ConsultationInputError, match="undeclared fields"):
        build_consultation_pack(scenario_dir, TEMPLATES, STYLESHEET, tmp_path / "out")


def test_generated_html_has_accessible_document_structure(tmp_path: Path) -> None:
    build_consultation_pack(SCENARIOS, TEMPLATES, STYLESHEET, tmp_path)

    for path in sorted(tmp_path.glob("*/*.html")):
        html = path.read_text()
        assert '<html lang="en">' in html
        assert html.count("<h1") == 1
        assert "<main" in html
        assert "<header" in html
        assert "<footer" in html
        assert "<caption>" in html
        assert 'aria-label="Consultation status"' in html


def test_screenshot_evidence_matches_sources_and_provenance(tmp_path: Path) -> None:
    manifest = build_consultation_pack(SCENARIOS, TEMPLATES, STYLESHEET, tmp_path)
    source_hashes = {entry["path"]: entry["sha256"] for entry in manifest["outputs"]}
    provenance = json.loads((SCREENSHOT_EVIDENCE / "provenance.json").read_text())

    screenshots = sorted(SCREENSHOT_EVIDENCE.glob("*.png"))
    entries = {entry["path"]: entry for entry in provenance["screenshots"]}
    assert len(screenshots) == 24
    assert set(entries) == {path.name for path in screenshots}
    assert provenance["classification"] == "synthetic_public"
    assert provenance["review_status"] == "local_prepublication_screening_only"

    for screenshot in screenshots:
        entry = entries[screenshot.name]
        assert hashlib.sha256(screenshot.read_bytes()).hexdigest() == entry["sha256"]
        assert source_hashes[entry["source_path"]] == entry["source_sha256"]
        assert entry["embedded_metadata_keys"] == []
        assert entry["device_pixel_ratio"] == 1

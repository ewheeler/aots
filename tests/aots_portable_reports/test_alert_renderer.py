from __future__ import annotations

import json
from pathlib import Path

from aots_portable_reports import dag
from aots_portable_reports.alert_renderer import AlertProseRequest
from aots_portable_reports.alert_renderer import BaselineReplayAlertProseProvider
from aots_portable_reports.alert_renderer import baseline_replay_summary_prose
from aots_portable_reports.alert_renderer import build_alert_claims
from aots_portable_reports.alert_renderer import build_alert_context
from aots_portable_reports.alert_renderer import build_alert_prose_slots
from aots_portable_reports.alert_renderer import compare_alert_output
from aots_portable_reports.alert_renderer import render_alert_html
from aots_portable_reports.models import BaselineManifest
from aots_portable_reports.models import ReportSnapshot
from aots_portable_reports.validation import ValidatedBaseline


FIXTURE_ALERT_CASES = Path(__file__).parents[1] / "fixtures" / "alert_compare_cases"


def test_baseline_replay_summary_prose_extracts_only_summary_paragraph() -> None:
    expected_alert_html = """<html><body>
    <h1>Storm HTML-ONLY - XXX</h1>
    <section><h2>Situation Summary</h2><p>Replay only prose.</p></section>
    <section><h2>Expected Impact - 50kt</h2><p>Snowflake-only population 9999.</p></section>
    </body></html>"""

    assert baseline_replay_summary_prose(expected_alert_html) == "Replay only prose."


def test_baseline_replay_prose_provider_returns_only_bounded_slots() -> None:
    expected_alert_html = """<html><body>
    <h1>Storm HTML-ONLY - XXX</h1>
    <section><h2>Situation Summary</h2><p>Replay only prose.</p></section>
    <section><h2>Expected Impact - 50kt</h2><p>Snowflake-only population 9999.</p></section>
    </body></html>"""

    slots = BaselineReplayAlertProseProvider().provide_prose_slots(
        AlertProseRequest(alert_context={}, expected_alert_html=expected_alert_html)
    )

    assert slots == {"situation_summary": "Replay only prose."}


def test_build_alert_prose_slots_filters_unbounded_provider_output() -> None:
    class UnboundedProvider:
        def provide_prose_slots(self, request: AlertProseRequest) -> dict[str, str]:
            del request
            return {
                "situation_summary": "Provider slot prose.",
                "whole_email_html": "<html><body>unbounded</body></html>",
            }

    slots = build_alert_prose_slots({}, provider=UnboundedProvider())

    assert slots == {"situation_summary": "Provider slot prose."}


def test_dag_defaults_to_baseline_replay_prose_provider() -> None:
    assert isinstance(dag.alert_prose_provider(), BaselineReplayAlertProseProvider)


def test_dag_rendering_uses_provider_slots_not_raw_expected_html(tmp_path: Path) -> None:
    validated_baseline = ValidatedBaseline(
        root=tmp_path,
        manifest=BaselineManifest(
            baseline_version=1,
            country="TST",
            storm="ALPHA",
            forecast_time="2026-01-01T00:00:00Z",
            expected_report_path="expected-report.json",
            expected_alert_path="expected-alert.html",
            artifacts=[],
        ),
        expected_report={},
        expected_alert_html=(
            "<html><body><h1>Storm HTML-ONLY - XXX</h1>"
            "<section><h2>Situation Summary</h2><p>Raw whole-email prose.</p></section>"
            "<section><h2>Expected Impact - 50kt</h2><p>Snowflake-only population 9999.</p></section>"
            "</body></html>"
        ),
    )
    alert_context = build_alert_context(
        ReportSnapshot(
            country="TST",
            storm="ALPHA",
            forecast_time="2026-01-01T00:00:00Z",
            report={"expected_pop": 123},
        )
    )

    class StubProvider:
        def provide_prose_slots(self, request: AlertProseRequest) -> dict[str, str]:
            assert request.expected_alert_html == validated_baseline.expected_alert_html
            assert request.alert_context == alert_context
            return {
                "situation_summary": "Provider slot prose.",
                "whole_email_html": request.expected_alert_html or "",
            }

    prose_slots = dag.alert_prose_slots(validated_baseline, alert_context, StubProvider())
    rendered = dag.rendered_alert_html(validated_baseline, alert_context, prose_slots)

    assert prose_slots == {"situation_summary": "Provider slot prose."}
    assert rendered is not None
    assert "Provider slot prose." in rendered
    assert "Raw whole-email prose." not in rendered
    assert "Snowflake-only population 9999." not in rendered


def test_build_alert_context_and_claims_capture_structured_report_first_facts() -> None:
    report_snapshot = ReportSnapshot(
        country="TST",
        storm="ALPHA",
        forecast_time="2026-01-01T00:00:00Z",
        report={
            "expected_pop": 123,
            "expected_children": 45,
            "expected_hcs": 6,
            "expected_schools": 9,
            "expected_shelters": 2,
            "expected_wash": 7,
            "E_people_in_need": 90,
            "E_children_in_need": 30,
            "expected_pop_34": 200,
            "expected_children_34": 80,
            "expected_pop_64": 40,
            "expected_children_64": 15,
            "rows_admins_pop_total": [
                {"name": "North District", "50": 70, "people_in_need": 12},
                {"name": "South District", "50": 40, "people_in_need": 9},
            ],
        },
    )

    alert_context = build_alert_context(report_snapshot)
    alert_claims = build_alert_claims(alert_context)

    assert alert_context["identity"] == {
        "country": "TST",
        "storm": "ALPHA",
        "forecast_time": "2026-01-01T00:00:00Z",
    }
    assert alert_context["main_threshold"] == {"wind_threshold": 50, "label": "50kt"}
    assert alert_context["impact_totals"] == {
        "population": 123,
        "children": 45,
        "schools": 9,
        "health_centers": 6,
        "shelters": 2,
        "wash": 7,
    }
    assert alert_context["people_in_need"] == {"population": 90, "children": 30}
    assert alert_context["top_admin_areas"] == [
        {"name": "North District", "population": 70, "people_in_need": 12},
        {"name": "South District", "population": 40, "people_in_need": 9},
    ]
    assert alert_context["cross_threshold_rows"] == [
        {"wind_threshold": 34, "population": 200, "children": 80},
        {"wind_threshold": 64, "population": 40, "children": 15},
    ]
    assert alert_context["required_caveats"] == [
        {
            "id": "ai_probabilistic_model_outputs",
            "text": "AI system based on probabilistic model outputs",
            "provenance_labels": ["inferred"],
        }
    ]
    assert alert_context["provenance_labels"] == ["data", "inferred"]

    assert alert_claims["identity"] == alert_context["identity"]
    assert alert_claims["main_threshold"] == alert_context["main_threshold"]
    assert alert_claims["impact_totals"] == [
        {"metric": "population", "value": 123, "provenance_labels": ["data"]},
        {"metric": "children", "value": 45, "provenance_labels": ["data"]},
        {"metric": "schools", "value": 9, "provenance_labels": ["data"]},
        {"metric": "health_centers", "value": 6, "provenance_labels": ["data"]},
        {"metric": "shelters", "value": 2, "provenance_labels": ["data"]},
        {"metric": "wash", "value": 7, "provenance_labels": ["data"]},
    ]
    assert alert_claims["people_in_need_values"] == [
        {"metric": "population", "value": 90, "provenance_labels": ["inferred"]},
        {"metric": "children", "value": 30, "provenance_labels": ["inferred"]},
    ]
    assert alert_claims["top_admin_areas"] == [
        {
            "name": "North District",
            "population": 70,
            "people_in_need": 12,
            "provenance_labels": ["data", "inferred"],
        },
        {
            "name": "South District",
            "population": 40,
            "people_in_need": 9,
            "provenance_labels": ["data", "inferred"],
        },
    ]
    assert alert_claims["cross_threshold_rows"] == [
        {"wind_threshold": 34, "population": 200, "children": 80, "provenance_labels": ["data"]},
        {"wind_threshold": 64, "population": 40, "children": 15, "provenance_labels": ["data"]},
    ]
    assert alert_claims["required_caveats"] == alert_context["required_caveats"]
    assert alert_claims["provenance_labels"] == ["data", "inferred"]


def test_compare_alert_output_passes_for_committed_caveat_fixture() -> None:
    alert_claims = json.loads((FIXTURE_ALERT_CASES / "claims.json").read_text())
    rendered_alert_html = (FIXTURE_ALERT_CASES / "rendered_with_caveat.html").read_text()

    comparison = compare_alert_output(alert_claims, rendered_alert_html)

    assert comparison.status == "passed"
    assert comparison.failures == []


def test_compare_alert_output_fails_for_committed_factual_mismatch_fixture() -> None:
    alert_claims = json.loads((FIXTURE_ALERT_CASES / "claims.json").read_text())
    rendered_alert_html = (FIXTURE_ALERT_CASES / "rendered_factual_mismatch.html").read_text()

    comparison = compare_alert_output(alert_claims, rendered_alert_html)

    assert comparison.status == "failed"
    assert [failure.code for failure in comparison.failures] == ["missing_alert_identity"]


def test_compare_alert_output_passes_when_prose_and_markup_vary_but_claim_evidence_matches() -> None:
    alert_claims = {
        "identity": {"storm": "ALPHA", "country": "TST", "forecast_time": "2026-01-01T00:00:00Z"},
        "main_threshold": {"wind_threshold": 50, "label": "50kt"},
        "impact_totals": [{"metric": "population", "value": 123, "provenance_labels": ["data"]}],
        "people_in_need_values": [{"metric": "population", "value": 90, "provenance_labels": ["inferred"]}],
        "top_admin_areas": [
            {
                "name": "North District",
                "population": 70,
                "people_in_need": 12,
                "provenance_labels": ["data", "inferred"],
            }
        ],
        "cross_threshold_rows": [
            {"wind_threshold": 34, "population": 200, "children": 80, "provenance_labels": ["data"]}
        ],
        "required_caveats": [
            {
                "id": "ai_probabilistic_model_outputs",
                "text": "AI system based on probabilistic model outputs",
                "provenance_labels": ["inferred"],
            }
        ],
        "provenance_labels": ["data", "inferred"],
    }
    rendered_alert_html = """<!doctype html>
    <html lang=\"en\"><body>
      <section>
        <h2>Situation Summary</h2>
        <p>Fresh wording that shares no baseline prose.</p>
      </section>
      <section>
        <table>
          <caption>Key alert facts derived from structured report inputs.</caption>
          <thead><tr><th>Fact</th><th>Value</th></tr></thead>
          <tbody>
            <tr><th>Storm</th><td><strong>ALPHA</strong></td></tr>
            <tr><th>Country</th><td>TST</td></tr>
            <tr><th>Forecast Issued</th><td><time datetime=\"2026-01-01T00:00:00Z\">2026-01-01T00:00:00Z</time></td></tr>
            <tr><th>Alert Threshold</th><td><span>50kt</span></td></tr>
          </tbody>
        </table>
      </section>
      <section>
        <table>
          <caption>Expected impact totals for the 50kt threshold.</caption>
          <thead><tr><th>Metric</th><th>Value</th><th>Provenance</th></tr></thead>
          <tbody><tr><th>Population</th><td>123</td><td><code>data</code></td></tr></tbody>
        </table>
      </section>
      <section>
        <table>
          <caption>Inferred people-in-need values used for review.</caption>
          <thead><tr><th>Metric</th><th>Value</th><th>Provenance</th></tr></thead>
          <tbody><tr><th>Population</th><td>90</td><td><code>inferred</code></td></tr></tbody>
        </table>
      </section>
      <section>
        <table>
          <caption>Administrative areas with the highest 50kt population exposure.</caption>
          <thead><tr><th>Area</th><th>Population</th><th>People in Need</th><th>Provenance</th></tr></thead>
          <tbody><tr><th>North District</th><td>70</td><td>12</td><td><code>data</code><code>inferred</code></td></tr></tbody>
        </table>
      </section>
      <section>
        <table>
          <caption>Population and children exposed across wind thresholds.</caption>
          <thead><tr><th>Wind Threshold</th><th>Population</th><th>Children</th><th>Provenance</th></tr></thead>
          <tbody><tr><th>34kt</th><td>200</td><td>80</td><td><code>data</code></td></tr></tbody>
        </table>
      </section>
      <section>
        <h2>Required Caveats</h2>
        <ul><li><span>AI system based on probabilistic model outputs</span> <code>inferred</code></li></ul>
      </section>
      <section>
        <h2>Provenance Labels</h2>
        <ul><li><code>data</code></li><li><code>inferred</code></li></ul>
      </section>
    </body></html>"""

    comparison = compare_alert_output(alert_claims, rendered_alert_html)

    assert comparison.status == "passed"
    assert comparison.failures == []


def test_compare_alert_output_fails_when_expected_impact_total_claim_is_missing_from_presentation() -> None:
    alert_claims = {
        "identity": {"storm": "ALPHA", "country": "TST", "forecast_time": "2026-01-01T00:00:00Z"},
        "main_threshold": {"wind_threshold": 50, "label": "50kt"},
        "impact_totals": [{"metric": "population", "value": 123, "provenance_labels": ["data"]}],
        "required_caveats": [{"text": "AI system based on probabilistic model outputs", "provenance_labels": ["inferred"]}],
        "provenance_labels": ["data", "inferred"],
    }
    rendered_alert_html = """<!doctype html>
    <html lang=\"en\"><body>
      <table>
        <caption>Key alert facts derived from structured report inputs.</caption>
        <thead><tr><th>Fact</th><th>Value</th></tr></thead>
        <tbody>
          <tr><th>Storm</th><td>ALPHA</td></tr>
          <tr><th>Country</th><td>TST</td></tr>
          <tr><th>Forecast Issued</th><td>2026-01-01T00:00:00Z</td></tr>
          <tr><th>Alert Threshold</th><td>50kt</td></tr>
        </tbody>
      </table>
      <table>
        <caption>Expected impact totals for the 50kt threshold.</caption>
        <thead><tr><th>Metric</th><th>Value</th><th>Provenance</th></tr></thead>
        <tbody><tr><th>Population</th><td>999</td><td><code>data</code></td></tr></tbody>
      </table>
      <ul><li>AI system based on probabilistic model outputs <code>inferred</code></li></ul>
      <ul><li><code>data</code></li><li><code>inferred</code></li></ul>
    </body></html>"""

    comparison = compare_alert_output(alert_claims, rendered_alert_html)

    assert comparison.status == "failed"
    assert [failure.code for failure in comparison.failures] == ["missing_impact_total_claim"]


def test_compare_alert_output_fails_when_top_admin_area_claim_differs_from_presentation() -> None:
    alert_claims = {
        "identity": {"storm": "ALPHA", "country": "TST"},
        "top_admin_areas": [
            {
                "name": "North District",
                "population": 70,
                "people_in_need": 12,
                "provenance_labels": ["data", "inferred"],
            }
        ],
        "required_caveats": [{"text": "AI system based on probabilistic model outputs", "provenance_labels": ["inferred"]}],
        "provenance_labels": ["data", "inferred"],
    }
    rendered_alert_html = """<!doctype html>
    <html lang=\"en\"><body>
      <h1>Storm ALPHA - TST</h1>
      <table>
        <caption>Administrative areas with the highest 50kt population exposure.</caption>
        <thead><tr><th>Area</th><th>Population</th><th>People in Need</th><th>Provenance</th></tr></thead>
        <tbody><tr><th>North District</th><td>55</td><td>12</td><td><code>data</code><code>inferred</code></td></tr></tbody>
      </table>
      <p>AI system based on probabilistic model outputs</p>
      <code>data</code><code>inferred</code>
    </body></html>"""

    comparison = compare_alert_output(alert_claims, rendered_alert_html)

    assert comparison.status == "failed"
    assert [failure.code for failure in comparison.failures] == ["missing_top_admin_area_claim"]


def test_compare_alert_output_fails_when_threshold_exposure_claim_differs_from_presentation() -> None:
    alert_claims = {
        "identity": {"storm": "ALPHA", "country": "TST"},
        "cross_threshold_rows": [
            {"wind_threshold": 34, "population": 200, "children": 80, "provenance_labels": ["data"]}
        ],
        "required_caveats": [{"text": "AI system based on probabilistic model outputs", "provenance_labels": ["inferred"]}],
        "provenance_labels": ["data", "inferred"],
    }
    rendered_alert_html = """<!doctype html>
    <html lang=\"en\"><body>
      <h1>Storm ALPHA - TST</h1>
      <table>
        <caption>Population and children exposed across wind thresholds.</caption>
        <thead><tr><th>Wind Threshold</th><th>Population</th><th>Children</th><th>Provenance</th></tr></thead>
        <tbody><tr><th>34kt</th><td>200</td><td>70</td><td><code>data</code></td></tr></tbody>
      </table>
      <p>AI system based on probabilistic model outputs</p>
      <code>data</code><code>inferred</code>
    </body></html>"""

    comparison = compare_alert_output(alert_claims, rendered_alert_html)

    assert comparison.status == "failed"
    assert [failure.code for failure in comparison.failures] == ["missing_threshold_exposure_claim"]


def test_render_alert_html_emits_reviewable_hybrid_sections_tables_and_labels() -> None:
    alert_context = build_alert_context(
        ReportSnapshot(
            country="TST",
            storm="ALPHA",
            forecast_time="2026-01-01T00:00:00Z",
            report={
                "expected_pop": 123,
                "expected_children": 45,
                "expected_schools": 9,
                "expected_hcs": 6,
                "expected_shelters": 2,
                "expected_wash": 7,
                "E_people_in_need": 90,
                "E_children_in_need": 30,
                "expected_pop_34": 200,
                "expected_children_34": 80,
                "expected_pop_64": 40,
                "expected_children_64": 15,
                "rows_admins_pop_total": [
                    {"name": "North District", "50": 70, "people_in_need": 12},
                    {"name": "South District", "50": 40, "people_in_need": 9},
                ],
            },
        )
    )

    rendered = render_alert_html(alert_context, prose_slots={"situation_summary": "Provider slot prose."})

    for heading in [
        "Situation Summary",
        "Alert Facts",
        "Expected Impact Totals",
        "People in Need",
        "Most Affected Administrative Areas",
        "Threshold Exposure",
        "Required Caveats",
        "Provenance Labels",
    ]:
        assert f">{heading}<" in rendered

    assert rendered.index("Situation Summary") < rendered.index("Alert Facts")
    assert rendered.index("Alert Facts") < rendered.index("Expected Impact Totals")
    assert rendered.index("Expected Impact Totals") < rendered.index("Most Affected Administrative Areas")
    assert rendered.index("Most Affected Administrative Areas") < rendered.index("Threshold Exposure")
    assert rendered.index("Threshold Exposure") < rendered.index("Required Caveats")
    assert "Provider slot prose." in rendered
    assert '<th scope="col">Fact</th>' in rendered
    assert '<th scope="col">Area</th>' in rendered
    assert '<th scope="col">Wind Threshold</th>' in rendered
    assert '<th scope="row">Storm</th><td>ALPHA</td>' in rendered
    assert '<th scope="row">Forecast Issued</th><td><time datetime="2026-01-01T00:00:00Z">2026-01-01T00:00:00Z</time></td>' in rendered
    assert '<th scope="row">Population</th><td>123</td><td><code>data</code></td>' in rendered
    assert '<th scope="row">Population</th><td>90</td><td><code>inferred</code></td>' in rendered
    assert '<th scope="row">North District</th><td>70</td><td>12</td><td><code>data</code> <code>inferred</code></td>' in rendered
    assert '<th scope="row">34kt</th><td>200</td><td>80</td><td><code>data</code></td>' in rendered
    assert '<li><span>AI system based on probabilistic model outputs</span> <code>inferred</code></li>' in rendered
    assert '<li><code>data</code></li>' in rendered
    assert '<li><code>inferred</code></li>' in rendered

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
from aots_portable_reports.alert_renderer import build_alert_visual_context
from aots_portable_reports.alert_renderer import compare_alert_output
from aots_portable_reports.alert_renderer import render_alert_visual_assets
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


def test_baseline_replay_summary_prose_drops_table_and_list_like_noise() -> None:
    expected_alert_html = """<html><body>
    <section><h2>Situation Summary</h2>
      <p>Storm-force winds may affect exposed communities.</p>
      <table><tr><th>Metric</th><th>Value</th></tr><tr><td>Population</td><td>9999</td></tr></table>
      <ul><li>Population: 9999</li><li>Children: 888</li></ul>
    </section>
    </body></html>"""

    assert baseline_replay_summary_prose(expected_alert_html) == "Storm-force winds may affect exposed communities."


def test_baseline_replay_summary_prose_removes_provenance_tokens_and_caps_length() -> None:
    expected_alert_html = """<html><body>
    <section><h2>Situation Summary</h2>
      <p>Storm Melissa threatens 236,621 data people in Jamaica. Saint James carries 34.4% data of national risk. This is an increase of +77,729 inferred people. This fourth sentence should move back to structured tables.</p>
    </section>
    </body></html>"""

    assert baseline_replay_summary_prose(expected_alert_html) == (
        "Storm Melissa threatens 236,621 people in Jamaica. "
        "Saint James carries 34.4% of national risk. "
        "This is an increase of +77,729 people."
    )


def test_baseline_replay_prose_provider_returns_snowflake_aligned_bounded_slots() -> None:
    expected_alert_html = """<html><body>
    <h1>Storm HTML-ONLY - XXX</h1>
    <section><h2>Situation Summary</h2><p>Summary prose.</p></section>
    <section><h2>Situation Overview</h2><p>Narrative prose.</p></section>
    <section><h2>Forecast Shift</h2><p>Shift prose.</p></section>
    <section><h2>Oscillation Notice</h2><p>Oscillation prose.</p></section>
    </body></html>"""

    slots = BaselineReplayAlertProseProvider().provide_prose_slots(
        AlertProseRequest(alert_context={}, expected_alert_html=expected_alert_html)
    )

    assert slots == {
        "summary": "Summary prose.",
        "situation_summary": "Summary prose.",
        "narrative": "Narrative prose.",
        "shift": "Shift prose.",
        "oscillation": "Oscillation prose.",
    }


def test_build_alert_prose_slots_filters_unbounded_provider_output() -> None:
    class UnboundedProvider:
        def provide_prose_slots(self, request: AlertProseRequest) -> dict[str, str]:
            del request
            return {
                "summary": "Provider slot prose.",
                "narrative": "Narrative slot prose.",
                "shift": "Shift slot prose.",
                "oscillation": "Oscillation slot prose.",
                "whole_email_html": "<html><body>unbounded</body></html>",
            }

    slots = build_alert_prose_slots({}, provider=UnboundedProvider())

    assert slots == {
        "summary": "Provider slot prose.",
        "situation_summary": "Provider slot prose.",
        "narrative": "Narrative slot prose.",
        "shift": "Shift slot prose.",
        "oscillation": "Oscillation slot prose.",
    }


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
                "summary": "Provider slot prose.",
                "narrative": "Narrative slot prose.",
                "shift": "Shift slot prose.",
                "oscillation": "Oscillation slot prose.",
                "whole_email_html": request.expected_alert_html or "",
            }

    prose_slots = dag.alert_prose_slots(validated_baseline, alert_context, StubProvider())
    rendered = dag.rendered_alert_html(validated_baseline, alert_context, prose_slots, [])

    assert prose_slots == {
        "summary": "Provider slot prose.",
        "situation_summary": "Provider slot prose.",
        "narrative": "Narrative slot prose.",
        "shift": "Shift slot prose.",
        "oscillation": "Oscillation slot prose.",
    }
    assert rendered is not None
    assert "Provider slot prose." in rendered
    assert "Narrative slot prose." in rendered
    assert "Shift slot prose." in rendered
    assert "Oscillation slot prose." in rendered
    assert "Raw whole-email prose." not in rendered
    assert "Snowflake-only population 9999." not in rendered


def test_render_alert_html_follows_snowflake_aligned_section_order_and_visual_hierarchy() -> None:
    alert_context = build_alert_context(
        ReportSnapshot(
            country="TST",
            storm="ALPHA",
            forecast_time="2026-01-01T00:00:00Z",
            report={
                "expected_pop": 123,
                "expected_children": 45,
                "E_people_in_need": 90,
                "expected_pop_34": 200,
                "expected_children_34": 80,
                "rows_admins_pop_total": [{"name": "North District", "50": 70}],
            },
        )
    )
    visual_assets = [
        {
            "kind": "ensemble_probability",
            "threshold": 50,
            "status": "rendered",
            "data_uri": "data:image/png;base64,AAAA",
            "alt_text": "Wind exposure probability map (50kt)",
            "caption": "Probability of wind exposure at the 50 kt threshold.",
            "provenance_labels": ["data"],
        },
        {
            "kind": "ensemble_probability",
            "threshold": 34,
            "status": "rendered",
            "data_uri": "data:image/png;base64,BBBB",
            "alt_text": "Wind exposure probability map (34kt)",
            "caption": "Probability of wind exposure at the 34 kt threshold.",
            "provenance_labels": ["data"],
        },
        {
            "kind": "admin_choropleth",
            "threshold": 50,
            "status": "rendered",
            "data_uri": "data:image/png;base64,CCCC",
            "alt_text": "Admin impact map",
            "caption": "Expected children at risk by administrative area at the 50 kt threshold.",
            "provenance_labels": ["data", "inferred"],
        },
        {
            "kind": "impact_evolution",
            "threshold": 50,
            "status": "rendered",
            "data_uri": "data:image/png;base64,DDDD",
            "alt_text": "Forecast evolution chart",
            "caption": "Total population at risk at storm-force winds (50 kt) across recent forecast runs.",
            "provenance_labels": ["data"],
        },
        {
            "kind": "population_composition",
            "threshold": 50,
            "status": "rendered",
            "data_uri": "data:image/png;base64,EEEE",
            "alt_text": "Population composition donut chart",
            "caption": "Composition of total population at risk at the 50 kt threshold.",
            "provenance_labels": ["data"],
        },
    ]

    html = render_alert_html(
        alert_context,
        prose_slots={
            "summary": "Summary slot.",
            "narrative": "Narrative slot.",
            "shift": "Shift slot.",
            "oscillation": "Oscillation slot.",
        },
        visual_assets=visual_assets,
    )

    expected_order = [
        "Active Forecast",
        "Situation Summary",
        "Timing &amp; Forecast Details",
        "Situation Overview",
        "Expected Impact",
        "Impact Composition",
        "Wind Exposure Probability - 50kt",
        "Additional Wind Probability Views",
        "Expected Children at Risk by Admin Area",
        "Forecast Shift",
        "Most Affected Administrative Areas",
        "Forecast Evolution - Expected People at Risk",
        "Oscillation Notice",
        "Required Caveats",
        "Provenance Labels",
    ]
    positions = [html.index(heading) for heading in expected_order]
    assert positions == sorted(positions)
    assert "alert-urgency-strip" in html
    assert "alert-card" in html
    assert "--aots-blue:#1CABE2" in html
    assert "Ahead of the Storm &mdash; Storm Alert" in html
    assert "background:var(--aots-blue)" in html
    assert html.index("Wind exposure probability map (50kt)") < html.index("Wind exposure probability map (34kt)")


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
            "expected_schools_34": 3,
            "expected_hcs_34": 2,
            "expected_shelters_34": 1,
            "expected_wash_34": 4,
            "expected_pop_64": 40,
            "expected_children_64": 15,
            "expected_schools_64": 1,
            "expected_hcs_64": 1,
            "expected_shelters_64": 0,
            "expected_wash_64": 1,
            "rows_admins_pop_total": [
                {"name": "South District", "50": 40, "people_in_need": 9},
                {"name": "North District", "50": 70, "people_in_need": 12},
            ],
            "rows_schools_winds": [{"name": "North District", "50": 5}, {"name": "South District", "50": 3}],
            "rows_hcs_winds": [{"name": "North District", "50": 2}, {"name": "South District", "50": 1}],
            "rows_shelters_winds": [{"name": "North District", "50": 1}, {"name": "South District", "50": 0}],
            "rows_wash_winds": [{"name": "North District", "50": 4}, {"name": "South District", "50": 2}],
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
        {"name": "North District", "population": 70, "people_in_need": 12, "schools": 5, "health_centers": 2, "shelters": 1, "wash": 4},
        {"name": "South District", "population": 40, "people_in_need": 9, "schools": 3, "health_centers": 1, "shelters": 0, "wash": 2},
    ]
    assert alert_context["cross_threshold_rows"] == [
        {"wind_threshold": 34, "population": 200, "children": 80, "schools": 3, "health_centers": 2, "shelters": 1, "wash": 4},
        {"wind_threshold": 64, "population": 40, "children": 15, "schools": 1, "health_centers": 1, "shelters": 0, "wash": 1},
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
            "schools": 5,
            "health_centers": 2,
            "shelters": 1,
            "wash": 4,
            "provenance_labels": ["data", "inferred"],
        },
        {
            "name": "South District",
            "population": 40,
            "people_in_need": 9,
            "schools": 3,
            "health_centers": 1,
            "shelters": 0,
            "wash": 2,
            "provenance_labels": ["data", "inferred"],
        },
    ]
    assert alert_claims["cross_threshold_rows"] == [
        {"wind_threshold": 34, "population": 200, "children": 80, "schools": 3, "health_centers": 2, "shelters": 1, "wash": 4, "provenance_labels": ["data"]},
        {"wind_threshold": 64, "population": 40, "children": 15, "schools": 1, "health_centers": 1, "shelters": 0, "wash": 1, "provenance_labels": ["data"]},
    ]
    assert alert_claims["required_caveats"] == alert_context["required_caveats"]
    assert alert_claims["provenance_labels"] == ["data", "inferred"]


def test_build_alert_visual_context_uses_structured_sources_not_expected_html() -> None:
    report_snapshot = ReportSnapshot(
        country="TST",
        storm="ALPHA",
        forecast_time="2026-01-01T00:00:00Z",
        report={"expected_pop": 100, "expected_children": 35, "E_people_in_need": 50, "E_children_in_need": 20},
    )
    source_artifacts = {
        "admin_geometry": [
            {"name": "North District", "geojson": '{"type":"Polygon","coordinates":[[[0,0],[1,0],[1,1],[0,1],[0,0]]]}', "clon": 0.5, "clat": 0.5},
        ],
        "admin_50": [{"name": "North District", "E_SCHOOL_AGE_POPULATION": 4, "E_INFANT_POPULATION": 2, "E_ADOLESCENT_POPULATION": 3}],
        "tiles_50": [{"ZONE_ID": "0", "PROBABILITY": 0.7}],
        "raw_tracks": [{"ENSEMBLE_MEMBER": "m1", "LEAD_TIME": 0, "LONGITUDE": 0.1, "LATITUDE": 0.2}],
        "impact_evolution_50": [{"forecast_date": "20260101000000", "pop": 100, "infant": 10, "school_age": 20, "adolescent": 5}],
        "alert_timing": [
            {"wind_threshold": 34, "consensus_impact_hours": 6, "consensus_impact_time": "2026-01-01 06:00", "earliest_impact_hours": 6, "latest_impact_hours": 18, "members_hitting": 51, "total_members": 51},
            {"wind_threshold": 50, "consensus_impact_hours": 12, "consensus_impact_time": "2026-01-01 12:00", "earliest_impact_hours": 6, "latest_impact_hours": 24, "members_hitting": 40, "total_members": 51},
        ],
    }

    visual_context = build_alert_visual_context(report_snapshot, source_artifacts=source_artifacts)

    assert visual_context["admin_choropleth"]["available"] is True
    assert visual_context["admin_choropleth"]["rows"][0]["children"] == 9
    assert visual_context["ensemble_probability"]["50"]["available"] is True
    assert visual_context["ensemble_probability"]["50"]["tiles"] == [{"z": "0", "p": 0.7}]
    assert visual_context["impact_evolution"]["available"] is True
    assert visual_context["impact_evolution"]["rows"][0]["population"] == 100
    assert visual_context["impact_composition"]["population"]["available"] is True
    assert visual_context["impact_composition"]["population"]["values"] == {"children": 35.0, "other_population": 65.0}
    assert visual_context["impact_composition"]["people_in_need"]["values"] == {"children_in_need": 20.0, "other_people_in_need": 30.0}
    assert visual_context["timing_rows"][1]["wind_threshold"] == 50
    assert visual_context["timing_rows"][1]["members_hitting"] == 40


def test_render_alert_html_includes_threshold_arrival_table_when_timing_context_exists() -> None:
    alert_context = build_alert_context(ReportSnapshot(country="TST", storm="ALPHA", forecast_time="2026-01-01T00:00:00Z", report={}))
    alert_context["timing_rows"] = [
        {"wind_threshold": 34, "consensus_impact_hours": 6, "consensus_impact_time": "2026-01-01 06:00", "earliest_impact_hours": 6, "latest_impact_hours": 18, "members_hitting": 51, "total_members": 51},
        {"wind_threshold": 50, "consensus_impact_hours": 12, "consensus_impact_time": "2026-01-01 12:00", "earliest_impact_hours": 6, "latest_impact_hours": 24, "members_hitting": 40, "total_members": 51},
    ]

    rendered = render_alert_html(alert_context)

    assert "Expected wind arrival by threshold." in rendered
    assert "Storm Force (34kt)" in rendered
    assert "Strong Storm Force (50kt)" in rendered
    assert "40/51 (78%)" in rendered


def test_render_alert_html_shows_admin_delta_only_when_non_trivial_previous_change_exists() -> None:
    alert_context = build_alert_context(
        ReportSnapshot(
            country="TST",
            storm="ALPHA",
            forecast_time="2026-01-01T00:00:00Z",
            report={
                "rows_admins_pop_total": [
                    {"name": "North District", "50": 70, "change_50": 12},
                    {"name": "South District", "50": 40, "change_50": 40},
                ]
            },
        )
    )

    rendered = render_alert_html(alert_context)

    assert "North District</th><td>70 <span" in rendered
    assert "▲ +12" in rendered
    assert "South District</th><td>40 <span" not in rendered


def test_render_alert_visual_assets_writes_png_ready_inline_assets() -> None:
    visual_context = {
        "impact_evolution": {
            "available": True,
            "rows": [
                {"label": "Jan 1 00Z", "population": 100, "infant": 10, "school_age": 20, "adolescent": 5},
                {"label": "Jan 1 06Z", "population": 130, "infant": 11, "school_age": 25, "adolescent": 6},
            ],
        }
    }

    assets = render_alert_visual_assets(visual_context)

    evolution = next(asset for asset in assets if asset["kind"] == "impact_evolution")
    assert evolution["filename"] == "impact-evolution-50kt.png"
    assert evolution["status"] == "rendered"
    assert evolution["mime_type"] == "image/png"
    assert evolution["data_uri"].startswith("data:image/png;base64,")
    assert evolution["png_base64"]


def test_render_alert_visual_assets_includes_admin_choropleth_png_when_geometry_exists() -> None:
    visual_context = {
        "admin_choropleth": {
            "available": True,
            "rows": [
                {
                    "name": "North District",
                    "geojson": '{"type":"Polygon","coordinates":[[[0,0],[1,0],[1,1],[0,1],[0,0]]]}',
                    "clon": 0.5,
                    "clat": 0.5,
                    "children": 9,
                }
            ],
        }
    }

    assets = render_alert_visual_assets(visual_context)

    admin = next(asset for asset in assets if asset["kind"] == "admin_choropleth")
    assert admin["filename"] == "admin-choropleth-50kt.png"
    assert admin["alt_text"] == "Admin impact map"
    assert admin["data_uri"].startswith("data:image/png;base64,")


def test_render_alert_visual_assets_includes_ensemble_probability_png_when_tiles_exist() -> None:
    visual_context = {
        "ensemble_probability": {
            "50": {
                "available": True,
                "tiles": [{"z": "0", "p": 0.7}],
                "tracks": [
                    {"m": "m1", "lt": 0, "lon": 0.1, "lat": 0.2},
                    {"m": "m1", "lt": 6, "lon": 0.2, "lat": 0.3},
                ],
            }
        }
    }

    assets = render_alert_visual_assets(visual_context)

    ensemble = next(asset for asset in assets if asset["kind"] == "ensemble_probability")
    assert ensemble["filename"] == "ensemble-probability-50kt.png"
    assert ensemble["alt_text"] == "Wind exposure probability map (50kt)"
    assert ensemble["data_uri"].startswith("data:image/png;base64,")


def test_render_alert_visual_assets_includes_donut_pngs() -> None:
    visual_context = {
        "impact_composition": {
            "population": {"available": True, "values": {"children": 35, "other_population": 65}},
            "people_in_need": {"available": True, "values": {"children_in_need": 20, "other_people_in_need": 30}},
        },
    }

    assets = render_alert_visual_assets(visual_context)

    filenames = {asset["filename"] for asset in assets}
    assert "population-composition-50kt.png" in filenames
    assert "people-in-need-composition-50kt.png" in filenames
    for asset in assets:
        assert asset["data_uri"].startswith("data:image/png;base64,")


def test_alert_claims_include_visual_asset_claims_when_visual_context_has_source_data() -> None:
    alert_context = {
        "identity": {"storm": "ALPHA", "country": "TST"},
        "visual_context": {
            "impact_composition": {
                "population": {"available": True, "values": {"children": 35, "other_population": 65}},
                "people_in_need": {"available": True, "values": {"children_in_need": 20, "other_people_in_need": 30}},
            },
            "impact_evolution": {"available": True, "threshold": 50, "rows": [{"population": 100}]},
            "admin_choropleth": {"available": True, "threshold": 50, "rows": [{"name": "North"}]},
            "ensemble_probability": {"50": {"available": True, "threshold": 50, "tiles": [{"z": "0", "p": 0.7}]}, "34": {"available": False}},
        },
    }

    claims = build_alert_claims(alert_context)

    assert claims["visual_assets"] == [
        {
            "kind": "population_composition",
            "threshold": 50,
            "alt_text": "Population composition donut chart",
            "caption": "Composition of total population at risk at the 50 kt threshold.",
        },
        {
            "kind": "people_in_need_composition",
            "threshold": 50,
            "alt_text": "People in need composition donut chart",
            "caption": "Composition of people in need at the 50 kt threshold.",
        },
        {
            "kind": "impact_evolution",
            "threshold": 50,
            "alt_text": "Forecast evolution chart",
            "caption": "Total population at risk at storm-force winds (50 kt) across recent forecast runs.",
        },
        {
            "kind": "admin_choropleth",
            "threshold": 50,
            "alt_text": "Admin impact map",
            "caption": "Expected children at risk by administrative area at the 50 kt threshold.",
        },
        {
            "kind": "ensemble_probability",
            "threshold": 50,
            "alt_text": "Wind exposure probability map (50kt)",
            "caption": "Probability of wind exposure at the 50 kt threshold.",
        },
    ]


def test_compare_alert_output_fails_when_required_visual_asset_is_missing_from_presentation() -> None:
    alert_claims = {
        "identity": {"storm": "ALPHA", "country": "TST"},
        "required_caveats": [{"text": "AI system based on probabilistic model outputs", "provenance_labels": ["inferred"]}],
        "provenance_labels": ["data", "inferred"],
        "visual_assets": [
            {
                "kind": "impact_evolution",
                "threshold": 50,
                "alt_text": "Forecast evolution chart",
                "caption": "Total population at risk at storm-force winds (50 kt) across recent forecast runs.",
            }
        ],
    }
    rendered_alert_html = """<!doctype html><html><body>
      <h1>Storm ALPHA - TST</h1>
      <p>AI system based on probabilistic model outputs</p>
      <code>data</code><code>inferred</code>
    </body></html>"""

    comparison = compare_alert_output(alert_claims, rendered_alert_html)

    assert comparison.status == "failed"
    assert [failure.code for failure in comparison.failures] == ["missing_alert_visual_asset"]


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
        <thead><tr><th>Area</th><th>Population</th><th>People in Need</th><th>Schools</th><th>Health Centers</th><th>Shelters</th><th>WASH</th><th>Provenance</th></tr></thead>
        <tbody><tr><th>North District</th><td>70</td><td>12</td><td>5</td><td>2</td><td>1</td><td>4</td><td><code>data</code><code>inferred</code></td></tr></tbody>
        </table>
      </section>
      <section>
        <table>
          <caption>Population and children exposed across wind thresholds.</caption>
          <thead><tr><th>Wind Threshold</th><th>Population</th><th>Children</th><th>Schools</th><th>Health Centers</th><th>Shelters</th><th>WASH</th><th>Provenance</th></tr></thead>
          <tbody><tr><th>34kt</th><td>200</td><td>80</td><td>3</td><td>2</td><td>1</td><td>4</td><td><code>data</code></td></tr></tbody>
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
            {"wind_threshold": 34, "population": 200, "children": 80, "schools": 3, "health_centers": 2, "shelters": 1, "wash": 4, "provenance_labels": ["data"]}
        ],
        "required_caveats": [{"text": "AI system based on probabilistic model outputs", "provenance_labels": ["inferred"]}],
        "provenance_labels": ["data", "inferred"],
    }
    rendered_alert_html = """<!doctype html>
    <html lang=\"en\"><body>
      <h1>Storm ALPHA - TST</h1>
      <table>
        <caption>Population and children exposed across wind thresholds.</caption>
          <thead><tr><th>Wind Threshold</th><th>Population</th><th>Children</th><th>Schools</th><th>Health Centers</th><th>Shelters</th><th>WASH</th><th>Provenance</th></tr></thead>
          <tbody><tr><th>34kt</th><td>200</td><td>70</td><td>3</td><td>2</td><td>1</td><td>4</td><td><code>data</code></td></tr></tbody>
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
                "expected_schools_34": 3,
                "expected_hcs_34": 2,
                "expected_shelters_34": 1,
                "expected_wash_34": 4,
                "expected_pop_64": 40,
                "expected_children_64": 15,
                "rows_admins_pop_total": [
                    {"name": "North District", "50": 70, "people_in_need": 12},
                    {"name": "South District", "50": 40, "people_in_need": 9},
                ],
                "rows_schools_winds": [{"name": "North District", "50": 5}],
                "rows_hcs_winds": [{"name": "North District", "50": 2}],
                "rows_shelters_winds": [{"name": "North District", "50": 1}],
                "rows_wash_winds": [{"name": "North District", "50": 4}],
            },
        )
    )

    rendered = render_alert_html(alert_context, prose_slots={"situation_summary": "Provider slot prose."})

    assert "Active Forecast" in rendered
    for heading in [
        "Situation Summary",
        "Timing &amp; Forecast Details",
        "Situation Overview",
        "Expected Impact",
        "Most Affected Administrative Areas",
        "Threshold Exposure",
        "Required Caveats",
        "Provenance Labels",
    ]:
        assert f">{heading}<" in rendered

    assert rendered.index("Situation Summary") < rendered.index("Timing &amp; Forecast Details")
    assert rendered.index("Timing &amp; Forecast Details") < rendered.index("Situation Overview")
    assert rendered.index("Situation Overview") < rendered.index("Expected Impact")
    assert rendered.index("Expected Impact") < rendered.index("Threshold Exposure")
    assert rendered.index("Threshold Exposure") < rendered.index("Forecast Shift")
    assert rendered.index("Forecast Shift") < rendered.index("Most Affected Administrative Areas")
    assert rendered.index("Most Affected Administrative Areas") < rendered.index("Required Caveats")
    assert rendered.index("Threshold Exposure") < rendered.index("Required Caveats")
    assert "Provider slot prose." in rendered
    assert '<th scope="col">Fact</th>' in rendered
    assert '<th scope="col">Area</th>' in rendered
    assert '<th scope="col">Wind Threshold</th>' in rendered
    assert '<th scope="row">Storm</th><td>ALPHA</td>' in rendered
    assert '<th scope="row">Forecast Issued</th><td><time datetime="2026-01-01T00:00:00Z">2026-01-01T00:00:00Z</time></td>' in rendered
    assert '<th scope="row">Population</th><td>123</td><td><code>data</code></td>' in rendered
    assert '<th scope="row">Population</th><td>90</td><td><code>inferred</code></td>' in rendered
    assert '<th scope="row">North District</th><td>70</td><td>12</td><td>5</td><td>2</td><td>1</td><td>4</td><td><code>data</code> <code>inferred</code></td>' in rendered
    assert '<th scope="row">34kt</th><td>200</td><td>80</td><td>3</td><td>2</td><td>1</td><td>4</td><td><code>data</code></td>' in rendered
    assert '<li><span>AI system based on probabilistic model outputs</span> <code>inferred</code></li>' in rendered
    assert '<li><code>data</code></li>' in rendered
    assert '<li><code>inferred</code></li>' in rendered

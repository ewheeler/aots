from __future__ import annotations

import base64
import io
import json
import math
import re
from dataclasses import dataclass
from html import escape
from html.parser import HTMLParser
from typing import Any, Mapping, Protocol, TypedDict

import matplotlib

matplotlib.use("Agg")
import matplotlib.colors as mcolors
import matplotlib.patches as mpatches
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
import numpy as np
from matplotlib.collections import PatchCollection
from matplotlib.patches import Rectangle
from shapely.geometry import shape

from aots_portable_reports.alert_contract import ALERT_PROVENANCE_LABELS
from aots_portable_reports.models import ComparisonIssue, ComparisonReport, ReportSnapshot


MAIN_ALERT_THRESHOLD = 50
SITUATION_SUMMARY_HEADING = "Situation Summary"
SITUATION_SUMMARY_SLOT = "situation_summary"
SUMMARY_SLOT = "summary"
NARRATIVE_SLOT = "narrative"
SHIFT_SLOT = "shift"
OSCILLATION_SLOT = "oscillation"
BOUNDED_PROSE_SLOTS = (SUMMARY_SLOT, SITUATION_SUMMARY_SLOT, NARRATIVE_SLOT, SHIFT_SLOT, OSCILLATION_SLOT)
AI_PROBABILISTIC_CAVEAT = "AI system based on probabilistic model outputs"
VISUAL_THRESHOLDS = (50, 34, 64)


class AlertProseSlots(TypedDict, total=False):
    summary: str
    situation_summary: str
    narrative: str
    shift: str
    oscillation: str


@dataclass(frozen=True)
class AlertProseRequest:
    alert_context: dict[str, Any]
    expected_alert_html: str | None = None


class AlertProseProvider(Protocol):
    def provide_prose_slots(self, request: AlertProseRequest) -> dict[str, str]: ...


class BaselineReplayAlertProseProvider:
    def provide_prose_slots(self, request: AlertProseRequest) -> dict[str, str]:
        summary = baseline_replay_summary_prose(request.expected_alert_html)
        slots = {
            SUMMARY_SLOT: summary,
            SITUATION_SUMMARY_SLOT: summary,
            NARRATIVE_SLOT: _first_available_paragraph(
                request.expected_alert_html,
                ["Situation Overview", "Expected Impact", "Impact Narrative", "Narrative"],
            ),
            SHIFT_SLOT: _first_available_paragraph(
                request.expected_alert_html,
                ["Forecast Shift", "Shift", "Track Shift", "Forecast changes"],
            ),
            OSCILLATION_SLOT: _first_available_paragraph(
                request.expected_alert_html,
                ["Oscillation Notice", "Oscillation", "Forecast Oscillation"],
            ),
        }
        return {key: value for key, value in slots.items() if value}


DEFAULT_ALERT_PROSE_PROVIDER: AlertProseProvider = BaselineReplayAlertProseProvider()


@dataclass(frozen=True)
class _AlertTableEvidence:
    caption: str
    headers: tuple[str, ...]
    rows: tuple[tuple[str, ...], ...]


@dataclass(frozen=True)
class _AlertImageEvidence:
    alt_text: str
    caption: str


@dataclass(frozen=True)
class _AlertPresentationEvidence:
    text: str
    tables: tuple[_AlertTableEvidence, ...]
    images: tuple[_AlertImageEvidence, ...]
    list_items: tuple[str, ...]


def build_alert_context(report_snapshot: ReportSnapshot) -> dict[str, Any]:
    report = report_snapshot.report
    identity = {
        "country": report.get("country", report_snapshot.country),
        "storm": report.get("storm", report_snapshot.storm),
        "forecast_time": report.get("forecast_time", report_snapshot.forecast_time),
    }
    main_threshold = {"wind_threshold": MAIN_ALERT_THRESHOLD, "label": f"{MAIN_ALERT_THRESHOLD}kt"}
    impact_totals = _compact_dict(
        {
            "population": report.get("expected_pop", report.get("expected_population")),
            "children": report.get("expected_children"),
            "schools": report.get("expected_schools"),
            "health_centers": report.get("expected_hcs", report.get("expected_health_centers")),
            "shelters": report.get("expected_shelters"),
            "wash": report.get("expected_wash"),
        }
    )
    people_in_need = _compact_dict(
        {
            "population": report.get("E_people_in_need"),
            "children": report.get("E_children_in_need"),
        }
    )
    top_admin_areas = _top_admin_context_rows(report)
    cross_threshold_rows = _threshold_rows(report)
    required_caveats = [
        {
            "id": "ai_probabilistic_model_outputs",
            "text": AI_PROBABILISTIC_CAVEAT,
            "provenance_labels": ["inferred"],
        }
    ]
    provenance_labels = list(ALERT_PROVENANCE_LABELS)
    totals = dict(impact_totals)
    if "population" in people_in_need:
        totals["people_in_need"] = people_in_need["population"]
    if "children" in people_in_need:
        totals["children_in_need"] = people_in_need["children"]
    return {
        "identity": identity,
        "main_threshold": main_threshold,
        "impact_totals": impact_totals,
        "people_in_need": people_in_need,
        "top_admin_areas": top_admin_areas,
        "cross_threshold_rows": cross_threshold_rows,
        "required_caveats": required_caveats,
        "provenance_labels": provenance_labels,
        "country": identity["country"],
        "storm": identity["storm"],
        "forecast_time": identity["forecast_time"],
        "totals": totals,
        "admin_rows": report.get("rows_admins_pop_total", []),
        "threshold_rows": cross_threshold_rows,
        "required_caveat": AI_PROBABILISTIC_CAVEAT,
    }


def build_alert_claims(alert_context: dict[str, Any]) -> dict[str, Any]:
    identity = _context_identity(alert_context)
    main_threshold = _context_main_threshold(alert_context)
    impact_totals = _metric_claims(
        alert_context.get("impact_totals") or _impact_totals_from_legacy(alert_context),
        provenance_labels=["data"],
    )
    people_in_need_values = _metric_claims(
        alert_context.get("people_in_need") or _people_in_need_from_legacy(alert_context),
        provenance_labels=["inferred"],
    )
    top_admin_areas = [
        {**row, "provenance_labels": ["data", "inferred"]}
        for row in _top_admin_claims(alert_context.get("top_admin_areas") or alert_context.get("admin_rows", []))
    ]
    cross_threshold_rows = [
        {**row, "provenance_labels": ["data"]}
        for row in _cross_threshold_claims(alert_context)
    ]
    required_caveats = _required_caveat_claims(alert_context)
    totals = _legacy_totals(alert_context)
    return {
        "identity": identity,
        "main_threshold": main_threshold,
        "impact_totals": impact_totals,
        "people_in_need_values": people_in_need_values,
        "top_admin_areas": top_admin_areas,
        "cross_threshold_rows": cross_threshold_rows,
        "required_caveats": required_caveats,
        "provenance_labels": alert_context.get("provenance_labels", []),
        "totals": totals,
        "threshold_rows": [
            {key: value for key, value in row.items() if key != "provenance_labels"} for row in cross_threshold_rows
        ],
        "visual_assets": _visual_asset_claims(alert_context.get("visual_context")),
        "required_caveat": required_caveats[0]["text"] if required_caveats else None,
    }


def build_alert_visual_context(
    report_snapshot: ReportSnapshot,
    *,
    source_artifacts: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    report = report_snapshot.report
    artifacts = source_artifacts or {}
    admin_rows = _records(artifacts.get("admin_50"))
    admin_geometry_rows = _records(artifacts.get("admin_geometry"))
    children_by_name = {_norm_key(row.get("name")): _children_at_risk(row) for row in admin_rows if row.get("name")}
    admin_visual_rows = []
    for row in admin_geometry_rows:
        name = row.get("name") or row.get("NAME")
        if not name:
            continue
        admin_visual_rows.append(
            {
                "name": str(name),
                "geojson": row.get("geojson") or row.get("GEOGEOJSON") or row.get("geometry_geojson"),
                "clon": _float_or_none(row.get("clon") or row.get("centroid_lon")),
                "clat": _float_or_none(row.get("clat") or row.get("centroid_lat")),
                "children": children_by_name.get(_norm_key(name), 0),
            }
        )
    ensemble = {}
    for threshold in VISUAL_THRESHOLDS:
        tiles = [_tile_visual_row(row) for row in _records(artifacts.get(f"tiles_{threshold}"))]
        tiles = [row for row in tiles if row is not None]
        ensemble[str(threshold)] = {
            "available": bool(tiles),
            "threshold": threshold,
            "tiles": tiles,
            "admin": admin_visual_rows,
            "tracks": [_track_visual_row(row) for row in _records(artifacts.get("raw_tracks"))],
        }
    evolution_rows = [_evolution_visual_row(row) for row in _records(artifacts.get("impact_evolution_50"))]
    evolution_rows = [row for row in evolution_rows if row is not None]
    timing_rows = [_timing_context_row(row) for row in _records(artifacts.get("alert_timing"))]
    timing_rows = [row for row in timing_rows if row is not None]
    return {
        "impact_composition": _impact_composition_context(report),
        "admin_choropleth": {"available": bool(admin_visual_rows), "threshold": 50, "rows": admin_visual_rows},
        "ensemble_probability": ensemble,
        "impact_evolution": {"available": bool(evolution_rows), "threshold": 50, "rows": evolution_rows},
        "timing_rows": timing_rows,
    }


def render_alert_visual_assets(alert_visual_context: dict[str, Any]) -> list[dict[str, Any]]:
    assets: list[dict[str, Any]] = []
    composition = alert_visual_context.get("impact_composition", {})
    if isinstance(composition, dict):
        population = composition.get("population", {})
        if isinstance(population, dict) and population.get("available"):
            assets.append(
                _asset(
                    kind="population_composition",
                    threshold=50,
                    filename="population-composition-50kt.png",
                    png_base64=_render_donut_chart(
                        population.get("values", {}),
                        labels={"children": "Children 0-19", "other_population": "Other population"},
                        title="Population at risk",
                        colors=["#1CABE2", "#d8d8d8"],
                    ),
                    alt_text="Population composition donut chart",
                    caption="Composition of total population at risk at the 50 kt threshold.",
                )
            )
        people_in_need = composition.get("people_in_need", {})
        if isinstance(people_in_need, dict) and people_in_need.get("available"):
            assets.append(
                _asset(
                    kind="people_in_need_composition",
                    threshold=50,
                    filename="people-in-need-composition-50kt.png",
                    png_base64=_render_donut_chart(
                        people_in_need.get("values", {}),
                        labels={"children_in_need": "Children in need", "other_people_in_need": "Other people in need"},
                        title="People in need",
                        colors=["#f28c28", "#f7d7b5"],
                    ),
                    alt_text="People in need composition donut chart",
                    caption="Composition of people in need at the 50 kt threshold.",
                )
            )
    evolution = alert_visual_context.get("impact_evolution", {})
    if isinstance(evolution, dict) and evolution.get("available"):
        assets.append(
            _asset(
                kind="impact_evolution",
                threshold=50,
                filename="impact-evolution-50kt.png",
                png_base64=_render_impact_evolution_chart(evolution.get("rows", [])),
                alt_text="Forecast evolution chart",
                caption="Total population at risk at storm-force winds (50 kt) across recent forecast runs.",
            )
        )
    admin = alert_visual_context.get("admin_choropleth", {})
    if isinstance(admin, dict) and admin.get("available"):
        assets.append(
            _asset(
                kind="admin_choropleth",
                threshold=50,
                filename="admin-choropleth-50kt.png",
                png_base64=_render_admin_choropleth(admin.get("rows", [])),
                alt_text="Admin impact map",
                caption="Expected children at risk by administrative area at the 50 kt threshold.",
            )
        )
    ensemble = alert_visual_context.get("ensemble_probability", {})
    if isinstance(ensemble, dict):
        for threshold in VISUAL_THRESHOLDS:
            entry = ensemble.get(str(threshold), {})
            if not isinstance(entry, dict) or not entry.get("available"):
                continue
            assets.append(
                _asset(
                    kind="ensemble_probability",
                    threshold=threshold,
                    filename=f"ensemble-probability-{threshold}kt.png",
                    png_base64=_render_ensemble_probability_map(
                        entry.get("tiles", []),
                        entry.get("tracks", []) if threshold == 50 else [],
                        threshold=threshold,
                        admin_rows=entry.get("admin", []),
                    ),
                    alt_text=f"Wind exposure probability map ({threshold}kt)",
                    caption=f"Probability of wind exposure at the {threshold} kt threshold.",
                )
            )
    return [asset for asset in assets if asset["status"] == "rendered"]


def build_alert_prose_slots(
    alert_context: dict[str, Any],
    *,
    expected_alert_html: str | None = None,
    provider: AlertProseProvider | None = None,
) -> AlertProseSlots:
    active_provider = provider or DEFAULT_ALERT_PROSE_PROVIDER
    return _bounded_alert_prose_slots(
        active_provider.provide_prose_slots(
            AlertProseRequest(alert_context=alert_context, expected_alert_html=expected_alert_html)
        )
    )


def render_alert_html(
    alert_context: dict[str, Any],
    *,
    prose_slots: AlertProseSlots | None = None,
    visual_assets: list[dict[str, Any]] | None = None,
) -> str:
    bounded_prose = _bounded_alert_prose_slots(prose_slots or {})
    summary = _slot_value(bounded_prose, SUMMARY_SLOT, SITUATION_SUMMARY_SLOT)
    narrative = _slot_value(bounded_prose, NARRATIVE_SLOT)
    shift = _slot_value(bounded_prose, SHIFT_SLOT)
    oscillation = _slot_value(bounded_prose, OSCILLATION_SLOT)
    identity = _context_identity(alert_context)
    main_threshold = _context_main_threshold(alert_context)
    title = f"Storm {identity.get('storm', 'Unknown')} - {identity.get('country', 'Unknown')}"
    threshold_label = escape(str(main_threshold.get("label", f"{MAIN_ALERT_THRESHOLD}kt")))
    summary_html = escape(summary) if summary else "No bounded summary prose was available."
    narrative_html = escape(narrative) if narrative else "Structured forecast facts and generated visuals summarize expected exposure for review."
    shift_html = escape(shift) if shift else "No bounded forecast-shift prose was available for this snapshot."
    oscillation_html = escape(oscillation) if oscillation else "No bounded oscillation notice was available for this snapshot."
    timing_rows = _timing_rows(alert_context.get("timing_rows", []))
    facts_rows = "".join(
        [
            _fact_row("Storm", identity.get("storm")),
            _fact_row("Country", identity.get("country")),
            _fact_row("Forecast Issued", _time_html(identity.get("forecast_time"))),
            _fact_row("Alert Threshold", threshold_label),
        ]
    )
    impact_rows = _metric_rows(alert_context.get("impact_totals") or _impact_totals_from_legacy(alert_context), ["data"])
    people_in_need_rows = _metric_rows(
        alert_context.get("people_in_need") or _people_in_need_from_legacy(alert_context), ["inferred"]
    )
    admin_rows = _admin_area_rows(_top_admin_claims(alert_context.get("top_admin_areas") or alert_context.get("admin_rows", [])))
    threshold_rows = _threshold_exposure_rows(_cross_threshold_claims(alert_context))
    caveat_items = _required_caveat_items(_required_caveat_claims(alert_context))
    provenance_items = _provenance_list_items(alert_context.get("provenance_labels", []))
    required_caveat = _required_caveat_text(alert_context)
    composition_visuals = _composition_visual_section(visual_assets or [])
    primary_visual = _primary_visual_section(visual_assets or [])
    secondary_visuals = _secondary_visual_section(visual_assets or [])
    admin_visual = _admin_visual_section(visual_assets or [])
    evolution_visual = _evolution_visual_section(visual_assets or [])
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <title>{escape(title)}</title>
  <style>
    :root {{ --aots-blue:#1CABE2; --aots-blue-dark:#1A6080; --aots-blue-border:#1499c7; --aots-text:#222; --aots-muted:#888; --aots-line:#e8e8e8; --aots-cell:#ddd; --aots-highlight:#ebf8ff; }}
    body {{ margin:0; background:#f6f6f6; color:var(--aots-text); font-family:Arial, Helvetica, sans-serif; line-height:1.6; }}
    .email-shell {{ max-width:700px; margin:0 auto; background:#ffffff; border:1px solid #d0d0d0; }}
    .alert-header {{ background:var(--aots-blue); color:#ffffff; padding:18px 24px; }}
    .eyebrow {{ margin:0; font-size:12px; font-weight:700; letter-spacing:1.2px; text-transform:uppercase; }}
    .header-rule {{ border-top:1px solid rgba(255,255,255,0.3); margin:12px 0 10px; }}
    .alert-urgency-strip {{ background:var(--aots-blue-dark); color:#ffffff; padding:10px 24px; margin:0; font-weight:700; font-size:0.85em; letter-spacing:0.5px; text-transform:uppercase; }}
    main {{ padding:24px 28px; }}
    .alert-card {{ border-top:1px solid var(--aots-line); padding:22px 0 0; margin:24px 0 0; }}
    .alert-card:first-child {{ border-top:0; padding-top:0; margin-top:0; }}
    .alert-card h2 {{ margin:0 0 14px; font-size:1em; color:var(--aots-blue); border-left:4px solid var(--aots-blue); padding-left:10px; text-transform:uppercase; letter-spacing:0.5px; }}
    .accent-card {{ background:#f0f9ff; border-left:5px solid var(--aots-blue); border-top:0; padding:14px 18px; margin:0 0 20px; border-radius:0 3px 3px 0; }}
    .accent-card h2 {{ border-left:0; padding-left:0; font-size:0.8em; color:var(--aots-blue-dark); margin:0 0 7px; }}
    .visual-primary figure, .visual-secondary figure {{ margin:12px 0 18px; }}
    .visual-secondary-grid {{ display:grid; grid-template-columns:repeat(auto-fit,minmax(260px,1fr)); gap:14px; }}
    table {{ width:100%; border-collapse:collapse; font-size:0.92em; margin-top:8px; }}
    caption {{ text-align:left; color:var(--aots-muted); font-size:0.83em; margin-bottom:4px; }}
    thead tr {{ background:var(--aots-blue); }}
    thead th {{ background:var(--aots-blue); color:#ffffff; border:1px solid var(--aots-blue-border); padding:7px 10px; font-weight:bold; }}
    tbody th, tbody td {{ border:1px solid var(--aots-cell); padding:6px 10px; text-align:left; vertical-align:top; }}
    tbody tr:nth-child(odd) {{ background:#ffffff; }}
    tbody tr:nth-child(even) {{ background:#f9f9f9; }}
    code {{ background:#f0f8fc; border:1px solid #9ecde8; border-radius:2px; padding:0 3px; font-size:0.73em; color:var(--aots-blue-dark); white-space:nowrap; }}
    img {{ max-width:100%; height:auto; border:0; }}
    figcaption {{ font-size:0.83em; color:var(--aots-muted); margin-top:4px; }}
    footer {{ background:#f8f8f8; padding:16px 28px 20px; border-top:1px solid var(--aots-line); color:#666; font-size:0.88em; }}
  </style>
</head>
<body>
  <div class="email-shell">
    <header class="alert-header">
      <p class="eyebrow">Ahead of the Storm &mdash; Storm Alert</p>
      <div class="header-rule"></div>
      <h1 style="margin:10px 0 6px; font-size:30px; line-height:1.2;">{escape(title)}</h1>
      <p style="margin:0; color:rgba(255,255,255,0.85); font-size:0.9em;">Forecast issued: {escape(str(identity.get('forecast_time', 'Unknown')))}</p>
    </header>
    <p class="alert-urgency-strip" id="alert-urgency-strip">Active Forecast — Review expected {threshold_label} exposure and validate local preparedness decisions.</p>
    <main>
      <section aria-labelledby="summary-heading" class="alert-card accent-card">
        <h2 id="summary-heading">{SITUATION_SUMMARY_HEADING}</h2>
        <p style="margin:0;">{summary_html}</p>
      </section>
      <section aria-labelledby="timing-heading" class="alert-card">
        <h2 id="timing-heading">Timing &amp; Forecast Details</h2>
        {_table_html("alert-facts-caption", "Key alert facts derived from structured report inputs.", ["Fact", "Value"], facts_rows)}
        {timing_rows}
      </section>
      <section aria-labelledby="overview-heading" class="alert-card">
        <h2 id="overview-heading">Situation Overview</h2>
        <p style="margin:0;">{narrative_html}</p>
      </section>
      <section aria-labelledby="impact-heading" class="alert-card accent-card">
        <h2 id="impact-heading">Expected Impact</h2>
        {_table_html("impact-totals-caption", f"Expected impact totals for the {threshold_label} threshold.", ["Metric", "Value", "Provenance"], impact_rows)}
        <div style="height:12px;"></div>
        {_table_html("people-in-need-caption", "Inferred people-in-need values used for review.", ["Metric", "Value", "Provenance"], people_in_need_rows)}
      </section>
      {composition_visuals}
      {primary_visual}
      {secondary_visuals}
      <section aria-labelledby="threshold-heading" class="alert-card">
        <h2 id="threshold-heading">Threshold Exposure</h2>
        {_table_html("threshold-exposure-caption", "Population, children, and facilities exposed across wind thresholds.", ["Wind Threshold", "Population", "Children", "Schools", "Health Centers", "Shelters", "WASH", "Provenance"], threshold_rows)}
      </section>
      {admin_visual}
      <section aria-labelledby="shift-heading" class="alert-card">
        <h2 id="shift-heading">Forecast Shift</h2>
        <p style="margin:0;">{shift_html}</p>
      </section>
      <section aria-labelledby="admin-heading" class="alert-card">
        <h2 id="admin-heading">Most Affected Administrative Areas</h2>
        {_table_html("admin-areas-caption", "Administrative areas with the highest 50kt population exposure.", ["Area", "Population", "People in Need", "Schools", "Health Centers", "Shelters", "WASH", "Provenance"], admin_rows)}
      </section>
      {evolution_visual}
      <section aria-labelledby="oscillation-heading" class="alert-card">
        <h2 id="oscillation-heading">Oscillation Notice</h2>
        <p style="margin:0;">{oscillation_html}</p>
      </section>
      <section aria-labelledby="caveats-heading" class="alert-card">
        <h2 id="caveats-heading">Required Caveats</h2>
        <ul style="margin:0; padding-left:20px;">{caveat_items}</ul>
      </section>
      <section aria-labelledby="provenance-heading" class="alert-card">
        <h2 id="provenance-heading">Provenance Labels</h2>
        <ul style="margin:0; padding-left:20px;">{provenance_items}</ul>
      </section>
    </main>
    <footer>
      <p style="margin:0;">This alert was generated automatically by an {escape(required_caveat)}, not observed conditions. Numbers reflect expected values across the forecast ensemble and should be reviewed before use.</p>
    </footer>
  </div>
</body>
</html>
"""


def compare_alert_output(alert_claims: dict[str, Any], rendered_alert_html: str) -> ComparisonReport:
    evidence = _presentation_evidence(rendered_alert_html)
    failures: list[ComparisonIssue] = []
    warnings: list[ComparisonIssue] = []
    identity = alert_claims.get("identity", {})
    facts = _facts_table(evidence.tables)
    for key, fact_label in {"storm": "Storm", "country": "Country", "forecast_time": "Forecast Issued"}.items():
        value = identity.get(key)
        if value and not _fact_value_matches(facts, fact_label, value, evidence.text):
            failures.append(_failure("missing_alert_identity", f"rendered alert does not include {key}: {value}"))
    threshold_claim = _main_threshold_label(alert_claims)
    if threshold_claim and not _fact_value_matches(facts, "Alert Threshold", threshold_claim, evidence.text):
        failures.append(_failure("missing_alert_threshold", f"rendered alert does not include alert threshold: {threshold_claim}"))
    impact_rows = _metric_table(_find_table(evidence.tables, headers=("metric", "value", "provenance"), caption_contains="impact"))
    people_rows = _metric_table(_find_table(evidence.tables, headers=("metric", "value", "provenance"), caption_contains="people"))
    admin_rows = _admin_area_table(
        _find_table(
            evidence.tables,
            headers=("area", "population", "people in need", "schools", "health centers", "shelters", "wash", "provenance"),
            caption_contains="administrative",
        )
    )
    threshold_rows = _threshold_table(
        _find_table(
            evidence.tables,
            headers=("wind threshold", "population", "children", "schools", "health centers", "shelters", "wash", "provenance"),
            caption_contains="threshold",
        )
    )
    for claim in _claim_rows(alert_claims.get("impact_totals")):
        if not _metric_claim_matches(impact_rows, claim):
            failures.append(_failure("missing_impact_total_claim", _metric_claim_message("impact total", claim)))
    for claim in _claim_rows(alert_claims.get("people_in_need_values")):
        if not _metric_claim_matches(people_rows, claim):
            failures.append(_failure("missing_people_in_need_claim", _metric_claim_message("people-in-need", claim)))
    for claim in _claim_rows(alert_claims.get("top_admin_areas")):
        if not _admin_area_claim_matches(admin_rows, claim):
            failures.append(_failure("missing_top_admin_area_claim", _admin_area_claim_message(claim)))
    cross_threshold_claims = _cross_threshold_claims(alert_claims)
    for claim in cross_threshold_claims:
        if not _threshold_claim_matches(threshold_rows, claim):
            failures.append(_failure("missing_threshold_exposure_claim", _threshold_claim_message(claim)))
    for caveat in _required_caveat_texts(alert_claims):
        if caveat and not _text_or_list_item_matches(evidence, caveat):
            failures.append(_failure("missing_alert_caveat", "rendered alert is missing required AI/probabilistic caveat"))
    for label in alert_claims.get("provenance_labels", []):
        if not _text_or_list_item_matches(evidence, label):
            failures.append(_failure("missing_provenance_label", f"rendered alert is missing provenance label: {label}"))
    for claim in _claim_rows(alert_claims.get("visual_assets")):
        if not _visual_asset_claim_matches(evidence.images, claim):
            failures.append(
                _failure(
                    "missing_alert_visual_asset",
                    f"rendered alert is missing visual asset: {claim.get('kind')} {claim.get('threshold')}kt",
                )
            )
    if not cross_threshold_claims:
        warnings.append(_warning("missing_threshold_claims", "no cross-threshold alert claims were available"))
    return ComparisonReport(status="failed" if failures else "passed", failures=failures, warnings=warnings)


def baseline_replay_summary_prose(expected_alert_html: str | None) -> str:
    if not expected_alert_html:
        return ""
    paragraph = _first_paragraph_after_heading(expected_alert_html, SITUATION_SUMMARY_HEADING)
    if paragraph:
        return _clean_replayed_prose(paragraph)
    text = _html_text(expected_alert_html)
    marker = SITUATION_SUMMARY_HEADING
    if marker in text:
        return _clean_replayed_prose(text.split(marker, maxsplit=1)[1].strip())
    return _clean_replayed_prose(text.strip())


def _first_available_paragraph(expected_alert_html: str | None, headings: list[str]) -> str:
    if not expected_alert_html:
        return ""
    for heading in headings:
        paragraph = _first_paragraph_after_heading(expected_alert_html, heading)
        if paragraph:
            return _clean_replayed_prose(paragraph)
    return ""


def _clean_replayed_prose(value: str, *, max_sentences: int = 3, max_chars: int = 460) -> str:
    cleaned = " ".join(value.split())
    cleaned = re.sub(r"\b(data|inferred)\b", "", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"\ban decrease\b", "a decrease", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"\ba increase\b", "an increase", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"\s+([,.;:!?])", r"\1", cleaned)
    cleaned = re.sub(r"\s{2,}", " ", cleaned).strip()
    sentences = [part.strip() for part in re.split(r"(?<=[.!?])\s+", cleaned) if part.strip()]
    if sentences:
        cleaned = " ".join(sentences[:max_sentences])
    if len(cleaned) > max_chars:
        truncated = cleaned[:max_chars].rsplit(" ", maxsplit=1)[0].rstrip(",;:")
        cleaned = truncated + "..."
    return cleaned


def _bounded_alert_prose_slots(values: Mapping[str, Any]) -> AlertProseSlots:
    bounded: AlertProseSlots = {}
    for slot in BOUNDED_PROSE_SLOTS:
        value = values.get(slot)
        if value is not None:
            bounded[slot] = str(value)
    if SUMMARY_SLOT in bounded and SITUATION_SUMMARY_SLOT not in bounded:
        bounded[SITUATION_SUMMARY_SLOT] = bounded[SUMMARY_SLOT]
    if SITUATION_SUMMARY_SLOT in bounded and SUMMARY_SLOT not in bounded:
        bounded[SUMMARY_SLOT] = bounded[SITUATION_SUMMARY_SLOT]
    return bounded


def _asset(
    *,
    kind: str,
    threshold: int,
    filename: str,
    png_base64: str | None,
    alt_text: str,
    caption: str,
) -> dict[str, Any]:
    if not png_base64:
        return {"kind": kind, "threshold": threshold, "filename": filename, "status": "skipped"}
    return {
        "kind": kind,
        "threshold": threshold,
        "filename": filename,
        "status": "rendered",
        "mime_type": "image/png",
        "png_base64": png_base64,
        "data_uri": f"data:image/png;base64,{png_base64}",
        "alt_text": alt_text,
        "caption": caption,
        "provenance_labels": ["data", "inferred"] if kind == "admin_choropleth" else ["data"],
    }


def _impact_composition_context(report: Mapping[str, Any]) -> dict[str, Any]:
    population = _float(report.get("expected_pop") or report.get("expected_population"))
    children = _float(report.get("expected_children"))
    people_in_need = _float(report.get("E_people_in_need"))
    children_in_need = _float(report.get("E_children_in_need"))
    return {
        "population": {
            "available": population > 0 and children > 0,
            "values": {
                "children": children,
                "other_population": max(population - children, 0.0),
            },
        },
        "people_in_need": {
            "available": people_in_need > 0 and children_in_need > 0,
            "values": {
                "children_in_need": children_in_need,
                "other_people_in_need": max(people_in_need - children_in_need, 0.0),
            },
        },
    }


def _render_donut_chart(
    values: Any,
    *,
    labels: dict[str, str],
    title: str,
    colors: list[str],
) -> str | None:
    if not isinstance(values, Mapping):
        return None
    keys = [key for key in labels if _float(values.get(key)) > 0]
    if not keys:
        return None
    sizes = [_float(values.get(key)) for key in keys]
    display_labels = [labels[key] for key in keys]
    fig, ax = plt.subplots(figsize=(4.2, 3.2), dpi=150)
    fig.patch.set_facecolor("white")
    wedges, _ = ax.pie(
        sizes,
        colors=colors[: len(sizes)],
        startangle=90,
        counterclock=False,
        wedgeprops={"width": 0.38, "edgecolor": "white"},
    )
    total = sum(sizes)
    ax.text(0, 0.05, f"{int(round(total)):,}", ha="center", va="center", fontsize=14, fontweight="bold", color="#16313a")
    ax.text(0, -0.17, "total", ha="center", va="center", fontsize=8, color="#5a6b72")
    ax.set_title(title, fontsize=10, color="#0f4f5e", pad=8)
    legend_labels = [f"{label}: {int(round(size)):,}" for label, size in zip(display_labels, sizes)]
    ax.legend(wedges, legend_labels, loc="lower center", bbox_to_anchor=(0.5, -0.16), fontsize=7, frameon=False)
    ax.set_aspect("equal")
    plt.tight_layout(pad=0.6)
    return _figure_png_base64(fig, dpi=150)


def _render_impact_evolution_chart(rows: Any) -> str | None:
    data = [row for row in rows if isinstance(row, dict)]
    if not data:
        return None
    labels = [str(row.get("label") or row.get("forecast_date") or index + 1) for index, row in enumerate(data)]
    population = [_float(row.get("population") or row.get("pop")) for row in data]
    children = [
        _float(row.get("children"))
        if row.get("children") is not None
        else _float(row.get("infant")) + _float(row.get("school_age")) + _float(row.get("adolescent"))
        for row in data
    ]
    x = np.arange(len(labels))
    fig, ax = plt.subplots(figsize=(7.2, 3.0))
    fig.patch.set_facecolor("white")
    ax.set_facecolor("white")
    zeros = [0.0] * len(labels)
    ax.fill_between(x, zeros, population, color="#d8d8d8", alpha=0.85, label="Total population at risk")
    ax.fill_between(x, zeros, children, color="#1CABE2", alpha=0.9, label="of which: children 0-19")
    if len(x) > 0:
        ax.axvspan(x[-1] - 0.45, x[-1] + 0.45, alpha=0.12, color="#1CABE2", zorder=0)
        ax.text(x[-1], 0, "current", ha="center", va="bottom", fontsize=6.5, color="#1A6080", style="italic")
    ax.set_xticks(x)
    ax.set_xticklabels(labels, rotation=40, ha="right", fontsize=7.5)
    ax.set_ylabel("People at risk (50 kt)", fontsize=8)
    ax.yaxis.set_major_formatter(mticker.FuncFormatter(lambda value, _: f"{int(value):,}"))
    ax.legend(loc="upper left", fontsize=7, framealpha=0.9, edgecolor="#e0e0e0")
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.yaxis.grid(True, color="#f0f0f0", linewidth=0.7, zorder=0)
    ax.set_axisbelow(True)
    ax.tick_params(axis="both", length=0)
    ax.set_xlim(-0.5, len(x) - 0.5)
    ax.set_ylim(bottom=0)
    plt.tight_layout(pad=0.6)
    return _figure_png_base64(fig, dpi=130)


def _render_admin_choropleth(rows: Any) -> str | None:
    features = []
    for row in rows if isinstance(rows, list) else []:
        if not isinstance(row, dict) or not row.get("geojson"):
            continue
        try:
            features.append(
                {
                    "name": str(row.get("name") or ""),
                    "geom": shape(json.loads(str(row["geojson"]))),
                    "children": _float(row.get("children")),
                    "clon": _float_or_none(row.get("clon")),
                    "clat": _float_or_none(row.get("clat")),
                }
            )
        except Exception:
            continue
    if not features:
        return None
    colors = ["#ffffcc", "#ffeda0", "#fed976", "#feb24c", "#fd8d3c", "#fc4e2a", "#e31a1c", "#bd0026", "#800026"]
    rgb = [_hex_to_rgb(color) for color in colors]
    max_value = max(feature["children"] for feature in features) or 1
    fig, ax = plt.subplots(figsize=(10, 6), dpi=150)
    fig.patch.set_facecolor("white")
    ax.set_facecolor("white")
    bounds_lons: list[float] = []
    bounds_lats: list[float] = []
    for feature in features:
        color = _value_color(feature["children"], max_value, rgb)
        for poly in _polygons(feature["geom"]):
            x, y = poly.exterior.xy
            ax.fill(x, y, facecolor=color, edgecolor=color, linewidth=0.6, antialiased=False)
            for interior in poly.interiors:
                xi, yi = interior.xy
                ax.fill(xi, yi, facecolor="white", edgecolor="white", linewidth=0.6, antialiased=False)
            ax.plot(x, y, color="#888888", linewidth=0.4)
        west, south, east, north = feature["geom"].bounds
        bounds_lons.extend([west, east])
        bounds_lats.extend([south, north])
    for feature in features:
        if feature["clon"] is None or feature["clat"] is None:
            continue
        label_name = _wrap_name(feature["name"])
        is_two_line = "\n" in label_name
        name_offset = 0.022 if is_two_line else 0.015
        label_bbox = dict(boxstyle="round,pad=0.15", facecolor="white", alpha=0.75, edgecolor="none")
        ax.text(feature["clon"], feature["clat"] + name_offset, label_name, fontsize=6.5 if is_two_line else 7, fontweight="bold", ha="center", va="bottom", color="#111111", bbox=label_bbox)
        ax.text(feature["clon"], feature["clat"] - 0.010, f'{int(round(feature["children"])):,}', fontsize=6, ha="center", va="top", color="#333333", bbox=label_bbox)
    if bounds_lons and bounds_lats:
        lon_range = max(bounds_lons) - min(bounds_lons) or 1
        lat_range = max(bounds_lats) - min(bounds_lats) or 1
        ax.set_xlim(min(bounds_lons) - lon_range * 0.22, max(bounds_lons) + lon_range * 0.22)
        ax.set_ylim(min(bounds_lats) - lat_range * 0.22, max(bounds_lats) + lat_range * 0.22)
        mid_lat = (min(bounds_lats) + max(bounds_lats)) / 2
        ax.set_aspect(1.0 / max(math.cos(math.radians(mid_lat)), 0.1))
    ax.axis("off")
    legend_patches = []
    n = len(colors)
    for index, color in enumerate(colors):
        lo = (index / n) * max_value
        hi = ((index + 1) / n) * max_value
        legend_patches.append(
            mpatches.Patch(facecolor=_hex_to_rgb(color), edgecolor="#cccccc", linewidth=0.3, label=f"{int(round(lo)):,}–{int(round(hi)):,}")
        )
    fig.legend(handles=legend_patches, title="Children at risk (0-19) at 50kt", title_fontsize=8, fontsize=7, loc="lower center", ncol=n, bbox_to_anchor=(0.5, 0), frameon=True, framealpha=0.9, edgecolor="#dddddd", handlelength=1.2, handleheight=0.9)
    plt.tight_layout(rect=(0, 0.08, 1, 1))
    return _figure_png_base64(fig, dpi=150)


def _render_ensemble_probability_map(rows: Any, tracks: Any, *, threshold: int, admin_rows: Any = None) -> str | None:
    tiles = [row for row in rows if isinstance(row, dict)] if isinstance(rows, list) else []
    if not tiles:
        return None
    admin_geoms = _admin_geometries(admin_rows)
    if not admin_geoms:
        admin_geoms = []
    fig, ax = plt.subplots(figsize=(10, 6), dpi=150)
    fig.patch.set_facecolor("white")
    ax.set_facecolor("white")
    patches = []
    colors = []
    for tile in tiles:
        z = tile.get("z")
        p = _float(tile.get("p"))
        if not z or p < 0.005:
            continue
        try:
            west, south, east, north = _qk_bounds(str(z))
        except Exception:
            continue
        patches.append(Rectangle((west, south), east - west, north - south))
        colors.append(p)
    if not patches:
        return None
    cmap = mcolors.LinearSegmentedColormap.from_list("ylorrd", ["#ffffcc", "#ffeda0", "#fed976", "#feb24c", "#fd8d3c", "#fc4e2a", "#f03b20", "#e31a1c", "#bd0026", "#800026"])
    actual_max = max(colors) if colors else 0.1
    norm = mcolors.Normalize(vmin=0, vmax=actual_max)
    for geom in admin_geoms:
        for poly in _polygons(geom):
            ax.fill(*poly.exterior.xy, facecolor="white", edgecolor="none", zorder=1)
            for interior in poly.interiors:
                ax.fill(*interior.xy, facecolor="white", edgecolor="none", zorder=1)
    ax.add_collection(PatchCollection(patches, array=np.array(colors), cmap=cmap, norm=norm, linewidths=0, antialiased=False, alpha=1.0, zorder=3))
    track_rows = [row for row in tracks if isinstance(row, dict)] if isinstance(tracks, list) else []
    members: dict[str, list[tuple[int, float, float]]] = {}
    for row in track_rows:
        member = str(row.get("m") or row.get("ENSEMBLE_MEMBER") or row.get("ensemble_member") or "member")
        lon = _float_or_none(row.get("lon") or row.get("LONGITUDE") or row.get("longitude"))
        lat = _float_or_none(row.get("lat") or row.get("LATITUDE") or row.get("latitude"))
        lead = int(_float(row.get("lt") or row.get("LEAD_TIME") or row.get("lead_time")))
        if lon is None or lat is None:
            continue
        members.setdefault(member, []).append((lead, lon, lat))
    all_x = [patch.get_x() for patch in patches] + [patch.get_x() + patch.get_width() for patch in patches]
    all_y = [patch.get_y() for patch in patches] + [patch.get_y() + patch.get_height() for patch in patches]
    for geom in admin_geoms:
        west, south, east, north = geom.bounds
        all_x.extend([west, east])
        all_y.extend([south, north])
    if members:
        initial_points = [points[0] for points in (sorted(points, key=lambda item: item[0]) for points in members.values()) if points]
        if initial_points:
            init_lon = sum(point[1] for point in initial_points) / len(initial_points)
            init_lat = sum(point[2] for point in initial_points) / len(initial_points)
            all_x.append(init_lon)
            all_y.append(init_lat)
    if all_x and all_y:
        x_range = max(all_x) - min(all_x) or 1
        y_range = max(all_y) - min(all_y) or 1
        ax.set_xlim(min(all_x) - x_range * 0.22, max(all_x) + x_range * 0.22)
        ax.set_ylim(min(all_y) - y_range * 0.22, max(all_y) + y_range * 0.22)
        mid_lat = (min(all_y) + max(all_y)) / 2
        cos_lat = max(math.cos(math.radians(mid_lat)), 0.1)
        ax.set_aspect(1.0 / cos_lat)
    else:
        cos_lat = 1.0
    if threshold == 50 and members:
        _draw_ensemble_density_bands(ax, members, cos_lat=cos_lat)
    for points in members.values():
        points.sort(key=lambda item: item[0])
        ax.plot(
            [point[1] for point in points],
            [point[2] for point in points],
            color="#888888",
            alpha=0.20,
            linewidth=0.6,
            solid_capstyle="round",
            zorder=8,
        )
    if threshold == 50 and members:
        initial_points = [points[0] for points in (sorted(points, key=lambda item: item[0]) for points in members.values()) if points]
        if initial_points:
            init_lon = sum(point[1] for point in initial_points) / len(initial_points)
            init_lat = sum(point[2] for point in initial_points) / len(initial_points)
            ax.scatter([init_lon], [init_lat], s=60, color="white", edgecolors="#1a3a5c", linewidths=1.5, zorder=12)
            ax.scatter([init_lon], [init_lat], s=15, color="#1CABE2", zorder=13)
    for geom in admin_geoms:
        for poly in _polygons(geom):
            ax.plot(*poly.exterior.xy, color="#888888", linewidth=0.4, solid_capstyle="round", solid_joinstyle="round", zorder=5)
    ax.set_title(f"P({threshold}kt winds)", fontsize=9)
    ax.axis("off")
    sm = plt.cm.ScalarMappable(cmap=cmap, norm=norm)
    sm.set_array([])
    cbar = fig.colorbar(sm, ax=ax, orientation="horizontal", fraction=0.035, pad=0.04)
    cbar.ax.tick_params(labelsize=6.5)
    cbar.set_ticks(np.linspace(0, actual_max, 5))
    cbar.set_ticklabels([f"{value:.0%}" for value in np.linspace(0, actual_max, 5)])
    cbar.set_label(f"P({threshold}kt winds)  max {actual_max:.0%}", fontsize=6.5)
    plt.tight_layout(rect=(0, 0.08, 1, 1), pad=0.2)
    return _figure_png_base64(fig, dpi=150)


def _draw_ensemble_density_bands(
    ax: Any,
    members: dict[str, list[tuple[int, float, float]]],
    *,
    cos_lat: float,
) -> None:
    if not members:
        return
    xlim = ax.get_xlim()
    ylim = ax.get_ylim()
    grid_x = np.linspace(xlim[0], xlim[1], 200)
    grid_y = np.linspace(ylim[0], ylim[1], 125)
    gx, gy = np.meshgrid(grid_x, grid_y)
    density = np.zeros(gx.shape, dtype=np.float64)
    radius_degrees = 0.75
    radius2 = radius_degrees**2
    for points in members.values():
        sorted_points = sorted(points, key=lambda point: point[0])
        min_dist2 = np.full(gx.shape, np.inf, dtype=np.float64)
        for index in range(len(sorted_points) - 1):
            _, x1, y1 = sorted_points[index]
            _, x2, y2 = sorted_points[index + 1]
            dx = (x2 - x1) * cos_lat
            dy = y2 - y1
            segment2 = dx * dx + dy * dy
            if segment2 < 1e-12:
                dist2 = ((gx - x1) * cos_lat) ** 2 + (gy - y1) ** 2
            else:
                t = np.clip(((gx - x1) * cos_lat * dx + (gy - y1) * dy) / segment2, 0.0, 1.0)
                nearest_x = x1 + t * (x2 - x1)
                nearest_y = y1 + t * (y2 - y1)
                dist2 = ((gx - nearest_x) * cos_lat) ** 2 + (gy - nearest_y) ** 2
            min_dist2 = np.minimum(min_dist2, dist2)
        if len(sorted_points) == 1:
            _, x, y = sorted_points[0]
            min_dist2 = ((gx - x) * cos_lat) ** 2 + (gy - y) ** 2
        density += np.exp(-0.5 * min_dist2 / radius2)
    density /= len(members)
    fill_colors = ["#deebf7", "#c6dbef", "#9ecae1", "#6baed6", "#3182bd"]
    ax.contourf(
        grid_x,
        grid_y,
        density,
        levels=[0.50, 0.60, 0.70, 0.80, 0.90, 1.01],
        colors=fill_colors,
        alpha=0.60,
        zorder=2,
    )
    contour_levels = [0.50, 0.60, 0.70, 0.80, 0.90]
    contours = ax.contour(
        grid_x,
        grid_y,
        density,
        levels=contour_levels,
        colors=["#9ecae1", "#6baed6", "#3182bd", "#08519c", "#08306b"],
        linewidths=0.7,
        alpha=0.85,
        zorder=4,
    )
    ax.clabel(contours, fmt={level: f"{int(level * 100)}%" for level in contour_levels}, fontsize=5.5, inline=True)


def _figure_png_base64(fig, *, dpi: int) -> str:
    buffer = io.BytesIO()
    fig.savefig(buffer, format="png", dpi=dpi, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    buffer.seek(0)
    return base64.b64encode(buffer.read()).decode("utf-8")


def _records(value: Any) -> list[dict[str, Any]]:
    if value is None:
        return []
    to_dict = getattr(value, "to_dict", None)
    if callable(to_dict):
        try:
            records = to_dict("records")
            if not isinstance(records, list):
                return []
            return [_casefold_record(record) for record in records if isinstance(record, dict)]
        except TypeError:
            pass
    if isinstance(value, list):
        return [_casefold_record(record) for record in value if isinstance(record, dict)]
    return []


def _casefold_record(record: dict[str, Any]) -> dict[str, Any]:
    normalized = dict(record)
    for key, value in record.items():
        normalized.setdefault(str(key).lower(), value)
    return normalized


def _children_at_risk(row: dict[str, Any]) -> float:
    explicit = _float(row.get("children") or row.get("children_at_risk"))
    if explicit:
        return explicit
    return sum(
        _float(row.get(key))
        for key in ["e_school_age_population", "e_infant_population", "e_adolescent_population"]
    )


def _tile_visual_row(row: dict[str, Any]) -> dict[str, Any] | None:
    z = row.get("z") or row.get("ZONE_ID") or row.get("zone_id")
    p = row.get("p") or row.get("PROBABILITY") or row.get("probability")
    if z is None or p is None:
        return None
    return {"z": str(z), "p": float(p)}


def _track_visual_row(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "m": str(row.get("m") or row.get("ENSEMBLE_MEMBER") or row.get("ensemble_member") or "member"),
        "lt": int(_float(row.get("lt") or row.get("LEAD_TIME") or row.get("lead_time"))),
        "lon": _float(row.get("lon") or row.get("LONGITUDE") or row.get("longitude")),
        "lat": _float(row.get("lat") or row.get("LATITUDE") or row.get("latitude")),
    }


def _timing_context_row(row: dict[str, Any]) -> dict[str, Any] | None:
    threshold = row.get("wind_threshold") or row.get("WIND_THRESHOLD")
    if threshold is None:
        return None
    return {
        "wind_threshold": int(_float(threshold)),
        "consensus_impact_hours": row.get("consensus_impact_hours"),
        "consensus_impact_time": row.get("consensus_impact_time"),
        "consensus_local": row.get("consensus_local"),
        "earliest_impact_hours": row.get("earliest_impact_hours"),
        "earliest_local": row.get("earliest_local"),
        "latest_impact_hours": row.get("latest_impact_hours"),
        "latest_local": row.get("latest_local"),
        "tz_offset": row.get("tz_offset"),
        "members_hitting": row.get("members_hitting"),
        "total_members": row.get("total_members"),
    }


def _evolution_visual_row(row: dict[str, Any]) -> dict[str, Any] | None:
    forecast_date = row.get("forecast_date") or row.get("FORECAST_DATE")
    population = row.get("population") or row.get("pop") or row.get("POP")
    if forecast_date is None or population is None:
        return None
    return {
        "forecast_date": str(forecast_date),
        "label": str(row.get("label") or _forecast_label(str(forecast_date))),
        "population": _float(population),
        "infant": _float(row.get("infant") or row.get("INFANT")),
        "school_age": _float(row.get("school_age") or row.get("SCHOOL_AGE")),
        "adolescent": _float(row.get("adolescent") or row.get("ADOLESCENT")),
    }


def _forecast_label(value: str) -> str:
    digits = "".join(ch for ch in value if ch.isdigit())
    if len(digits) >= 10:
        return f"{digits[4:6]}/{digits[6:8]} {digits[8:10]}Z"
    return value


def _norm_key(value: Any) -> str:
    return str(value).strip().casefold()


def _float(value: Any) -> float:
    try:
        if value is None:
            return 0.0
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def _float_or_none(value: Any) -> float | None:
    try:
        if value is None:
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def _hex_to_rgb(value: str) -> tuple[float, float, float]:
    value = value.lstrip("#")
    return (
        int(value[0:2], 16) / 255.0,
        int(value[2:4], 16) / 255.0,
        int(value[4:6], 16) / 255.0,
    )


def _value_color(value: float, max_value: float, colors: list[tuple[float, float, float]]) -> tuple[float, float, float]:
    if value <= 0 or max_value <= 0:
        return (1.0, 1.0, 1.0)
    index = min(int((value / max_value) * len(colors)), len(colors) - 1)
    return colors[index]


def _polygons(geometry):
    return list(geometry.geoms) if geometry.geom_type == "MultiPolygon" else [geometry]


def _wrap_name(name: str, max_chars: int = 12) -> str:
    if len(name) <= max_chars:
        return name
    mid = len(name) // 2
    best_pos = None
    best_dist = len(name)
    for index, char in enumerate(name):
        if char != " ":
            continue
        distance = abs(index - mid)
        if distance < best_dist:
            best_pos = index
            best_dist = distance
    if best_pos is None:
        return name
    return name[:best_pos] + "\n" + name[best_pos + 1 :]


def _admin_geometries(admin_rows: Any) -> list[Any]:
    geometries = []
    for row in admin_rows if isinstance(admin_rows, list) else []:
        if not isinstance(row, dict) or not row.get("geojson"):
            continue
        try:
            geometries.append(shape(json.loads(str(row["geojson"]))))
        except Exception:
            continue
    return geometries


def _qk_bounds(qk: str) -> tuple[float, float, float, float]:
    x = y = 0
    z = len(qk)
    for index, char in enumerate(reversed(qk)):
        mask = 1 << index
        digit = int(char)
        if digit & 1:
            x |= mask
        if digit & 2:
            y |= mask
    n = 1 << z
    west = x / n * 360.0 - 180.0
    east = (x + 1) / n * 360.0 - 180.0
    north = math.degrees(math.atan(math.sinh(math.pi * (1 - 2 * y / n))))
    south = math.degrees(math.atan(math.sinh(math.pi * (1 - 2 * (y + 1) / n))))
    return west, south, east, north


def _first_paragraph_after_heading(expected_alert_html: str, heading: str) -> str:
    parser = _SectionParagraphExtractor(heading)
    parser.feed(expected_alert_html)
    return parser.first_paragraph


def _threshold_rows(report: dict[str, Any]) -> list[dict[str, Any]]:
    rows = []
    for threshold in [34, 40, 50, 64, 83, 96, 113, 137]:
        population = report.get(f"expected_pop_{threshold}") or report.get(f"expected_population_{threshold}")
        children = report.get(f"expected_children_{threshold}")
        if population is None and children is None:
            continue
        rows.append(
            _compact_dict(
                {
                    "wind_threshold": threshold,
                    "population": population,
                    "children": children,
                    "schools": report.get(f"expected_schools_{threshold}"),
                    "health_centers": report.get(f"expected_hcs_{threshold}")
                    or report.get(f"expected_health_centers_{threshold}"),
                    "shelters": report.get(f"expected_shelters_{threshold}"),
                    "wash": report.get(f"expected_wash_{threshold}"),
                }
            )
        )
    return rows


def _top_admin_claims(rows: Any) -> list[dict[str, Any]]:
    if isinstance(rows, list) and rows and isinstance(rows[0], dict) and "population" in rows[0]:
        sorted_rows = sorted(rows, key=lambda row: _float(row.get("population")), reverse=True)
        return [
            _compact_dict({
                "name": row.get("name"),
                "population": row.get("population"),
                "population_delta": row.get("population_delta"),
                "people_in_need": row.get("people_in_need"),
                "schools": row.get("schools"),
                "health_centers": row.get("health_centers"),
                "shelters": row.get("shelters"),
                "wash": row.get("wash"),
            })
            for row in sorted_rows[:5]
            if row.get("name")
        ]
    if not isinstance(rows, list):
        return []
    claims = []
    sorted_rows = sorted(rows, key=lambda row: _float(row.get(str(MAIN_ALERT_THRESHOLD))) if isinstance(row, dict) else 0, reverse=True)
    for row in sorted_rows[:5]:
        if isinstance(row, dict) and row.get("name"):
            claims.append(
                _compact_dict({
                    "name": row.get("name"),
                    "population": row.get(str(MAIN_ALERT_THRESHOLD)),
                    "population_delta": _non_trivial_delta(
                        row.get(f"change_{MAIN_ALERT_THRESHOLD}"), row.get(str(MAIN_ALERT_THRESHOLD))
                    ),
                    "people_in_need": row.get("people_in_need"),
                })
            )
    return claims


def _top_admin_context_rows(report: Any) -> list[dict[str, Any]]:
    if not isinstance(report, dict):
        return _top_admin_claims(report)
    rows = _top_admin_claims(report.get("rows_admins_pop_total", []))
    facility_sources = {
        "schools": _rows_by_name(report.get("rows_schools_winds")),
        "health_centers": _rows_by_name(report.get("rows_hcs_winds")),
        "shelters": _rows_by_name(report.get("rows_shelters_winds")),
        "wash": _rows_by_name(report.get("rows_wash_winds")),
    }
    enriched = []
    for row in rows:
        name = row.get("name")
        item = dict(row)
        for key, source in facility_sources.items():
            if name in source:
                item[key] = source[name].get(str(MAIN_ALERT_THRESHOLD))
        enriched.append(item)
    return enriched


def _rows_by_name(rows: Any) -> dict[Any, dict[str, Any]]:
    if not isinstance(rows, list):
        return {}
    return {row.get("name"): row for row in rows if isinstance(row, dict) and row.get("name")}


def _context_identity(alert_context: dict[str, Any]) -> dict[str, Any]:
    identity = alert_context.get("identity")
    if isinstance(identity, dict):
        return identity
    return {
        "country": alert_context.get("country"),
        "storm": alert_context.get("storm"),
        "forecast_time": alert_context.get("forecast_time"),
    }


def _context_main_threshold(alert_context: dict[str, Any]) -> dict[str, Any]:
    main_threshold = alert_context.get("main_threshold")
    if isinstance(main_threshold, dict):
        return main_threshold
    wind_threshold = main_threshold if isinstance(main_threshold, int) else MAIN_ALERT_THRESHOLD
    return {"wind_threshold": wind_threshold, "label": f"{wind_threshold}kt"}


def _impact_totals_from_legacy(alert_context: dict[str, Any]) -> dict[str, Any]:
    totals = alert_context.get("totals", {})
    if not isinstance(totals, dict):
        return {}
    return _compact_dict(
        {
            "population": totals.get("population"),
            "children": totals.get("children"),
            "schools": totals.get("schools"),
            "health_centers": totals.get("health_centers"),
            "shelters": totals.get("shelters"),
            "wash": totals.get("wash"),
        }
    )


def _people_in_need_from_legacy(alert_context: dict[str, Any]) -> dict[str, Any]:
    totals = alert_context.get("totals", {})
    if not isinstance(totals, dict):
        return {}
    return _compact_dict(
        {
            "population": totals.get("people_in_need"),
            "children": totals.get("children_in_need"),
        }
    )


def _legacy_totals(alert_context: dict[str, Any]) -> dict[str, Any]:
    totals = dict(alert_context.get("impact_totals") or _impact_totals_from_legacy(alert_context))
    people_in_need = alert_context.get("people_in_need") or _people_in_need_from_legacy(alert_context)
    if isinstance(people_in_need, dict):
        if "population" in people_in_need:
            totals["people_in_need"] = people_in_need["population"]
        if "children" in people_in_need:
            totals["children_in_need"] = people_in_need["children"]
    return totals


def _metric_claims(values: Any, *, provenance_labels: list[str]) -> list[dict[str, Any]]:
    if not isinstance(values, dict):
        return []
    return [
        {"metric": key, "value": value, "provenance_labels": provenance_labels}
        for key, value in values.items()
        if value is not None
    ]


def _cross_threshold_claims(values: dict[str, Any]) -> list[dict[str, Any]]:
    rows = values.get("cross_threshold_rows")
    if isinstance(rows, list):
        return [
            {key: value for key, value in row.items() if key != "provenance_labels"}
            for row in rows
            if isinstance(row, dict)
        ]
    legacy_rows = values.get("threshold_rows")
    if isinstance(legacy_rows, list):
        return [row for row in legacy_rows if isinstance(row, dict)]
    return []


def _required_caveat_claims(alert_context: dict[str, Any]) -> list[dict[str, Any]]:
    caveats = alert_context.get("required_caveats")
    if isinstance(caveats, list):
        return [caveat for caveat in caveats if isinstance(caveat, dict)]
    caveat = alert_context.get("required_caveat")
    if caveat:
        return [{"id": "ai_probabilistic_model_outputs", "text": caveat, "provenance_labels": ["inferred"]}]
    return []


def _required_caveat_texts(values: dict[str, Any]) -> list[str]:
    texts = [str(caveat.get("text")) for caveat in _required_caveat_claims(values) if caveat.get("text")]
    if texts:
        return texts
    caveat = values.get("required_caveat")
    fallback: list[str] = [str(caveat)] if caveat else []
    return fallback


def _visual_asset_claims(visual_context: Any) -> list[dict[str, Any]]:
    if not isinstance(visual_context, dict):
        return []
    claims: list[dict[str, Any]] = []
    composition = visual_context.get("impact_composition")
    if isinstance(composition, dict):
        population = composition.get("population")
        if isinstance(population, dict) and population.get("available"):
            claims.append(
                {
                    "kind": "population_composition",
                    "threshold": 50,
                    "alt_text": "Population composition donut chart",
                    "caption": "Composition of total population at risk at the 50 kt threshold.",
                }
            )
        people_in_need = composition.get("people_in_need")
        if isinstance(people_in_need, dict) and people_in_need.get("available"):
            claims.append(
                {
                    "kind": "people_in_need_composition",
                    "threshold": 50,
                    "alt_text": "People in need composition donut chart",
                    "caption": "Composition of people in need at the 50 kt threshold.",
                }
            )
    impact = visual_context.get("impact_evolution")
    if isinstance(impact, dict) and impact.get("available"):
        claims.append(
            {
                "kind": "impact_evolution",
                "threshold": 50,
                "alt_text": "Forecast evolution chart",
                "caption": "Total population at risk at storm-force winds (50 kt) across recent forecast runs.",
            }
        )
    admin = visual_context.get("admin_choropleth")
    if isinstance(admin, dict) and admin.get("available"):
        claims.append(
            {
                "kind": "admin_choropleth",
                "threshold": 50,
                "alt_text": "Admin impact map",
                "caption": "Expected children at risk by administrative area at the 50 kt threshold.",
            }
        )
    ensemble = visual_context.get("ensemble_probability")
    if isinstance(ensemble, dict):
        for threshold in VISUAL_THRESHOLDS:
            entry = ensemble.get(str(threshold))
            if isinstance(entry, dict) and entry.get("available"):
                claims.append(
                    {
                        "kind": "ensemble_probability",
                        "threshold": threshold,
                        "alt_text": f"Wind exposure probability map ({threshold}kt)",
                        "caption": f"Probability of wind exposure at the {threshold} kt threshold.",
                    }
                )
    return claims


def _required_caveat_text(alert_context: dict[str, Any]) -> str:
    texts = _required_caveat_texts(alert_context)
    return texts[0] if texts else AI_PROBABILISTIC_CAVEAT


def _compact_dict(values: dict[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in values.items() if value is not None}


def _table_row(label: str, value: Any) -> str:
    return f"<tr><th style=\"text-align:left; padding:4px 8px;\">{escape(label.replace('_', ' ').title())}</th><td style=\"text-align:right; padding:4px 8px;\">{escape(str(value))}<code>data</code></td></tr>"


def _provenance_labels_html(labels: list[Any]) -> str:
    return " ".join(f"<code>{escape(str(label))}</code>" for label in labels)


def _table_html(caption_id: str, caption: str, headers: list[str], body_rows: str) -> str:
    header_html = "".join(f'<th scope="col">{escape(header)}</th>' for header in headers)
    return (
        '<table aria-describedby="'
        + escape(caption_id)
        + '">'
        + f'<caption id="{escape(caption_id)}">{escape(caption)}</caption>'
        + f"<thead><tr>{header_html}</tr></thead><tbody>{body_rows}</tbody></table>"
    )


def _primary_visual_section(visual_assets: list[dict[str, Any]]) -> str:
    primary = _find_visual_asset(visual_assets, "ensemble_probability", 50)
    if primary is None:
        return ""
    return _visual_section(
        "visual-primary-heading",
        "Wind Exposure Probability - 50kt",
        _visual_asset_figure(primary, primary=True),
        extra_class="visual-primary accent-card",
    )


def _composition_visual_section(visual_assets: list[dict[str, Any]]) -> str:
    assets = [
        asset
        for kind in ("population_composition", "people_in_need_composition")
        if (asset := _find_visual_asset(visual_assets, kind, 50))
    ]
    if not assets:
        return ""
    body = '<div class="visual-secondary-grid">' + "".join(_visual_asset_figure(asset) for asset in assets) + "</div>"
    return _visual_section("visual-composition-heading", "Impact Composition", body)


def _secondary_visual_section(visual_assets: list[dict[str, Any]]) -> str:
    secondary = [asset for threshold in (34, 64) if (asset := _find_visual_asset(visual_assets, "ensemble_probability", threshold))]
    if not secondary:
        return ""
    body = '<div class="visual-secondary-grid">' + "".join(_visual_asset_figure(asset) for asset in secondary) + "</div>"
    return _visual_section(
        "visual-secondary-heading",
        "Additional Wind Probability Views",
        body,
        extra_class="visual-secondary",
    )


def _admin_visual_section(visual_assets: list[dict[str, Any]]) -> str:
    asset = _find_visual_asset(visual_assets, "admin_choropleth", 50)
    if asset is None:
        return ""
    return _visual_section(
        "visual-admin-heading",
        "Expected Children at Risk by Admin Area",
        _visual_asset_figure(asset, primary=True),
    )


def _evolution_visual_section(visual_assets: list[dict[str, Any]]) -> str:
    asset = _find_visual_asset(visual_assets, "impact_evolution", 50)
    if asset is None:
        return ""
    return _visual_section(
        "visual-evolution-heading",
        "Forecast Evolution - Expected People at Risk",
        _visual_asset_figure(asset, primary=True),
    )


def _find_visual_asset(visual_assets: list[dict[str, Any]], kind: str, threshold: int) -> dict[str, Any] | None:
    for asset in visual_assets:
        if asset.get("status") == "rendered" and asset.get("data_uri") and asset.get("kind") == kind and int(asset.get("threshold") or 0) == threshold:
            return asset
    return None


def _visual_section(heading_id: str, heading: str, body: str, *, extra_class: str = "") -> str:
    class_value = " ".join(part for part in ["alert-card", extra_class] if part)
    return (
        f'<section aria-labelledby="{escape(heading_id)}" class="{escape(class_value)}">'
        f'<h2 id="{escape(heading_id)}">{escape(heading)}</h2>'
        f'{body}'
        '</section>'
    )


def _visual_asset_figure(asset: dict[str, Any], *, primary: bool = False) -> str:
    data_uri = escape(str(asset.get("data_uri") or ""), quote=True)
    alt_text = escape(str(asset.get("alt_text") or "Alert visual asset"), quote=True)
    caption = escape(str(asset.get("caption") or "Alert visual asset."))
    labels = _provenance_labels_html(list(asset.get("provenance_labels") or []))
    max_width = "820px" if primary else "430px"
    return (
        '<figure>'
        f'<img src="{data_uri}" alt="{alt_text}" style="width:100%; max-width:{max_width}; display:block; margin:0 auto;" />'
        f'<figcaption>{caption} {labels}</figcaption>'
        '</figure>'
    )


def _slot_value(slots: Mapping[str, Any], *names: str) -> str:
    for name in names:
        value = slots.get(name)
        if value:
            return str(value)
    return ""


def _fact_row(label: str, value_html: str | None) -> str:
    value = value_html if value_html else "Unknown"
    return f'<tr><th scope="row">{escape(label)}</th><td>{value}</td></tr>'


def _metric_rows(values: Any, provenance_labels: list[str]) -> str:
    if not isinstance(values, dict) or not values:
        return _empty_table_row(3, "No values available.")
    rows = []
    for key, value in values.items():
        if value is None:
            continue
        rows.append(
            '<tr>'
            + f'<th scope="row">{escape(key.replace("_", " ").title())}</th>'
            + f'<td>{escape(str(value))}</td>'
            + f'<td>{_provenance_labels_html(provenance_labels)}</td>'
            + '</tr>'
        )
    return "".join(rows) or _empty_table_row(3, "No values available.")


def _admin_area_rows(rows: list[dict[str, Any]]) -> str:
    if not rows:
        return _empty_table_row(8, "No administrative area rows available.")
    rendered = []
    for row in rows:
        name = row.get("name")
        if not name:
            continue
        rendered.append(
            '<tr>'
            + f'<th scope="row">{escape(str(name))}</th>'
            + f'<td>{_display_value(row.get("population"))}{_delta_html(row.get("population_delta"))}</td>'
            + f'<td>{_display_value(row.get("people_in_need"))}</td>'
            + f'<td>{_display_value(row.get("schools"))}</td>'
            + f'<td>{_display_value(row.get("health_centers"))}</td>'
            + f'<td>{_display_value(row.get("shelters"))}</td>'
            + f'<td>{_display_value(row.get("wash"))}</td>'
            + f'<td>{_provenance_labels_html(["data", "inferred"])}</td>'
            + '</tr>'
        )
    return "".join(rendered) or _empty_table_row(8, "No administrative area rows available.")


def _threshold_exposure_rows(rows: list[dict[str, Any]]) -> str:
    if not rows:
        return _empty_table_row(8, "No threshold exposure rows available.")
    rendered = []
    for row in rows:
        threshold = row.get("wind_threshold")
        rendered.append(
            '<tr>'
            + f'<th scope="row">{escape(str(threshold))}kt</th>'
            + f'<td>{_display_value(row.get("population"))}</td>'
            + f'<td>{_display_value(row.get("children"))}</td>'
            + f'<td>{_display_value(row.get("schools"))}</td>'
            + f'<td>{_display_value(row.get("health_centers"))}</td>'
            + f'<td>{_display_value(row.get("shelters"))}</td>'
            + f'<td>{_display_value(row.get("wash"))}</td>'
            + f'<td>{_provenance_labels_html(["data"])}</td>'
            + '</tr>'
        )
    return "".join(rendered)


def _timing_rows(rows: Any) -> str:
    if not isinstance(rows, list) or not rows:
        return ""
    rendered_rows = []
    for row in sorted([row for row in rows if isinstance(row, dict)], key=lambda item: int(_float(item.get("wind_threshold")))):
        threshold = int(_float(row.get("wind_threshold")))
        rendered_rows.append(
            "<tr>"
            + f'<th scope="row">{_wind_level_label(threshold)}</th>'
            + f'<td>{_timing_consensus(row)}</td>'
            + f'<td>{_timing_window(row)}</td>'
            + f'<td>{_timing_scenarios(row)}</td>'
            + "</tr>"
        )
    body = "".join(rendered_rows) or _empty_table_row(4, "No threshold timing rows available.")
    return _table_html(
        "threshold-timing-caption",
        "Expected wind arrival by threshold.",
        ["Wind Level", "Consensus Arrival", "Window (earliest-latest)", "Scenarios"],
        body,
    )


def _wind_level_label(threshold: int) -> str:
    labels = {34: "Storm Force (34kt)", 50: "Strong Storm Force (50kt)", 64: "Cat 1 Hurricane (64kt)"}
    return labels.get(threshold, f"{threshold}kt")


def _timing_consensus(row: dict[str, Any]) -> str:
    hours = row.get("consensus_impact_hours")
    time = row.get("consensus_local") or row.get("consensus_impact_time")
    if hours is None and not time:
        return "-"
    suffix = f" ({escape(str(row.get('tz_offset')))})" if row.get("consensus_local") and row.get("tz_offset") else ""
    return f"{_fmt_hours(hours)} — {escape(str(time))}{suffix}" if time else _fmt_hours(hours)


def _timing_window(row: dict[str, Any]) -> str:
    earliest = row.get("earliest_impact_hours")
    latest = row.get("latest_impact_hours")
    if earliest is None and latest is None:
        return "-"
    return f"{_fmt_hours(earliest)} - {_fmt_hours(latest)}"


def _timing_scenarios(row: dict[str, Any]) -> str:
    members = row.get("members_hitting")
    total = row.get("total_members")
    if members is None or total in (None, 0):
        return "-"
    pct = round(_float(members) / _float(total) * 100)
    return f"{int(_float(members))}/{int(_float(total))} ({pct}%)"


def _fmt_hours(value: Any) -> str:
    if value is None:
        return "-"
    hours = _float(value)
    if hours >= 24:
        return f"~{hours / 24:.1f} days"
    return f"~{int(hours)} hours"


def _required_caveat_items(caveats: list[dict[str, Any]]) -> str:
    if not caveats:
        return "<li>No caveats available.</li>"
    items = []
    for caveat in caveats:
        text = caveat.get("text")
        if not text:
            continue
        items.append(
            f'<li><span>{escape(str(text))}</span> {_provenance_labels_html(caveat.get("provenance_labels", []))}</li>'
        )
    return "".join(items) or "<li>No caveats available.</li>"


def _provenance_list_items(labels: Any) -> str:
    if not isinstance(labels, list) or not labels:
        return "<li><code>none</code></li>"
    return "".join(f"<li><code>{escape(str(label))}</code></li>" for label in labels)


def _display_value(value: Any) -> str:
    return escape(str(value)) if value is not None else "Not available"


def _non_trivial_delta(delta: Any, current: Any) -> Any | None:
    if delta is None:
        return None
    delta_value = _float(delta)
    current_value = _float(current)
    if delta_value == 0 or abs(delta_value) == abs(current_value):
        return None
    return delta


def _delta_html(delta: Any) -> str:
    if delta is None:
        return ""
    value = _float(delta)
    if value == 0:
        return ""
    arrow = "▲" if value > 0 else "▼"
    color = "#c0392b" if value > 0 else "#27ae60"
    sign = "+" if value > 0 else "−"
    return f' <span style="color:{color}; font-weight:bold;">{arrow} {sign}{int(abs(value)):,}</span>'


def _empty_table_row(column_count: int, message: str) -> str:
    return f'<tr><td colspan="{column_count}">{escape(message)}</td></tr>'


def _time_html(value: Any) -> str:
    if value is None:
        return "Unknown"
    escaped = escape(str(value))
    return f'<time datetime="{escaped}">{escaped}</time>'


def _failure(code: str, message: str) -> ComparisonIssue:
    return ComparisonIssue(severity="failure", code=code, message=message)


def _warning(code: str, message: str) -> ComparisonIssue:
    return ComparisonIssue(severity="warning", code=code, message=message)


def _main_threshold_label(alert_claims: dict[str, Any]) -> str | None:
    main_threshold = alert_claims.get("main_threshold")
    if isinstance(main_threshold, dict):
        label = main_threshold.get("label")
        if label is not None:
            return str(label)
        wind_threshold = main_threshold.get("wind_threshold")
        if wind_threshold is not None:
            return f"{wind_threshold}kt"
    return None


def _presentation_evidence(rendered_alert_html: str) -> _AlertPresentationEvidence:
    parser = _PresentationEvidenceExtractor()
    parser.feed(rendered_alert_html)
    parser.close()
    return _AlertPresentationEvidence(
        text=" ".join(parser.parts),
        tables=tuple(parser.tables),
        images=tuple(parser.images),
        list_items=tuple(parser.list_items),
    )


def _facts_table(tables: tuple[_AlertTableEvidence, ...]) -> dict[str, str]:
    table = _find_table(tables, headers=("fact", "value"), caption_contains="alert facts")
    if table is None:
        return {}
    return {
        _normalize_text(row[0]): row[1]
        for row in table.rows
        if len(row) >= 2 and row[0].strip() and row[1].strip()
    }


def _metric_table(table: _AlertTableEvidence | None) -> dict[str, dict[str, Any]]:
    if table is None:
        return {}
    values: dict[str, dict[str, Any]] = {}
    for row in table.rows:
        if len(row) < 2:
            continue
        metric = _normalize_metric_name(row[0])
        if not metric:
            continue
        provenance_cell = row[2] if len(row) > 2 else ""
        values[metric] = {"value": row[1], "provenance_labels": _extract_labels(provenance_cell)}
    return values


def _admin_area_table(table: _AlertTableEvidence | None) -> dict[str, dict[str, Any]]:
    if table is None:
        return {}
    values: dict[str, dict[str, Any]] = {}
    for row in table.rows:
        if len(row) < 3:
            continue
        area = _normalize_text(row[0])
        if not area:
            continue
        provenance_cell = row[7] if len(row) > 7 else row[-1]
        values[area] = {
            "population": row[1],
            "people_in_need": row[2],
            "schools": row[3] if len(row) > 3 else None,
            "health_centers": row[4] if len(row) > 4 else None,
            "shelters": row[5] if len(row) > 5 else None,
            "wash": row[6] if len(row) > 6 else None,
            "provenance_labels": _extract_labels(provenance_cell),
        }
    return values


def _threshold_table(table: _AlertTableEvidence | None) -> dict[str, dict[str, Any]]:
    if table is None:
        return {}
    values: dict[str, dict[str, Any]] = {}
    for row in table.rows:
        if len(row) < 3:
            continue
        threshold = _normalize_threshold(row[0])
        if not threshold:
            continue
        provenance_cell = row[7] if len(row) > 7 else row[-1]
        values[threshold] = {
            "population": row[1],
            "children": row[2],
            "schools": row[3] if len(row) > 3 else None,
            "health_centers": row[4] if len(row) > 4 else None,
            "shelters": row[5] if len(row) > 5 else None,
            "wash": row[6] if len(row) > 6 else None,
            "provenance_labels": _extract_labels(provenance_cell),
        }
    return values


def _find_table(
    tables: tuple[_AlertTableEvidence, ...], *, headers: tuple[str, ...], caption_contains: str
) -> _AlertTableEvidence | None:
    normalized_headers = tuple(_normalize_text(header) for header in headers)
    normalized_caption = _normalize_text(caption_contains)
    for table in tables:
        if tuple(_normalize_text(header) for header in table.headers) != normalized_headers:
            continue
        caption = _normalize_text(table.caption)
        if not normalized_caption or normalized_caption in caption:
            return table
    return None


def _fact_value_matches(facts: dict[str, str], label: str, expected: Any, text_fallback: str) -> bool:
    actual = facts.get(_normalize_text(label))
    if actual is not None:
        return _normalize_text(actual) == _normalize_text(expected)
    return _normalize_text(expected) in _normalize_text(text_fallback)


def _claim_rows(values: Any) -> list[dict[str, Any]]:
    if not isinstance(values, list):
        return []
    return [value for value in values if isinstance(value, dict)]


def _metric_claim_matches(rows: dict[str, dict[str, Any]], claim: dict[str, Any]) -> bool:
    metric = _normalize_metric_name(claim.get("metric"))
    if not metric:
        return True
    row = rows.get(metric)
    if row is None:
        return False
    if not _value_matches(row.get("value"), claim.get("value")):
        return False
    return _labels_match(row.get("provenance_labels"), claim.get("provenance_labels"))


def _admin_area_claim_matches(rows: dict[str, dict[str, Any]], claim: dict[str, Any]) -> bool:
    name = _normalize_text(claim.get("name"))
    if not name:
        return True
    row = rows.get(name)
    if row is None:
        return False
    if not _optional_value_matches(row.get("population"), claim.get("population")):
        return False
    if not _optional_value_matches(row.get("people_in_need"), claim.get("people_in_need")):
        return False
    for key in ["schools", "health_centers", "shelters", "wash"]:
        if not _optional_value_matches(row.get(key), claim.get(key)):
            return False
    return _labels_match(row.get("provenance_labels"), claim.get("provenance_labels"))


def _threshold_claim_matches(rows: dict[str, dict[str, Any]], claim: dict[str, Any]) -> bool:
    threshold = _normalize_threshold(claim.get("wind_threshold"))
    if not threshold:
        return True
    row = rows.get(threshold)
    if row is None:
        return False
    if not _optional_value_matches(row.get("population"), claim.get("population")):
        return False
    if not _optional_value_matches(row.get("children"), claim.get("children")):
        return False
    for key in ["schools", "health_centers", "shelters", "wash"]:
        if not _optional_value_matches(row.get(key), claim.get(key)):
            return False
    return _labels_match(row.get("provenance_labels"), claim.get("provenance_labels"))


def _visual_asset_claim_matches(images: tuple[_AlertImageEvidence, ...], claim: dict[str, Any]) -> bool:
    alt = _normalize_text(claim.get("alt_text"))
    caption = _normalize_text(claim.get("caption"))
    if not alt:
        return True
    for image in images:
        if alt != _normalize_text(image.alt_text):
            continue
        if caption and caption not in _normalize_text(image.caption):
            return False
        return True
    return False


def _metric_claim_message(kind: str, claim: dict[str, Any]) -> str:
    return f"rendered alert is missing {kind} claim evidence: {claim.get('metric')}={claim.get('value')}"


def _admin_area_claim_message(claim: dict[str, Any]) -> str:
    return (
        "rendered alert is missing top admin area claim evidence: "
        f"{claim.get('name')} population={claim.get('population')} people_in_need={claim.get('people_in_need')}"
    )


def _threshold_claim_message(claim: dict[str, Any]) -> str:
    return (
        "rendered alert is missing threshold exposure claim evidence: "
        f"{claim.get('wind_threshold')}kt population={claim.get('population')} children={claim.get('children')}"
    )


def _text_or_list_item_matches(evidence: _AlertPresentationEvidence, expected: Any) -> bool:
    normalized_expected = _normalize_text(expected)
    if normalized_expected in _normalize_text(evidence.text):
        return True
    return any(normalized_expected in _normalize_text(item) for item in evidence.list_items)


def _value_matches(actual: Any, expected: Any) -> bool:
    return _normalize_text(actual) == _normalize_text(expected)


def _optional_value_matches(actual: Any, expected: Any) -> bool:
    if expected is None:
        return True
    return _value_matches(actual, expected)


def _labels_match(actual: Any, expected: Any) -> bool:
    expected_labels = _extract_labels(expected)
    if not expected_labels:
        return True
    actual_labels = _extract_labels(actual)
    return expected_labels.issubset(actual_labels)


def _extract_labels(values: Any) -> set[str]:
    if isinstance(values, (list, tuple, set, frozenset)):
        return {_normalize_text(value) for value in values if _normalize_text(value)}
    if values is None:
        return set()
    return {_normalize_text(part) for part in str(values).split() if _normalize_text(part)}


def _normalize_metric_name(value: Any) -> str:
    return _normalize_text(str(value).replace("_", " "))


def _normalize_threshold(value: Any) -> str:
    if value is None:
        return ""
    text = _normalize_text(value)
    if not text:
        return ""
    return text if text.endswith("kt") else f"{text}kt"


def _normalize_text(value: Any) -> str:
    return " ".join(str(value).split()).casefold() if value is not None else ""


def _html_text(value: str) -> str:
    parser = _TextExtractor()
    parser.feed(value)
    return " ".join(parser.parts)


class _TextExtractor(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.parts: list[str] = []

    def handle_data(self, data: str) -> None:
        stripped = data.strip()
        if stripped:
            self.parts.append(stripped)


class _SectionParagraphExtractor(HTMLParser):
    def __init__(self, heading: str) -> None:
        super().__init__()
        self.heading = heading.casefold()
        self.first_paragraph = ""
        self._heading_parts: list[str] = []
        self._paragraph_parts: list[str] = []
        self._capturing_heading = False
        self._capturing_paragraph = False
        self._in_target_section = False

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag in {"h1", "h2", "h3", "h4", "h5", "h6"}:
            self._capturing_heading = True
            self._heading_parts = []
        elif tag == "p" and self._in_target_section and not self.first_paragraph:
            self._capturing_paragraph = True
            self._paragraph_parts = []

    def handle_endtag(self, tag: str) -> None:
        if tag in {"h1", "h2", "h3", "h4", "h5", "h6"} and self._capturing_heading:
            heading_text = " ".join(self._heading_parts).strip()
            self._capturing_heading = False
            self._in_target_section = heading_text.casefold() == self.heading
        elif tag == "p" and self._capturing_paragraph:
            paragraph = " ".join(self._paragraph_parts).strip()
            self._capturing_paragraph = False
            if paragraph and not self.first_paragraph:
                self.first_paragraph = paragraph

    def handle_data(self, data: str) -> None:
        stripped = data.strip()
        if not stripped:
            return
        if self._capturing_heading:
            self._heading_parts.append(stripped)
        if self._capturing_paragraph:
            self._paragraph_parts.append(stripped)


class _PresentationEvidenceExtractor(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.parts: list[str] = []
        self.tables: list[_AlertTableEvidence] = []
        self.images: list[_AlertImageEvidence] = []
        self.list_items: list[str] = []
        self._table_caption_parts: list[str] = []
        self._table_headers: list[str] = []
        self._table_rows: list[tuple[str, ...]] = []
        self._row_cells: list[str] = []
        self._cell_parts: list[str] = []
        self._list_item_parts: list[str] = []
        self._figure_image_alt: str | None = None
        self._figure_caption_parts: list[str] = []
        self._in_table = False
        self._in_caption = False
        self._in_figcaption = False
        self._in_cell = False
        self._in_list_item = False
        self._table_section: str | None = None

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attrs_dict = {key: value for key, value in attrs}
        if tag == "table":
            self._in_table = True
            self._table_caption_parts = []
            self._table_headers = []
            self._table_rows = []
        elif tag == "caption" and self._in_table:
            self._in_caption = True
            self._table_caption_parts = []
        elif tag in {"thead", "tbody"} and self._in_table:
            self._table_section = tag
        elif tag == "tr" and self._in_table:
            self._row_cells = []
        elif tag in {"th", "td"} and self._in_table:
            self._in_cell = True
            self._cell_parts = []
        elif tag == "li":
            self._in_list_item = True
            self._list_item_parts = []
        elif tag == "figure":
            self._figure_image_alt = None
            self._figure_caption_parts = []
        elif tag == "img":
            self._figure_image_alt = attrs_dict.get("alt") or ""
        elif tag == "figcaption":
            self._in_figcaption = True
            self._figure_caption_parts = []

    def handle_endtag(self, tag: str) -> None:
        if tag == "caption" and self._in_caption:
            self._in_caption = False
        elif tag in {"th", "td"} and self._in_cell:
            self._in_cell = False
            self._row_cells.append(" ".join(self._cell_parts).strip())
        elif tag == "tr" and self._in_table and self._row_cells:
            row = tuple(cell for cell in self._row_cells)
            if self._table_section == "thead":
                self._table_headers = list(row)
            else:
                self._table_rows.append(row)
            self._row_cells = []
        elif tag in {"thead", "tbody"}:
            self._table_section = None
        elif tag == "table" and self._in_table:
            self._in_table = False
            self.tables.append(
                _AlertTableEvidence(
                    caption=" ".join(self._table_caption_parts).strip(),
                    headers=tuple(self._table_headers),
                    rows=tuple(self._table_rows),
                )
            )
        elif tag == "li" and self._in_list_item:
            self._in_list_item = False
            item = " ".join(self._list_item_parts).strip()
            if item:
                self.list_items.append(item)
        elif tag == "figcaption" and self._in_figcaption:
            self._in_figcaption = False
        elif tag == "figure":
            if self._figure_image_alt is not None:
                self.images.append(
                    _AlertImageEvidence(
                        alt_text=self._figure_image_alt,
                        caption=" ".join(self._figure_caption_parts).strip(),
                    )
                )
            self._figure_image_alt = None
            self._figure_caption_parts = []

    def handle_data(self, data: str) -> None:
        stripped = data.strip()
        if not stripped:
            return
        self.parts.append(stripped)
        if self._in_caption:
            self._table_caption_parts.append(stripped)
        if self._in_cell:
            self._cell_parts.append(stripped)
        if self._in_list_item:
            self._list_item_parts.append(stripped)
        if self._in_figcaption:
            self._figure_caption_parts.append(stripped)

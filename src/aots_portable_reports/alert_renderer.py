from __future__ import annotations

from dataclasses import dataclass
from html import escape
from html.parser import HTMLParser
from typing import Any, Mapping, Protocol, TypedDict

from aots_portable_reports.alert_contract import ALERT_PROVENANCE_LABELS
from aots_portable_reports.models import ComparisonIssue, ComparisonReport, ReportSnapshot


MAIN_ALERT_THRESHOLD = 50
SITUATION_SUMMARY_HEADING = "Situation Summary"
SITUATION_SUMMARY_SLOT = "situation_summary"
AI_PROBABILISTIC_CAVEAT = "AI system based on probabilistic model outputs"


class AlertProseSlots(TypedDict, total=False):
    situation_summary: str


@dataclass(frozen=True)
class AlertProseRequest:
    alert_context: dict[str, Any]
    expected_alert_html: str | None = None


class AlertProseProvider(Protocol):
    def provide_prose_slots(self, request: AlertProseRequest) -> dict[str, str]: ...


class BaselineReplayAlertProseProvider:
    def provide_prose_slots(self, request: AlertProseRequest) -> dict[str, str]:
        return {SITUATION_SUMMARY_SLOT: baseline_replay_summary_prose(request.expected_alert_html)}


DEFAULT_ALERT_PROSE_PROVIDER: AlertProseProvider = BaselineReplayAlertProseProvider()


@dataclass(frozen=True)
class _AlertTableEvidence:
    caption: str
    headers: tuple[str, ...]
    rows: tuple[tuple[str, ...], ...]


@dataclass(frozen=True)
class _AlertPresentationEvidence:
    text: str
    tables: tuple[_AlertTableEvidence, ...]
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
    top_admin_areas = _top_admin_context_rows(report.get("rows_admins_pop_total", []))
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
        "required_caveat": required_caveats[0]["text"] if required_caveats else None,
    }


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


def render_alert_html(alert_context: dict[str, Any], *, prose_slots: AlertProseSlots | None = None) -> str:
    situation_summary = _bounded_alert_prose_slots(prose_slots or {}).get(SITUATION_SUMMARY_SLOT, "")
    identity = _context_identity(alert_context)
    main_threshold = _context_main_threshold(alert_context)
    title = f"Storm {identity.get('storm', 'Unknown')} - {identity.get('country', 'Unknown')}"
    summary_html = escape(situation_summary) if situation_summary else "No bounded summary prose was available."
    facts_rows = "".join(
        [
            _fact_row("Storm", identity.get("storm")),
            _fact_row("Country", identity.get("country")),
            _fact_row("Forecast Issued", _time_html(identity.get("forecast_time"))),
            _fact_row("Alert Threshold", escape(str(main_threshold.get("label", f"{MAIN_ALERT_THRESHOLD}kt")))),
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
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <title>{escape(title)}</title>
</head>
<body style="margin:0; background:#f4f7f8; color:#16313a; font-family:Georgia, 'Times New Roman', serif; line-height:1.5;">
  <div style="max-width:900px; margin:0 auto; background:#ffffff;">
    <header style="background:#0f5a6b; color:#ffffff; padding:24px 28px 20px;">
      <p style="margin:0; font-size:12px; font-weight:700; letter-spacing:1.2px; text-transform:uppercase;">Ahead of the Storm - Hybrid Alert Artifact</p>
      <h1 style="margin:10px 0 6px; font-size:30px; line-height:1.2;">{escape(title)}</h1>
      <p style="margin:0; font-size:16px;">Reviewable alert email artifact for structured forecast facts, bounded prose, and provenance labels.</p>
    </header>
    <main style="padding:24px 28px 32px;">
      <section aria-labelledby="summary-heading" style="margin:0 0 24px;">
        <h2 id="summary-heading" style="margin:0 0 10px; font-size:22px;">{SITUATION_SUMMARY_HEADING}</h2>
        <p style="margin:0;">{summary_html}</p>
      </section>
      <section aria-labelledby="facts-heading" style="margin:0 0 24px;">
        <h2 id="facts-heading" style="margin:0 0 10px; font-size:22px;">Alert Facts</h2>
        {_table_html("alert-facts-caption", "Key alert facts derived from structured report inputs.", ["Fact", "Value"], facts_rows)}
      </section>
      <section aria-labelledby="impact-heading" style="margin:0 0 24px;">
        <h2 id="impact-heading" style="margin:0 0 10px; font-size:22px;">Expected Impact Totals</h2>
        {_table_html("impact-totals-caption", f"Expected impact totals for the {escape(str(main_threshold.get('label', f'{MAIN_ALERT_THRESHOLD}kt')))} threshold.", ["Metric", "Value", "Provenance"], impact_rows)}
      </section>
      <section aria-labelledby="people-heading" style="margin:0 0 24px;">
        <h2 id="people-heading" style="margin:0 0 10px; font-size:22px;">People in Need</h2>
        {_table_html("people-in-need-caption", "Inferred people-in-need values used for review.", ["Metric", "Value", "Provenance"], people_in_need_rows)}
      </section>
      <section aria-labelledby="admin-heading" style="margin:0 0 24px;">
        <h2 id="admin-heading" style="margin:0 0 10px; font-size:22px;">Most Affected Administrative Areas</h2>
        {_table_html("admin-areas-caption", "Administrative areas with the highest 50kt population exposure.", ["Area", "Population", "People in Need", "Provenance"], admin_rows)}
      </section>
      <section aria-labelledby="threshold-heading" style="margin:0 0 24px;">
        <h2 id="threshold-heading" style="margin:0 0 10px; font-size:22px;">Threshold Exposure</h2>
        {_table_html("threshold-exposure-caption", "Population and children exposed across wind thresholds.", ["Wind Threshold", "Population", "Children", "Provenance"], threshold_rows)}
      </section>
      <section aria-labelledby="caveats-heading" style="margin:0 0 24px;">
        <h2 id="caveats-heading" style="margin:0 0 10px; font-size:22px;">Required Caveats</h2>
        <ul style="margin:0; padding-left:20px;">{caveat_items}</ul>
      </section>
      <section aria-labelledby="provenance-heading">
        <h2 id="provenance-heading" style="margin:0 0 10px; font-size:22px;">Provenance Labels</h2>
        <ul style="margin:0; padding-left:20px;">{provenance_items}</ul>
      </section>
    </main>
    <footer style="background:#edf3f4; padding:16px 28px 20px; border-top:1px solid #d6e2e4;">
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
            headers=("area", "population", "people in need", "provenance"),
            caption_contains="administrative",
        )
    )
    threshold_rows = _threshold_table(
        _find_table(
            evidence.tables,
            headers=("wind threshold", "population", "children", "provenance"),
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
    if not cross_threshold_claims:
        warnings.append(_warning("missing_threshold_claims", "no cross-threshold alert claims were available"))
    return ComparisonReport(status="failed" if failures else "passed", failures=failures, warnings=warnings)


def baseline_replay_summary_prose(expected_alert_html: str | None) -> str:
    if not expected_alert_html:
        return ""
    paragraph = _first_paragraph_after_heading(expected_alert_html, SITUATION_SUMMARY_HEADING)
    if paragraph:
        return paragraph
    text = _html_text(expected_alert_html)
    marker = SITUATION_SUMMARY_HEADING
    if marker in text:
        return text.split(marker, maxsplit=1)[1].strip()
    return text.strip()


def _bounded_alert_prose_slots(values: Mapping[str, Any]) -> AlertProseSlots:
    bounded: AlertProseSlots = {}
    situation_summary = values.get(SITUATION_SUMMARY_SLOT)
    if situation_summary is not None:
        bounded[SITUATION_SUMMARY_SLOT] = str(situation_summary)
    return bounded


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
        rows.append({"wind_threshold": threshold, "population": population, "children": children})
    return rows


def _top_admin_claims(rows: Any) -> list[dict[str, Any]]:
    if isinstance(rows, list) and rows and isinstance(rows[0], dict) and "population" in rows[0]:
        return [
            {
                "name": row.get("name"),
                "population": row.get("population"),
                "people_in_need": row.get("people_in_need"),
            }
            for row in rows[:5]
            if row.get("name")
        ]
    if not isinstance(rows, list):
        return []
    claims = []
    for row in rows[:5]:
        if isinstance(row, dict) and row.get("name"):
            claims.append(
                {
                    "name": row.get("name"),
                    "population": row.get(str(MAIN_ALERT_THRESHOLD)),
                    "people_in_need": row.get("people_in_need"),
                }
            )
    return claims


def _top_admin_context_rows(rows: Any) -> list[dict[str, Any]]:
    return _top_admin_claims(rows)


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
        return _empty_table_row(4, "No administrative area rows available.")
    rendered = []
    for row in rows:
        name = row.get("name")
        if not name:
            continue
        rendered.append(
            '<tr>'
            + f'<th scope="row">{escape(str(name))}</th>'
            + f'<td>{_display_value(row.get("population"))}</td>'
            + f'<td>{_display_value(row.get("people_in_need"))}</td>'
            + f'<td>{_provenance_labels_html(["data", "inferred"])}</td>'
            + '</tr>'
        )
    return "".join(rendered) or _empty_table_row(4, "No administrative area rows available.")


def _threshold_exposure_rows(rows: list[dict[str, Any]]) -> str:
    if not rows:
        return _empty_table_row(4, "No threshold exposure rows available.")
    rendered = []
    for row in rows:
        threshold = row.get("wind_threshold")
        rendered.append(
            '<tr>'
            + f'<th scope="row">{escape(str(threshold))}kt</th>'
            + f'<td>{_display_value(row.get("population"))}</td>'
            + f'<td>{_display_value(row.get("children"))}</td>'
            + f'<td>{_provenance_labels_html(["data"])}</td>'
            + '</tr>'
        )
    return "".join(rendered)


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
        provenance_cell = row[3] if len(row) > 3 else ""
        values[area] = {
            "population": row[1],
            "people_in_need": row[2],
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
        provenance_cell = row[3] if len(row) > 3 else ""
        values[threshold] = {
            "population": row[1],
            "children": row[2],
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
    return _labels_match(row.get("provenance_labels"), claim.get("provenance_labels"))


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
        self.list_items: list[str] = []
        self._table_caption_parts: list[str] = []
        self._table_headers: list[str] = []
        self._table_rows: list[tuple[str, ...]] = []
        self._row_cells: list[str] = []
        self._cell_parts: list[str] = []
        self._list_item_parts: list[str] = []
        self._in_table = False
        self._in_caption = False
        self._in_cell = False
        self._in_list_item = False
        self._table_section: str | None = None

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        del attrs
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

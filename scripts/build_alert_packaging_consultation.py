from __future__ import annotations

import argparse
import hashlib
import html
import json
import re
import shutil
from pathlib import Path
from string import Template
from typing import Any


ALTERNATIVES = (
    "combined-long",
    "concise-email",
    "concise-linked-report",
    "expanded-email",
)
RECOMMENDED_ALTERNATIVE = "concise-linked-report"
EXPECTED_SCENARIOS = {
    "official-alert": "alert",
    "official-warning": "warning",
    "forecast-only-warning": "warning",
}
TOP_LEVEL_FIELDS = {
    "schema_version",
    "scenario_id",
    "classification",
    "display_name",
    "country_name",
    "product_decision",
    "official_status",
    "local_threat",
    "forecast_conditioned_need",
    "hazards",
    "forecast_evolution",
    "provenance",
}
NESTED_FIELDS = {
    "official_status": {"availability", "classification", "valid_at"},
    "local_threat": {
        "threshold_kt",
        "horizon_hours",
        "cumulative",
        "maximum_probability",
        "nonzero_tile_count",
        "expected_population",
        "expected_children",
    },
    "forecast_conditioned_need": {"pin", "chin"},
    "hazards": {"wind", "rainfall", "storm_surge"},
    "provenance": {"label", "as_of"},
}
EVOLUTION_FIELDS = {"label", "modeled_exposure"}
DISALLOWED_TEXT = re.compile(r"https?://|[\w.+-]+@[\w.-]+|<[^>]+>", re.IGNORECASE)


class ConsultationInputError(ValueError):
    """Raised when a consultation display fixture violates its narrow contract."""


def _read_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text())
    except (OSError, json.JSONDecodeError) as exc:
        raise ConsultationInputError(f"invalid scenario JSON: {path.name}") from exc
    if not isinstance(value, dict):
        raise ConsultationInputError(f"scenario must be an object: {path.name}")
    return value


def _require_exact_fields(value: dict[str, Any], allowed: set[str], label: str) -> None:
    unexpected = set(value) - allowed
    missing = allowed - set(value)
    if unexpected:
        raise ConsultationInputError(
            f"{label} has undeclared fields: {', '.join(sorted(unexpected))}"
        )
    if missing:
        raise ConsultationInputError(f"{label} is missing fields: {', '.join(sorted(missing))}")


def _validate_text(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ConsultationInputError(f"{label} must be non-empty text")
    if DISALLOWED_TEXT.search(value):
        raise ConsultationInputError(f"{label} contains prohibited text")
    return value


def _validate_nested_fields(scenario: dict[str, Any], scenario_id: str) -> None:
    for field_name, allowed in NESTED_FIELDS.items():
        value = scenario[field_name]
        if not isinstance(value, dict):
            raise ConsultationInputError(f"{scenario_id}.{field_name} must be an object")
        _require_exact_fields(value, allowed, f"{scenario_id}.{field_name}")

    evolution = scenario["forecast_evolution"]
    if not isinstance(evolution, list) or not evolution:
        raise ConsultationInputError(f"{scenario_id}.forecast_evolution must be a non-empty list")
    for index, item in enumerate(evolution):
        if not isinstance(item, dict):
            raise ConsultationInputError(f"{scenario_id}.forecast_evolution[{index}] is invalid")
        _require_exact_fields(
            item,
            EVOLUTION_FIELDS,
            f"{scenario_id}.forecast_evolution[{index}]",
        )


def _validate_semantics(scenario: dict[str, Any]) -> None:
    scenario_id = str(scenario["scenario_id"])
    decision = scenario["product_decision"]
    if decision != EXPECTED_SCENARIOS[scenario_id]:
        raise ConsultationInputError(f"{scenario_id} has an invalid supplied Product Decision")

    threat = scenario["local_threat"]
    if (
        threat["threshold_kt"] != 34
        or threat["horizon_hours"] != 144
        or threat["cumulative"] is not True
    ):
        raise ConsultationInputError(
            f"{scenario_id} must use complete cumulative 144-hour 34 kt data"
        )
    if not 0.005 < threat["maximum_probability"] <= 1:
        raise ConsultationInputError(f"{scenario_id} has an invalid 34 kt probability")
    if threat["nonzero_tile_count"] < 3 or threat["expected_population"] <= 0:
        raise ConsultationInputError(f"{scenario_id} does not satisfy the synthetic threat fixture")
    if not 0 <= threat["expected_children"] <= threat["expected_population"]:
        raise ConsultationInputError(f"{scenario_id} has invalid modeled child exposure")

    need = scenario["forecast_conditioned_need"]
    if not 0 <= need["chin"] <= need["pin"]:
        raise ConsultationInputError(f"{scenario_id} must satisfy CHiN <= PiN")
    if scenario["hazards"] != {
        "wind": "available",
        "rainfall": "unavailable",
        "storm_surge": "unavailable",
    }:
        raise ConsultationInputError(f"{scenario_id} has unsupported hazard availability")

    official = scenario["official_status"]
    if scenario_id == "official-alert":
        expected_official = {"availability": "available", "classification": "Hurricane"}
    elif scenario_id == "official-warning":
        expected_official = {"availability": "available", "classification": "Tropical Storm"}
    else:
        expected_official = {"availability": "unavailable", "classification": "Unavailable"}
    for key, expected in expected_official.items():
        if official[key] != expected:
            raise ConsultationInputError(f"{scenario_id} has an invalid official status")


def _validate_scenario(scenario: dict[str, Any], source_name: str) -> dict[str, Any]:
    _require_exact_fields(scenario, TOP_LEVEL_FIELDS, source_name)
    scenario_id = scenario.get("scenario_id")
    if scenario_id not in EXPECTED_SCENARIOS:
        raise ConsultationInputError(f"unsupported scenario_id in {source_name}")
    if scenario["schema_version"] != "consultation-display-v1":
        raise ConsultationInputError(f"unsupported schema_version in {source_name}")
    if scenario["classification"] != "synthetic_public":
        raise ConsultationInputError(f"{scenario_id} must be classified synthetic_public")
    for field_name in ("display_name", "country_name", "product_decision"):
        _validate_text(scenario[field_name], f"{scenario_id}.{field_name}")
    _validate_nested_fields(scenario, scenario_id)
    for field_name in ("classification", "valid_at"):
        _validate_text(scenario["official_status"][field_name], f"{scenario_id}.official_status")
    for field_name in ("label", "as_of"):
        _validate_text(scenario["provenance"][field_name], f"{scenario_id}.provenance")
    for item in scenario["forecast_evolution"]:
        _validate_text(item["label"], f"{scenario_id}.forecast_evolution.label")
        if not isinstance(item["modeled_exposure"], int) or item["modeled_exposure"] < 0:
            raise ConsultationInputError(f"{scenario_id} has invalid forecast evolution")
    _validate_semantics(scenario)
    return scenario


def _load_scenarios(scenario_dir: Path) -> list[dict[str, Any]]:
    scenarios = [
        _validate_scenario(_read_json(path), path.name)
        for path in sorted(scenario_dir.glob("*.json"))
    ]
    ids = {scenario["scenario_id"] for scenario in scenarios}
    if ids != set(EXPECTED_SCENARIOS):
        raise ConsultationInputError(
            "scenario directory must contain exactly three evidence states"
        )
    return sorted(scenarios, key=lambda item: str(item["scenario_id"]))


def _read_template(template_dir: Path, name: str) -> Template:
    path = template_dir / name
    try:
        return Template(path.read_text())
    except OSError as exc:
        raise ConsultationInputError(f"missing template: {name}") from exc


def _safe(value: Any) -> str:
    return html.escape(str(value), quote=True)


def _integer(value: int) -> str:
    return f"{value:,}"


def _official_status(scenario: dict[str, Any]) -> str:
    official = scenario["official_status"]
    if official["availability"] == "unavailable":
        return "Official status unavailable"
    return f"Official global status: {_safe(official['classification'])}"


def _facts_table(scenario: dict[str, Any], caption: str) -> str:
    threat = scenario["local_threat"]
    need = scenario["forecast_conditioned_need"]
    rows = (
        ("Supplied Product Decision", str(scenario["product_decision"]).title()),
        ("Official current state", _official_status(scenario)),
        ("Local Country Threat", "Complete cumulative 144-hour local threat at 34 kt"),
        ("Maximum local 34 kt probability", f"{threat['maximum_probability']:.1%}"),
        ("Modeled population exposure", _integer(threat["expected_population"])),
        ("Modeled child exposure", _integer(threat["expected_children"])),
        ("Forecast-conditioned PiN", _integer(need["pin"])),
        ("Forecast-conditioned CHiN", _integer(need["chin"])),
        ("Rainfall", "Rainfall unavailable"),
        ("Storm surge", "Storm surge unavailable"),
    )
    body = "".join(
        f'<tr><th scope="row">{_safe(label)}</th><td>{_safe(value)}</td></tr>'
        for label, value in rows
    )
    return (
        '<div class="table-scroll"><table><caption>'
        f"{_safe(caption)}</caption><tbody>{body}</tbody></table></div>"
    )


def _evolution_table(scenario: dict[str, Any]) -> str:
    rows = "".join(
        "<tr>"
        f'<th scope="row">{_safe(item["label"])}</th>'
        f"<td>{_safe(_integer(item['modeled_exposure']))}</td>"
        "</tr>"
        for item in scenario["forecast_evolution"]
    )
    return (
        '<div class="table-scroll"><table><caption>Supplied synthetic forecast evolution; '
        'not an observed trend</caption><thead><tr><th scope="col">Forecast issue</th>'
        f'<th scope="col">Modeled exposure</th></tr></thead><tbody>{rows}</tbody></table></div>'
    )


def _common_summary(scenario: dict[str, Any]) -> str:
    threat = scenario["local_threat"]
    return (
        f"<p><strong>{_safe(scenario['display_name'])}</strong> is a fixed synthetic scenario "
        f"for {_safe(scenario['country_name'])}. The supplied Product Decision is "
        f"<strong>{_safe(str(scenario['product_decision']).title())}</strong>. "
        f"Modeled exposure at 34 kt is {_safe(_integer(threat['expected_population']))} people, "
        "not observed impact.</p>"
    )


def _email_content(scenario: dict[str, Any], alternative: str) -> str:
    summary = _common_summary(scenario)
    facts = _facts_table(scenario, "Synthetic decision-support facts")
    status = f'<p class="status-line">{_safe(_official_status(scenario))}</p>'
    evolution = _evolution_table(scenario)
    caveats = (
        "<section><h2>Interpretation boundaries</h2><ul>"
        "<li>Modeled exposure - not observed impact.</li>"
        "<li>Forecast-conditioned PiN/CHiN - not observed need.</li>"
        "<li>Rainfall unavailable; storm surge unavailable.</li>"
        "<li>Prototype wording - not approved action guidance.</li>"
        "</ul></section>"
    )
    if alternative == "combined-long":
        return (
            "<section><h2>Situation</h2>"
            f"{status}{summary}</section><section><h2>Expected impacts</h2>{facts}</section>"
            f"<section><h2>Forecast evolution</h2>{evolution}</section>{caveats}"
        )
    if alternative == "concise-email":
        return f"<section><h2>Decision summary</h2>{status}{summary}{facts}</section>{caveats}"
    if alternative == "concise-linked-report":
        report_name = f"{scenario['scenario_id']}--technical-report.html"
        return (
            f"<section><h2>Decision summary</h2>{status}{summary}{facts}"
            f'<p><a class="report-link" href="../reports/{_safe(report_name)}">'
            "Open the optional synthetic technical report</a>. The email remains "
            "self-contained if the link is unavailable.</p></section>"
            f"{caveats}"
        )
    if alternative == "expanded-email":
        return (
            f"<section><h2>Executive interpretation</h2>{status}{summary}</section>"
            f"<section><h2>Evidence detail</h2>{facts}</section>"
            f"<section><h2>Forecast evolution</h2>{evolution}</section>{caveats}"
        )
    raise ConsultationInputError(f"unsupported consultation alternative: {alternative}")


def _report_content(scenario: dict[str, Any]) -> str:
    return (
        f"<section><h2>Executive summary</h2>{_common_summary(scenario)}"
        f'<p class="status-line">{_safe(_official_status(scenario))}</p></section>'
        f"<section><h2>Expected impacts</h2>{_facts_table(scenario, 'Synthetic expected-impact facts')}</section>"
        "<section><h2>Scenario interpretation</h2><p>This is one fixed synthetic "
        "forecast-conditioned evidence state, not a prediction range or observed event.</p></section>"
        f"<section><h2>Forecast evolution</h2>{_evolution_table(scenario)}</section>"
        "<section><h2>Provenance and caveats</h2><ul>"
        f"<li>{_safe(scenario['provenance']['label'])}; as of {_safe(scenario['provenance']['as_of'])}.</li>"
        "<li>Modeled exposure - not observed impact.</li>"
        "<li>Forecast-conditioned PiN/CHiN - not observed need.</li>"
        "<li>Rainfall unavailable; storm surge unavailable.</li>"
        "<li>Prototype wording - not approved action guidance.</li>"
        "</ul></section>"
    )


def _render_document(
    document_template: Template,
    content_template: Template,
    scenario: dict[str, Any],
    title: str,
    format_label: str,
    content: str,
) -> str:
    body = content_template.substitute(content=content)
    return document_template.substitute(
        title=_safe(title),
        format_label=_safe(format_label),
        scenario_label=_safe(scenario["display_name"]),
        product_decision=_safe(str(scenario["product_decision"]).title()),
        content=body,
        stylesheet_path="../prototype.css",
    )


def _write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, newline="\n")


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _generated_index(output_paths: list[str]) -> str:
    links = "\n".join(f"- [{path}]({path})" for path in sorted(output_paths))
    return (
        "---\n"
        'title: "Generated Alert Packaging Consultation Index"\n'
        "---\n\n"
        "CONSULTATION PROTOTYPE - NOT OPERATIONAL\n\n"
        "Generated from synthetic public test data. These files are review evidence only.\n\n"
        f"{links}\n"
    )


def build_consultation_pack(
    scenario_dir: Path,
    template_dir: Path,
    stylesheet_path: Path,
    output_dir: Path,
) -> dict[str, Any]:
    scenarios = _load_scenarios(Path(scenario_dir))
    document_template = _read_template(Path(template_dir), "document.html")
    email_template = _read_template(Path(template_dir), "email.html")
    report_template = _read_template(Path(template_dir), "technical-report.html")

    output_dir = Path(output_dir)
    if output_dir.exists():
        shutil.rmtree(output_dir)
    output_dir.mkdir(parents=True)
    shutil.copyfile(stylesheet_path, output_dir / "prototype.css")
    written = ["prototype.css"]

    for scenario in scenarios:
        alternatives = (
            ALTERNATIVES
            if scenario["scenario_id"] != "forecast-only-warning"
            else (RECOMMENDED_ALTERNATIVE,)
        )
        for alternative in alternatives:
            relative_path = f"emails/{scenario['scenario_id']}--{alternative}.html"
            title = (
                f"{scenario['product_decision'].title()} - {alternative.replace('-', ' ').title()}"
            )
            rendered = _render_document(
                document_template,
                email_template,
                scenario,
                title,
                alternative.replace("-", " ").title(),
                _email_content(scenario, alternative),
            )
            _write(output_dir / relative_path, rendered)
            written.append(relative_path)

        report_path = f"reports/{scenario['scenario_id']}--technical-report.html"
        rendered_report = _render_document(
            document_template,
            report_template,
            scenario,
            f"{scenario['product_decision'].title()} - Technical Report",
            "Optional Technical Report",
            _report_content(scenario),
        )
        _write(output_dir / report_path, rendered_report)
        written.append(report_path)

    scenario_index_path = output_dir / "scenario-index.json"
    scenario_index_path.write_text(
        json.dumps(scenarios, indent=2, sort_keys=True) + "\n",
        newline="\n",
    )
    written.append("scenario-index.json")

    index_path = output_dir / "consultation-index.qmd"
    _write(index_path, _generated_index(written))
    written.append("consultation-index.qmd")

    outputs = [{"path": path, "sha256": _sha256(output_dir / path)} for path in sorted(written)]
    manifest: dict[str, Any] = {
        "schema_version": "alert-packaging-consultation-build-v1",
        "classification": "synthetic_public",
        "outputs": outputs,
    }
    (output_dir / "manifest.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n",
        newline="\n",
    )
    return manifest


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Build the synthetic consultation prototype pack")
    parser.add_argument("--scenario-dir", required=True, type=Path)
    parser.add_argument("--template-dir", required=True, type=Path)
    parser.add_argument("--stylesheet", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    return parser


def main() -> int:
    args = _parser().parse_args()
    build_consultation_pack(
        scenario_dir=args.scenario_dir,
        template_dir=args.template_dir,
        stylesheet_path=args.stylesheet,
        output_dir=args.output_dir,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

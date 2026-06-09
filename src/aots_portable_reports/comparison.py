from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from aots_portable_reports.models import ComparisonIssue, ComparisonReport, ExpectedReportProvenance

RAW_PROBABILITY_TOLERANCE = 1e-9
RENDERED_PERCENTAGE_TOLERANCE = 0.01
ADMIN_ROW_KEYS = {
    "rows_admins_pop_total",
    "rows_admins_school",
    "rows_admins_infant",
    "rows_admins_adolescent",
    "rows_schools_winds",
    "rows_hcs_winds",
    "rows_shelters_winds",
    "rows_wash_winds",
}


def compare_report_payloads(
    expected: Any,
    actual: Any,
    *,
    expected_report_provenance: ExpectedReportProvenance = "unknown",
) -> ComparisonReport:
    failures: list[ComparisonIssue] = []
    warnings: list[ComparisonIssue] = []
    expected = _normalize_contract_value(expected, path="$")
    actual = _normalize_contract_value(actual, path="$")
    _compare_value(expected, actual, path="$", failures=failures, warnings=warnings)
    if failures:
        return ComparisonReport(
            status="failed",
            certification_state="reproduction_ready",
            certifying=False,
            failures=failures,
            warnings=warnings,
        )
    certifying = expected_report_provenance == "independent_current_output"
    return ComparisonReport(
        status="passed",
        certification_state="certifying_comparison" if certifying else "provisional_comparison",
        certifying=certifying,
        failures=failures,
        warnings=warnings,
    )


def _compare_value(
    expected: Any,
    actual: Any,
    *,
    path: str,
    failures: list[ComparisonIssue],
    warnings: list[ComparisonIssue],
) -> None:
    if isinstance(expected, Mapping) and isinstance(actual, Mapping):
        _compare_mapping(expected, actual, path=path, failures=failures, warnings=warnings)
        return
    if _is_sequence(expected) and _is_sequence(actual):
        _compare_sequence(expected, actual, path=path, failures=failures, warnings=warnings)
        return
    if _is_number(expected) and _is_number(actual):
        _compare_number(expected, actual, path=path, failures=failures)
        return
    if expected != actual:
        failures.append(
            ComparisonIssue(
                severity="failure",
                code="value_mismatch",
                message=f"{path}: expected {expected!r}, got {actual!r}",
            )
        )


def _compare_mapping(
    expected: Mapping[str, Any],
    actual: Mapping[str, Any],
    *,
    path: str,
    failures: list[ComparisonIssue],
    warnings: list[ComparisonIssue],
) -> None:
    expected_keys = set(expected)
    actual_keys = set(actual)
    for key in sorted(expected_keys - actual_keys):
        failures.append(
            ComparisonIssue(severity="failure", code="missing_field", message=f"{path}.{key}: missing field")
        )
    for key in sorted(actual_keys - expected_keys):
        failures.append(
            ComparisonIssue(severity="failure", code="extra_field", message=f"{path}.{key}: extra field")
        )
    for key in sorted(expected_keys & actual_keys):
        child_path = f"{path}.{key}"
        if _is_top_facility_descriptor_tie(key, expected, actual):
            warnings.append(
                ComparisonIssue(
                    severity="warning",
                    code="top_facility_tie_order",
                    message=f"{child_path}: descriptor differs but probability tie makes slot order unstable",
                )
            )
            continue
        _compare_value(expected[key], actual[key], path=child_path, failures=failures, warnings=warnings)


def _compare_sequence(
    expected: Sequence[Any],
    actual: Sequence[Any],
    *,
    path: str,
    failures: list[ComparisonIssue],
    warnings: list[ComparisonIssue],
) -> None:
    if len(expected) != len(actual):
        failures.append(
            ComparisonIssue(
                severity="failure",
                code="value_mismatch",
                message=f"{path}: expected {len(expected)} items, got {len(actual)}",
            )
        )
        return
    for index, (expected_item, actual_item) in enumerate(zip(expected, actual)):
        _compare_value(expected_item, actual_item, path=f"{path}[{index}]", failures=failures, warnings=warnings)


def _compare_number(expected: int | float, actual: int | float, *, path: str, failures: list[ComparisonIssue]) -> None:
    if isinstance(expected, int) and isinstance(actual, int):
        if expected != actual:
            failures.append(
                ComparisonIssue(
                    severity="failure",
                    code="value_mismatch",
                    message=f"{path}: expected {expected!r}, got {actual!r}",
                )
            )
        return
    tolerance = _tolerance_for_path(path)
    if abs(float(expected) - float(actual)) > tolerance:
        failures.append(
            ComparisonIssue(
                severity="failure",
                code="numeric_tolerance",
                message=f"{path}: expected {expected!r}, got {actual!r}, tolerance {tolerance}",
            )
        )


def _tolerance_for_path(path: str) -> float:
    lower_path = path.lower()
    if "percent" in lower_path or "percentage" in lower_path:
        return RENDERED_PERCENTAGE_TOLERANCE
    return RAW_PROBABILITY_TOLERANCE


def _is_number(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def _is_sequence(value: Any) -> bool:
    return isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray))


def _normalize_contract_value(value: Any, *, path: str) -> Any:
    if isinstance(value, Mapping):
        return {key: _normalize_contract_value(child, path=f"{path}.{key}") for key, child in value.items()}
    if _is_sequence(value):
        normalized_items = [_normalize_contract_value(child, path=f"{path}[]") for child in value]
        key = path.rsplit(".", maxsplit=1)[-1]
        if key in ADMIN_ROW_KEYS and _all_named_mappings(normalized_items):
            return sorted(normalized_items, key=lambda item: str(item["name"]))
        return normalized_items
    return value


def _all_named_mappings(value: list[Any]) -> bool:
    return bool(value) and all(isinstance(item, Mapping) and isinstance(item.get("name"), str) for item in value)


def _is_top_facility_descriptor_tie(key: str, expected: Mapping[str, Any], actual: Mapping[str, Any]) -> bool:
    parsed = _top_facility_descriptor_key(key)
    if parsed is None:
        return False
    prefix, index = parsed
    probability_key = f"{prefix}_prob_{index}"
    if probability_key not in expected or probability_key not in actual:
        return False
    if expected.get(key) == actual.get(key):
        return False
    expected_probability = expected.get(probability_key)
    actual_probability = actual.get(probability_key)
    if not (_is_number(expected_probability) and _is_number(actual_probability)):
        return False
    return abs(float(expected_probability) - float(actual_probability)) <= RAW_PROBABILITY_TOLERANCE


def _top_facility_descriptor_key(key: str) -> tuple[str, str] | None:
    parts = key.rsplit("_", maxsplit=1)
    if len(parts) != 2 or not parts[1].isdigit():
        return None
    stem, index = parts
    for suffix in ["_name", "_type", "_edulevel"]:
        if stem.endswith(suffix):
            return stem.removesuffix(suffix), index
    return None

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from aots_portable_reports.models import ComparisonIssue, ComparisonReport

RAW_PROBABILITY_TOLERANCE = 1e-9
RENDERED_PERCENTAGE_TOLERANCE = 0.01


def compare_report_payloads(expected: Any, actual: Any) -> ComparisonReport:
    failures: list[ComparisonIssue] = []
    _compare_value(expected, actual, path="$", failures=failures)
    return ComparisonReport(status="failed" if failures else "passed", failures=failures)


def _compare_value(expected: Any, actual: Any, *, path: str, failures: list[ComparisonIssue]) -> None:
    if isinstance(expected, Mapping) and isinstance(actual, Mapping):
        _compare_mapping(expected, actual, path=path, failures=failures)
        return
    if _is_sequence(expected) and _is_sequence(actual):
        _compare_sequence(expected, actual, path=path, failures=failures)
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
    expected: Mapping[str, Any], actual: Mapping[str, Any], *, path: str, failures: list[ComparisonIssue]
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
        _compare_value(expected[key], actual[key], path=f"{path}.{key}", failures=failures)


def _compare_sequence(
    expected: Sequence[Any], actual: Sequence[Any], *, path: str, failures: list[ComparisonIssue]
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
        _compare_value(expected_item, actual_item, path=f"{path}[{index}]", failures=failures)


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

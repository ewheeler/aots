from __future__ import annotations

from aots_portable_reports.comparison import compare_report_payloads


def test_comparison_passes_within_probability_and_percentage_tolerances() -> None:
    expected = {
        "admin_areas_at_risk": 1,
        "risk_category": "moderate",
        "maximum_probability": 0.25,
        "maximum_percentage": 25.0,
    }
    actual = {
        "admin_areas_at_risk": 1,
        "risk_category": "moderate",
        "maximum_probability": 0.2500000001,
        "maximum_percentage": 25.005,
    }

    comparison = compare_report_payloads(expected, actual)

    assert comparison.status == "passed"
    assert comparison.failures == []


def test_comparison_fails_on_integer_and_categorical_mismatch() -> None:
    comparison = compare_report_payloads(
        {"count": 1, "category": "low"},
        {"count": 2, "category": "high"},
    )

    assert comparison.status == "failed"
    assert [issue.code for issue in comparison.failures] == ["value_mismatch", "value_mismatch"]


def test_comparison_fails_on_floats_outside_declared_tolerances() -> None:
    comparison = compare_report_payloads(
        {"maximum_probability": 0.25, "maximum_percentage": 25.0},
        {"maximum_probability": 0.25001, "maximum_percentage": 25.02},
    )

    assert comparison.status == "failed"
    assert [issue.code for issue in comparison.failures] == ["numeric_tolerance", "numeric_tolerance"]


def test_comparison_fails_on_missing_and_extra_contract_fields() -> None:
    comparison = compare_report_payloads(
        {"required": 1},
        {"extra": 1},
    )

    assert comparison.status == "failed"
    assert [issue.code for issue in comparison.failures] == ["missing_field", "extra_field"]

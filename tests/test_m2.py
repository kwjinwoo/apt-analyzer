import json
import subprocess
from datetime import date
from decimal import Decimal

import pytest

from apt_analyzer.analytics import (
    HouseholdEvidence,
    analyze,
    build_population,
    discover_area_groups,
    maximum_drawdown,
    monthly_median_prices,
    retention,
    turnover,
    yearly_price_summaries,
)
from apt_analyzer.cli import analyze_input, result_to_dict, result_to_text
from apt_analyzer.domain import (
    AnalysisContext,
    AnalysisPeriod,
    Apartment,
    AreaGroup,
    AreaSelection,
    NormalizedTransaction,
    TransactionInclusionPolicy,
    TransactionType,
)


def test_discover_area_groups_preserves_raw_areas_with_integer_floor() -> None:
    transactions = [
        NormalizedTransaction(
            "apt-1", date(2025, 1, 1), 1, Decimal("84.81"), TransactionType.BROKERED, False
        ),
        NormalizedTransaction(
            "apt-1", date(2025, 1, 2), 1, Decimal("84.97"), TransactionType.BROKERED, False
        ),
        NormalizedTransaction(
            "apt-1", date(2025, 1, 3), 1, Decimal("59.99"), TransactionType.BROKERED, False
        ),
    ]
    groups = discover_area_groups(transactions)

    assert [(group.key, group.raw_areas_sqm) for group in groups] == [
        ("floor-59", frozenset({Decimal("59.99")})),
        ("floor-84", frozenset({Decimal("84.81"), Decimal("84.97")})),
    ]


def test_discover_area_groups_represents_absent_area_evidence_as_empty() -> None:
    assert discover_area_groups([]) == ()


def _context(period: AnalysisPeriod) -> AnalysisContext:
    return AnalysisContext(
        Apartment("apt-1", "Example"),
        period,
        AreaSelection.all(),
        TransactionInclusionPolicy(False, frozenset({TransactionType.BROKERED})),
    )


def test_yearly_and_monthly_results_keep_empty_years_and_observation_counts() -> None:
    context = _context(AnalysisPeriod(date(2024, 1, 1), date(2025, 12, 31)))
    transactions = [
        NormalizedTransaction(
            "apt-1", date(2025, 1, 1), 100, Decimal("84"), TransactionType.BROKERED, False
        ),
        NormalizedTransaction(
            "apt-1", date(2025, 3, 1), 80, Decimal("84"), TransactionType.BROKERED, False
        ),
    ]
    population = build_population(transactions, context)

    yearly = yearly_price_summaries(population)
    assert yearly[0].count == 0 and yearly[0].median_krw is None
    assert (
        yearly[1].count == 2
        and yearly[1].mean_krw == Decimal("90")
        and yearly[1].median_krw == Decimal("90")
    )
    assert yearly[1].maximum_krw == 100 and yearly[1].minimum_krw == 80
    assert monthly_median_prices(population)[0].transaction_count == 1


def test_turnover_and_retention_make_unsupported_and_zero_baseline_explicit() -> None:
    context = _context(AnalysisPeriod(date(2024, 1, 1), date(2025, 12, 31)))
    population = build_population([], context)
    partial = turnover(
        population,
        AnalysisPeriod(date(2025, 2, 1), date(2025, 12, 31)),
        HouseholdEvidence(100, "complex"),
    )
    zero = retention(
        population,
        AnalysisPeriod(date(2024, 1, 1), date(2024, 12, 31)),
        AnalysisPeriod(date(2025, 1, 1), date(2025, 12, 31)),
    )
    assert partial.value is None and partial.unavailable is not None
    assert zero.value is None and zero.unavailable is not None


def test_mdd_reports_peak_trough_and_sparse_unavailable_state() -> None:
    context = _context(AnalysisPeriod(date(2025, 1, 1), date(2025, 12, 31)))
    transactions = [
        NormalizedTransaction(
            "apt-1", date(2025, 1, 1), 100, Decimal("84"), TransactionType.BROKERED, False
        ),
        NormalizedTransaction(
            "apt-1", date(2025, 3, 1), 80, Decimal("84"), TransactionType.BROKERED, False
        ),
    ]
    result = maximum_drawdown(build_population(transactions, context))
    assert result.value == Decimal("-0.2")
    assert result.peak is not None and result.peak.month == "2025-01"
    assert result.trough is not None and result.trough.month == "2025-03"
    sparse = maximum_drawdown(build_population(transactions[:1], context))
    assert sparse.value is None and sparse.unavailable is not None


def test_retention_annualizes_differing_complete_period_lengths() -> None:
    context = _context(AnalysisPeriod(date(2023, 1, 1), date(2025, 12, 31)))
    transactions = [
        NormalizedTransaction(
            "apt-1", date(2023, 1, 1), 100, Decimal("84"), TransactionType.BROKERED, False
        ),
        NormalizedTransaction(
            "apt-1", date(2023, 2, 1), 100, Decimal("84"), TransactionType.BROKERED, False
        ),
        NormalizedTransaction(
            "apt-1", date(2025, 1, 1), 100, Decimal("84"), TransactionType.BROKERED, False
        ),
    ]
    result = retention(
        build_population(transactions, context),
        AnalysisPeriod(date(2023, 1, 1), date(2023, 12, 31)),
        AnalysisPeriod(date(2024, 1, 1), date(2025, 12, 31)),
    )
    assert result.value == Decimal("0.25")
    assert result.context == context


def test_mdd_non_declining_series_reports_zero_with_same_observation_peak_trough() -> None:
    context = _context(AnalysisPeriod(date(2025, 1, 1), date(2025, 12, 31)))
    transactions = [
        NormalizedTransaction(
            "apt-1", date(2025, 1, 1), 100, Decimal("84"), TransactionType.BROKERED, False
        ),
        NormalizedTransaction(
            "apt-1", date(2025, 3, 1), 120, Decimal("84"), TransactionType.BROKERED, False
        ),
    ]
    result = maximum_drawdown(build_population(transactions, context))
    assert result.value == Decimal("0") and result.peak == result.trough
    assert result.price_series_method == "observed monthly median"
    assert result.missing_month_method == "observed months only; no interpolation"


def test_successful_annual_and_multiyear_turnover_expose_context_and_evidence() -> None:
    context = _context(AnalysisPeriod(date(2024, 1, 1), date(2025, 12, 31)))
    transactions = [
        NormalizedTransaction(
            "apt-1", date(2024, 1, 1), 100, Decimal("84"), TransactionType.BROKERED, False
        ),
        NormalizedTransaction(
            "apt-1", date(2024, 1, 2), 101, Decimal("84"), TransactionType.BROKERED, False
        ),
        NormalizedTransaction(
            "apt-1", date(2025, 1, 1), 102, Decimal("84"), TransactionType.BROKERED, False
        ),
    ]
    result = analyze(
        transactions,
        context,
        turnover_period=context.period,
        household=HouseholdEvidence(100, "complex", "fixture"),
    )
    assert result.turnover is not None and result.turnover.value == Decimal("0.015")
    assert result.turnover.context == context
    assert result.turnover.annualization_method == "complete-calendar-year-average"
    assert len(result.annual_turnover) == 2
    assert result.annual_turnover[0].value == Decimal("0.02")
    assert result.annual_turnover[1].value == Decimal("0.01")


def test_metric_period_outside_context_is_unavailable_and_household_source_required() -> None:
    context = _context(AnalysisPeriod(date(2025, 1, 1), date(2025, 12, 31)))
    population = build_population([], context)
    outside = turnover(
        population,
        AnalysisPeriod(date(2024, 1, 1), date(2024, 12, 31)),
        HouseholdEvidence(100, "complex", "fixture"),
    )
    missing_source = turnover(population, context.period, HouseholdEvidence(100, "complex", ""))
    assert outside.unavailable is not None and "outside" in outside.unavailable.reason
    assert missing_source.unavailable is not None and "source" in missing_source.unavailable.reason
    baseline_outside = retention(
        population, AnalysisPeriod(date(2024, 1, 1), date(2024, 12, 31)), context.period
    )
    comparison_outside = retention(
        population, context.period, AnalysisPeriod(date(2026, 1, 1), date(2026, 12, 31))
    )
    assert baseline_outside.unavailable is not None
    assert comparison_outside.unavailable is not None


def test_area_group_turnover_rejects_whole_complex_denominator_scope() -> None:
    context = AnalysisContext(
        Apartment("apt-1", "Example"),
        AnalysisPeriod(date(2025, 1, 1), date(2025, 12, 31)),
        AreaSelection.for_group(AreaGroup("floor-84", "84㎡", frozenset({Decimal("84")}))),
        TransactionInclusionPolicy(False, frozenset({TransactionType.BROKERED})),
    )
    result = turnover(
        build_population([], context), context.period, HouseholdEvidence(100, "complex", "fixture")
    )
    assert (
        result.value is None
        and result.unavailable is not None
        and "scope" in result.unavailable.reason
    )


def test_non_volume_metrics_use_same_area_type_and_cancellation_population() -> None:
    context = AnalysisContext(
        Apartment("apt-1", "Example"),
        AnalysisPeriod(date(2025, 1, 1), date(2025, 12, 31)),
        AreaSelection.for_group(AreaGroup("floor-84", "84㎡", frozenset({Decimal("84")}))),
        TransactionInclusionPolicy(False, frozenset({TransactionType.BROKERED})),
    )
    transactions = [
        NormalizedTransaction(
            "apt-1", date(2025, 1, 1), 100, Decimal("84"), TransactionType.BROKERED, False
        ),
        NormalizedTransaction(
            "apt-1", date(2025, 2, 1), 90, Decimal("84"), TransactionType.BROKERED, True
        ),
        NormalizedTransaction(
            "apt-1", date(2025, 3, 1), 80, Decimal("59"), TransactionType.BROKERED, False
        ),
        NormalizedTransaction(
            "apt-1", date(2025, 4, 1), 70, Decimal("84"), TransactionType.DIRECT, False
        ),
    ]
    result = analyze(transactions, context)
    assert len(result.population.eligible) == 1
    assert result.yearly_summaries[0].count == 1
    assert result.monthly_prices[0].month == "2025-01"
    assert result.mdd.unavailable is not None


def test_mdd_subperiod_is_effective_context_and_serializable() -> None:
    context = _context(AnalysisPeriod(date(2024, 1, 1), date(2025, 12, 31)))
    transactions = [
        NormalizedTransaction(
            "apt-1", date(2024, 1, 1), 100, Decimal("84"), TransactionType.BROKERED, False
        ),
        NormalizedTransaction(
            "apt-1", date(2025, 3, 1), 80, Decimal("84"), TransactionType.BROKERED, False
        ),
    ]
    result = analyze(transactions, context)
    subperiod = AnalysisPeriod(date(2025, 1, 1), date(2025, 12, 31))
    mdd = maximum_drawdown(result.population, subperiod)
    assert mdd.period == subperiod
    sub_result = analyze(transactions, _context(subperiod))
    assert result_to_dict(sub_result)["mdd"]["period"] == {
        "start": "2025-01-01",
        "end": "2025-12-31",
    }


def test_cli_rejects_unknown_data_coverage_and_preserves_valid_empty_status() -> None:
    payload = {
        "data_status": "unknown",
        "apartment": {"internal_id": "apt-1", "display_name": "Example"},
        "period": {"start": "2025-01-01", "end": "2025-12-31"},
        "inclusion_policy": {"include_cancelled": False, "transaction_types": ["brokered"]},
        "transactions": [],
    }
    with pytest.raises(ValueError, match="data_status"):
        analyze_input(payload)
    payload["data_status"] = "valid_empty"
    result = analyze_input(payload)
    assert result.data_status == "valid_empty"
    assert result.yearly_summaries[0].count == 0


def test_grouping_policy_is_replaceable() -> None:
    class OneGroupPolicy:
        name = "one-group"

        def group(self, areas: list[Decimal]) -> tuple[AreaGroup, ...]:
            return (AreaGroup("all", "all", frozenset(areas)),) if areas else ()

    transactions = [
        NormalizedTransaction(
            "apt-1", date(2025, 1, 1), 1, Decimal("84.81"), TransactionType.BROKERED, False
        ),
        NormalizedTransaction(
            "apt-1", date(2025, 1, 2), 1, Decimal("59.99"), TransactionType.BROKERED, False
        ),
    ]
    groups = discover_area_groups(transactions, OneGroupPolicy())
    assert groups[0].key == "all" and groups[0].raw_areas_sqm == frozenset(
        {Decimal("84.81"), Decimal("59.99")}
    )


def test_real_console_entrypoint_outputs_configured_json_and_text() -> None:
    command = ["uv", "run", "--locked", "apt-analyzer", "analyze", "tests/fixtures/m2_input.json"]
    text_result = subprocess.run(command, check=True, capture_output=True, text=True)
    json_result = subprocess.run(
        command + ["--format", "json"], check=True, capture_output=True, text=True
    )
    data = json.loads(json_result.stdout)
    assert data["data_status"] == "complete"
    assert data["turnover"]["annualization_method"] == "complete-calendar-year-average"
    assert data["retention"]["annualization_method"] == "complete-calendar-year-average"
    assert data["retention"]["value"] == "1"
    assert (
        "annualization_method" in text_result.stdout
        and "available_area_groups" in text_result.stdout
    )


def test_integrated_result_exposes_areas_and_text_json_are_context_equivalent() -> None:
    payload = {
        "data_status": "complete",
        "apartment": {"internal_id": "apt-1", "display_name": "Example"},
        "period": {"start": "2025-01-01", "end": "2025-12-31"},
        "area_selection": {"kind": "group", "key": "floor-84"},
        "inclusion_policy": {"include_cancelled": False, "transaction_types": ["brokered"]},
        "household": {"count": 100, "scope": "complex", "source": "fixture"},
        "turnover_period": {"start": "2025-01-01", "end": "2025-12-31"},
        "transactions": [
            {
                "apartment_id": "apt-1",
                "contract_date": "2025-01-01",
                "price_krw": 100,
                "exclusive_area_sqm": "84.81",
                "transaction_type": "brokered",
                "is_cancelled": False,
            }
        ],
    }
    result = analyze_input(payload)
    data = result_to_dict(result)
    text = result_to_text(result)
    assert data["available_area_groups"][0]["raw_areas_sqm"] == ["84.81"]
    assert "available_area_groups" in text and "inclusion_policy" in text
    assert "price_series_method" in text and "turnover" in text


def test_cli_group_selection_requires_discovered_key_and_rejects_absent_evidence() -> None:
    base = {
        "data_status": "complete",
        "apartment": {"internal_id": "apt-1", "display_name": "Example"},
        "period": {"start": "2025-01-01", "end": "2025-12-31"},
        "inclusion_policy": {"include_cancelled": False, "transaction_types": ["brokered"]},
        "transactions": [
            {
                "apartment_id": "apt-1",
                "contract_date": "2025-01-01",
                "price_krw": 100,
                "exclusive_area_sqm": "84.81",
                "transaction_type": "brokered",
                "is_cancelled": False,
            }
        ],
    }
    base["area_selection"] = {"kind": "group", "key": "floor-84"}
    assert analyze_input(base).population.context.area_selection.group is not None
    base["area_selection"] = {"kind": "group", "key": "floor-59"}
    with pytest.raises(ValueError, match="area group key"):
        analyze_input(base)

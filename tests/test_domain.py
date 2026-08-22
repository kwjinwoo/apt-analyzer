from datetime import date
from decimal import Decimal

import pytest

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


def test_analysis_period_rejects_reversed_boundaries() -> None:
    with pytest.raises(ValueError, match="start date must not be after end date"):
        AnalysisPeriod(start=date(2025, 1, 2), end=date(2025, 1, 1))


def test_domain_values_represent_source_independent_analysis_context() -> None:
    apartment = Apartment(internal_id="apt-001", display_name="Example Apartments")
    area_group = AreaGroup(
        key="area-84",
        label="84 m2",
        raw_areas_sqm=frozenset({Decimal("84.81"), Decimal("84.92")}),
    )
    context = AnalysisContext(
        apartment=apartment,
        period=AnalysisPeriod(start=date(2025, 1, 1), end=date(2025, 12, 31)),
        area_selection=AreaSelection.for_group(area_group),
        inclusion_policy=TransactionInclusionPolicy(
            include_cancelled=False,
            included_transaction_types=frozenset(
                {TransactionType.BROKERED, TransactionType.DIRECT}
            ),
        ),
    )
    transaction = NormalizedTransaction(
        apartment_id=apartment.internal_id,
        contract_date=date(2025, 6, 1),
        price_krw=900_000_000,
        exclusive_area_sqm=Decimal("84.92"),
        transaction_type=TransactionType.BROKERED,
        is_cancelled=False,
    )

    assert context.area_selection.includes(transaction.exclusive_area_sqm)
    assert context.period.includes(transaction.contract_date)
    assert transaction.exclusive_area_sqm == Decimal("84.92")


def test_all_area_selection_includes_any_raw_area() -> None:
    selection = AreaSelection.all()

    assert selection.includes(Decimal("59.99"))
    assert selection.includes(Decimal("114.72"))

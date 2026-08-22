from datetime import date
from decimal import Decimal

from apt_analyzer.analytics import TransactionVolumeResult, transaction_volume
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


def _transaction(
    *,
    apartment_id: str = "apt-001",
    contract_date: date = date(2025, 6, 1),
    area: str = "84.92",
    transaction_type: TransactionType = TransactionType.BROKERED,
    is_cancelled: bool = False,
) -> NormalizedTransaction:
    return NormalizedTransaction(
        apartment_id=apartment_id,
        contract_date=contract_date,
        price_krw=900_000_000,
        exclusive_area_sqm=Decimal(area),
        transaction_type=transaction_type,
        is_cancelled=is_cancelled,
    )


def test_transaction_volume_uses_explicit_population_without_external_api() -> None:
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
            included_transaction_types=frozenset({TransactionType.BROKERED}),
        ),
    )
    transactions = [
        _transaction(),
        _transaction(area="59.99"),
        _transaction(contract_date=date(2024, 12, 31)),
        _transaction(is_cancelled=True),
        _transaction(transaction_type=TransactionType.DIRECT),
        _transaction(apartment_id="apt-002"),
    ]

    result = transaction_volume(transactions, context)

    assert result == TransactionVolumeResult(raw_count=6, eligible_count=1, context=context)


def test_transaction_volume_distinguishes_valid_empty_population() -> None:
    context = AnalysisContext(
        apartment=Apartment(internal_id="apt-001", display_name="Example Apartments"),
        period=AnalysisPeriod(start=date(2025, 1, 1), end=date(2025, 12, 31)),
        area_selection=AreaSelection.all(),
        inclusion_policy=TransactionInclusionPolicy(
            include_cancelled=False,
            included_transaction_types=frozenset({TransactionType.BROKERED}),
        ),
    )

    assert transaction_volume([], context) == TransactionVolumeResult(
        raw_count=0,
        eligible_count=0,
        context=context,
    )

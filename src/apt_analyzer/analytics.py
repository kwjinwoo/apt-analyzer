"""Pure analytics over normalized apartment transaction domain values."""

from collections.abc import Iterable
from dataclasses import dataclass

from apt_analyzer.domain import AnalysisContext, NormalizedTransaction


@dataclass(frozen=True, slots=True)
class TransactionVolumeResult:
    """Report raw and eligible counts together with their analysis context."""

    raw_count: int
    eligible_count: int
    context: AnalysisContext


def transaction_volume(
    transactions: Iterable[NormalizedTransaction],
    context: AnalysisContext,
) -> TransactionVolumeResult:
    """Count transactions eligible under an explicit analysis context.

    Args:
        transactions: Normalized records already acquired from any source.
        context: Apartment, inclusive period, area selection, and inclusion policy.

    Returns:
        Raw input count and eligible transaction volume with the exact context.

    Notes:
        This function performs no acquisition, network access, or source parsing.
        An empty iterable is a valid population and returns zero counts.
    """
    raw_count = 0
    eligible_count = 0

    for transaction in transactions:
        raw_count += 1
        if _is_eligible(transaction, context):
            eligible_count += 1

    return TransactionVolumeResult(
        raw_count=raw_count,
        eligible_count=eligible_count,
        context=context,
    )


def _is_eligible(transaction: NormalizedTransaction, context: AnalysisContext) -> bool:
    """Return whether a transaction belongs to an analysis population."""
    return (
        transaction.apartment_id == context.apartment.internal_id
        and context.period.includes(transaction.contract_date)
        and context.area_selection.includes(transaction.exclusive_area_sqm)
        and context.inclusion_policy.includes(transaction)
    )

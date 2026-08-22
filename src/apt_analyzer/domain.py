"""Source-independent values used to define apartment transaction analyses."""

from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from enum import StrEnum


@dataclass(frozen=True, slots=True)
class Apartment:
    """Identify one apartment complex independently of external source schemas.

    Attributes:
        internal_id: Stable project-owned identifier for the complex.
        display_name: Human-readable complex name that is not used as identity.
    """

    internal_id: str
    display_name: str

    def __post_init__(self) -> None:
        """Reject values that cannot identify or display an apartment."""
        if not self.internal_id.strip():
            raise ValueError("internal apartment ID must not be empty")
        if not self.display_name.strip():
            raise ValueError("apartment display name must not be empty")


@dataclass(frozen=True, slots=True)
class AnalysisPeriod:
    """Represent an inclusive calendar-date interval for transaction analysis."""

    start: date
    end: date

    def __post_init__(self) -> None:
        """Reject a reversed interval instead of silently correcting it."""
        if self.start > self.end:
            raise ValueError("start date must not be after end date")

    def includes(self, value: date) -> bool:
        """Return whether a date is within the inclusive interval."""
        return self.start <= value <= self.end


@dataclass(frozen=True, slots=True)
class AreaGroup:
    """Represent an already-classified market-facing exclusive-area group.

    The value preserves the exact normalized areas assigned by a replaceable
    grouping policy. It does not itself decide how areas should be grouped.
    """

    key: str
    label: str
    raw_areas_sqm: frozenset[Decimal]

    def __post_init__(self) -> None:
        """Reject incomplete groups and non-positive exclusive areas."""
        if not self.key.strip():
            raise ValueError("area-group key must not be empty")
        if not self.label.strip():
            raise ValueError("area-group label must not be empty")
        if not self.raw_areas_sqm:
            raise ValueError("area group must contain at least one raw area")
        if any(area <= 0 for area in self.raw_areas_sqm):
            raise ValueError("raw exclusive areas must be positive")


@dataclass(frozen=True, slots=True)
class AreaSelection:
    """Select either every exclusive area or one explicit area group."""

    group: AreaGroup | None

    @classmethod
    def all(cls) -> AreaSelection:
        """Create a selection that accepts all exclusive areas."""
        return cls(group=None)

    @classmethod
    def for_group(cls, group: AreaGroup) -> AreaSelection:
        """Create a selection restricted to an explicit area group."""
        return cls(group=group)

    def includes(self, raw_area_sqm: Decimal) -> bool:
        """Return whether a normalized raw exclusive area is selected."""
        return self.group is None or raw_area_sqm in self.group.raw_areas_sqm


class TransactionType(StrEnum):
    """Normalized evidence about how a transaction was conducted."""

    BROKERED = "brokered"
    DIRECT = "direct"
    UNKNOWN = "unknown"


@dataclass(frozen=True, slots=True)
class NormalizedTransaction:
    """Represent a sale transaction without a source-specific response object.

    Prices are integer Korean won and exclusive areas use decimal square metres
    so analytics do not lose source precision through binary floating point.
    """

    apartment_id: str
    contract_date: date
    price_krw: int
    exclusive_area_sqm: Decimal
    transaction_type: TransactionType
    is_cancelled: bool
    floor: int | None = None
    building: str | None = None
    unit: str | None = None
    construction_year: int | None = None
    broker_location: str | None = None
    source_name: str | None = None
    source_record_id: str | None = None
    source_values: tuple[tuple[str, str], ...] = ()

    def __post_init__(self) -> None:
        """Reject normalized records with invalid required domain values."""
        if not self.apartment_id.strip():
            raise ValueError("transaction apartment ID must not be empty")
        if self.price_krw <= 0:
            raise ValueError("transaction price must be positive")
        if self.exclusive_area_sqm <= 0:
            raise ValueError("exclusive area must be positive")


@dataclass(frozen=True, slots=True)
class TransactionInclusionPolicy:
    """Make cancellation and transaction-type eligibility explicit."""

    include_cancelled: bool
    included_transaction_types: frozenset[TransactionType]

    def includes(self, transaction: NormalizedTransaction) -> bool:
        """Return whether a normalized transaction satisfies this policy."""
        cancellation_allowed = self.include_cancelled or not transaction.is_cancelled
        return (
            cancellation_allowed and transaction.transaction_type in self.included_transaction_types
        )


@dataclass(frozen=True, slots=True)
class AnalysisContext:
    """Carry the subject and population conditions used by an analysis."""

    apartment: Apartment
    period: AnalysisPeriod
    area_selection: AreaSelection
    inclusion_policy: TransactionInclusionPolicy

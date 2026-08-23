"""Common-configuration apartment comparison application boundary."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass

from apt_analyzer.analytics import (
    AnalysisResult,
    DataCoverageStatus,
    HouseholdEvidence,
    analyze,
    discover_area_groups,
)
from apt_analyzer.domain import (
    AnalysisContext,
    AnalysisPeriod,
    Apartment,
    AreaGroup,
    AreaSelection,
    NormalizedTransaction,
    TransactionInclusionPolicy,
)


@dataclass(frozen=True, slots=True)
class CommonAnalysisConfig:
    """One immutable configuration shared by every comparison subject."""

    overall_period: AnalysisPeriod
    turnover_period: AnalysisPeriod
    baseline_period: AnalysisPeriod
    comparison_period: AnalysisPeriod
    mdd_period: AnalysisPeriod
    inclusion_policy: TransactionInclusionPolicy
    area_grouping_policy: str = "integer-floor-exclusive-area"
    area_group_key: str | None = None
    price_series_method: str = "observed monthly median"


@dataclass(frozen=True, slots=True)
class ComparisonSubject:
    """Expose one subject's result and subject-specific area evidence."""

    apartment: Apartment
    result: AnalysisResult | None
    available: bool
    unavailable_reason: str | None
    discovered_area_groups: tuple[AreaGroup, ...]
    effective_area_key: str | None


@dataclass(frozen=True, slots=True)
class ComparisonResult:
    """Comparison results carrying common configuration and subject evidence."""

    config: CommonAnalysisConfig
    subjects: tuple[ComparisonSubject, ...]


def compare(
    apartments: Sequence[Apartment],
    transactions: Mapping[str, Sequence[NormalizedTransaction]],
    config: CommonAnalysisConfig,
    households: Mapping[str, HouseholdEvidence] | None = None,
    *,
    data_status: str = DataCoverageStatus.COMPLETE,
) -> ComparisonResult:
    """Apply one configuration to every apartment, preserving missing group evidence."""
    if config.price_series_method != "observed monthly median":
        raise ValueError("unsupported price series method")
    if config.area_grouping_policy != "integer-floor-exclusive-area":
        raise ValueError("unsupported area grouping policy")
    if len(apartments) < 2 or len({apartment.internal_id for apartment in apartments}) != len(
        apartments
    ):
        raise ValueError("comparison requires at least two apartments with distinct internal IDs")
    subject_ids = {apartment.internal_id for apartment in apartments}
    if set(transactions) - subject_ids:
        raise ValueError("transactions mapping contains an unknown apartment subject")
    for apartment_id, records in transactions.items():
        if any(record.apartment_id != apartment_id for record in records):
            raise ValueError("transaction apartment ID does not match mapping subject")
    subjects: list[ComparisonSubject] = []
    for apartment in apartments:
        evidence = tuple(
            item
            for item in transactions.get(apartment.internal_id, ())
            if config.overall_period.includes(item.contract_date)
        )
        groups = discover_area_groups(evidence)
        selected = (
            None
            if config.area_group_key is None
            else next((group for group in groups if group.key == config.area_group_key), None)
        )
        if config.area_group_key is not None and selected is None:
            subjects.append(
                ComparisonSubject(
                    apartment,
                    None,
                    False,
                    "requested area group is absent from subject evidence",
                    groups,
                    config.area_group_key,
                )
            )
            continue
        context = AnalysisContext(
            apartment,
            config.overall_period,
            AreaSelection.all() if selected is None else AreaSelection.for_group(selected),
            config.inclusion_policy,
        )
        result = analyze(
            transactions.get(apartment.internal_id, ()),
            context,
            turnover_period=config.turnover_period,
            household=(households or {}).get(
                apartment.internal_id, HouseholdEvidence(None, "complex", None)
            ),
            baseline_period=config.baseline_period,
            comparison_period=config.comparison_period,
            mdd_period=config.mdd_period,
            data_status=data_status,
        )
        subjects.append(
            ComparisonSubject(
                apartment, result, True, None, groups, None if selected is None else selected.key
            )
        )
    return ComparisonResult(config, tuple(subjects))

"""Pure, deterministic analytics over normalized apartment transactions."""

from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from datetime import date
from decimal import ROUND_FLOOR, Decimal

from apt_analyzer.domain import AnalysisContext, AnalysisPeriod, AreaGroup, NormalizedTransaction

ANNUALIZATION_METHOD = "complete-calendar-year-average"
PRICE_SERIES_METHOD = "observed monthly median"
MISSING_MONTH_METHOD = "observed months only; no interpolation"


@dataclass(frozen=True, slots=True)
class TransactionPopulation:
    """The shared raw and eligible transaction population for an analysis."""

    raw: tuple[NormalizedTransaction, ...]
    eligible: tuple[NormalizedTransaction, ...]
    context: AnalysisContext


@dataclass(frozen=True, slots=True)
class TransactionVolumeResult:
    """Report raw and eligible counts together with their analysis context."""

    raw_count: int
    eligible_count: int
    context: AnalysisContext


@dataclass(frozen=True, slots=True)
class PriceSummary:
    """Exact price summary for one calendar year."""

    year: int
    count: int
    mean_krw: Decimal | None
    median_krw: Decimal | None
    maximum_krw: int | None
    minimum_krw: int | None


@dataclass(frozen=True, slots=True)
class MonthlyPriceObservation:
    """An observed monthly median and its transaction evidence count."""

    month: str
    median_krw: Decimal
    transaction_count: int


@dataclass(frozen=True, slots=True)
class MetricUnavailable:
    """Explicit unavailable metric state with a machine-readable reason."""

    status: str
    reason: str


@dataclass(frozen=True, slots=True)
class HouseholdEvidence:
    """Household denominator and its scope/source evidence."""

    count: int | None
    scope: str
    source: str | None = None


class DataCoverageStatus:
    """Explicit acquisition/coverage states carried by an offline analysis."""

    COMPLETE = "complete"
    VALID_EMPTY = "valid_empty"


@dataclass(frozen=True, slots=True)
class TurnoverResult:
    """Turnover value or unavailable state with denominator context."""

    value: Decimal | None
    annualized_count: Decimal | None
    eligible_count: int
    period: AnalysisPeriod
    household: HouseholdEvidence
    context: AnalysisContext
    annualization_method: str
    unavailable: MetricUnavailable | None = None


@dataclass(frozen=True, slots=True)
class RetentionResult:
    """Comparison-to-baseline annualized transaction retention."""

    value: Decimal | None
    baseline_count: int
    comparison_count: int
    baseline_annualized_count: Decimal | None
    comparison_annualized_count: Decimal | None
    baseline_period: AnalysisPeriod
    comparison_period: AnalysisPeriod
    context: AnalysisContext
    annualization_method: str
    unavailable: MetricUnavailable | None = None


@dataclass(frozen=True, slots=True)
class MddResult:
    """Observed monthly-median maximum drawdown and defining observations."""

    value: Decimal | None
    observations: tuple[MonthlyPriceObservation, ...]
    peak: MonthlyPriceObservation | None
    trough: MonthlyPriceObservation | None
    context: AnalysisContext
    period: AnalysisPeriod
    price_series_method: str
    missing_month_method: str
    unavailable: MetricUnavailable | None = None


@dataclass(frozen=True, slots=True)
class AnalysisResult:
    """One M2 result carrying shared population and all requested metrics."""

    population: TransactionPopulation
    yearly_summaries: tuple[PriceSummary, ...]
    monthly_prices: tuple[MonthlyPriceObservation, ...]
    turnover: TurnoverResult | None
    retention: RetentionResult | None
    mdd: MddResult
    annual_turnover: tuple[TurnoverResult, ...]
    available_area_groups: tuple[AreaGroup, ...]
    area_grouping_policy: str
    area_discovery_period: AnalysisPeriod
    data_status: str


class ExclusiveAreaGroupingPolicy:
    """Replaceable experimental policy grouping areas by integer floor."""

    name = "integer-floor-exclusive-area"

    def group(self, areas: Iterable[Decimal]) -> tuple[AreaGroup, ...]:
        """Return deterministic groups while retaining every raw Decimal area."""
        grouped: dict[int, set[Decimal]] = {}
        for area in areas:
            bucket = int(area.to_integral_value(rounding=ROUND_FLOOR))
            grouped.setdefault(bucket, set()).add(area)
        return tuple(
            AreaGroup(
                key=f"floor-{bucket}", label=f"{bucket}㎡", raw_areas_sqm=frozenset(grouped[bucket])
            )
            for bucket in sorted(grouped)
        )


def discover_area_groups(
    transactions: Iterable[NormalizedTransaction],
    policy: ExclusiveAreaGroupingPolicy | None = None,
) -> tuple[AreaGroup, ...]:
    """Discover area groups from observed raw transaction areas."""
    selected_policy = policy or ExclusiveAreaGroupingPolicy()
    return selected_policy.group(transaction.exclusive_area_sqm for transaction in transactions)


def build_population(
    transactions: Iterable[NormalizedTransaction], context: AnalysisContext
) -> TransactionPopulation:
    """Materialize one shared raw/eligible population for every metric."""
    raw = tuple(transactions)
    eligible = tuple(transaction for transaction in raw if _is_eligible(transaction, context))
    return TransactionPopulation(raw, eligible, context)


def transaction_volume(
    transactions: Iterable[NormalizedTransaction], context: AnalysisContext
) -> TransactionVolumeResult:
    """Count transactions eligible under an explicit analysis context."""
    population = build_population(transactions, context)
    return TransactionVolumeResult(len(population.raw), len(population.eligible), context)


def yearly_price_summaries(
    population: TransactionPopulation,
    period: AnalysisPeriod | None = None,
) -> tuple[PriceSummary, ...]:
    """Return summaries for every represented calendar year, including empty years."""
    selected = period or population.context.period
    values = _by_year(_within(population.eligible, selected))
    return tuple(
        PriceSummary(
            year,
            len(items),
            _mean(items),
            _median(items) if items else None,
            max((x.price_krw for x in items), default=None),
            min((x.price_krw for x in items), default=None),
        )
        for year in range(selected.start.year, selected.end.year + 1)
        for items in [values.get(year, ())]
    )


def monthly_median_prices(
    population: TransactionPopulation,
    period: AnalysisPeriod | None = None,
) -> tuple[MonthlyPriceObservation, ...]:
    """Return observed months only; gaps are never interpolated."""
    selected = period or population.context.period
    grouped: dict[str, list[NormalizedTransaction]] = {}
    for transaction in _within(population.eligible, selected):
        month = transaction.contract_date.strftime("%Y-%m")
        grouped.setdefault(month, []).append(transaction)
    return tuple(
        MonthlyPriceObservation(month, _median(items), len(items))
        for month, items in sorted(grouped.items())
    )


def turnover(
    population: TransactionPopulation, period: AnalysisPeriod, household: HouseholdEvidence
) -> TurnoverResult:
    """Calculate turnover only for complete calendar-year-aligned periods."""
    if not _contained_in_context(period, population.context.period):
        return TurnoverResult(
            None,
            None,
            0,
            period,
            household,
            population.context,
            ANNUALIZATION_METHOD,
            MetricUnavailable("unavailable", "metric period is outside overall analysis period"),
        )
    count = len(_within(population.eligible, period))
    if not _complete_calendar_period(period):
        return TurnoverResult(
            None,
            None,
            count,
            period,
            household,
            population.context,
            ANNUALIZATION_METHOD,
            MetricUnavailable("unavailable", "period is not complete calendar-year aligned"),
        )
    if household.count is None or household.count <= 0:
        return TurnoverResult(
            None,
            None,
            count,
            period,
            household,
            population.context,
            ANNUALIZATION_METHOD,
            MetricUnavailable("unavailable", "household denominator is missing or invalid"),
        )
    expected_scope = (
        "complex"
        if population.context.area_selection.group is None
        else population.context.area_selection.group.key
    )
    if not household.source or not household.source.strip():
        return TurnoverResult(
            None,
            None,
            count,
            period,
            household,
            population.context,
            ANNUALIZATION_METHOD,
            MetricUnavailable("unavailable", "household source evidence is missing"),
        )
    if household.scope != expected_scope:
        return TurnoverResult(
            None,
            None,
            count,
            period,
            household,
            population.context,
            ANNUALIZATION_METHOD,
            MetricUnavailable(
                "unavailable", "household denominator scope does not match area selection"
            ),
        )
    years = Decimal(period.end.year - period.start.year + 1)
    annualized = Decimal(count) / years
    return TurnoverResult(
        annualized / Decimal(household.count),
        annualized,
        count,
        period,
        household,
        population.context,
        ANNUALIZATION_METHOD,
    )


def retention(
    population: TransactionPopulation,
    baseline_period: AnalysisPeriod,
    comparison_period: AnalysisPeriod,
) -> RetentionResult:
    """Compare annualized counts, rejecting partial years and zero baseline."""
    baseline_count = len(_within(population.eligible, baseline_period))
    comparison_count = len(_within(population.eligible, comparison_period))
    if not _contained_in_context(
        baseline_period, population.context.period
    ) or not _contained_in_context(comparison_period, population.context.period):
        return RetentionResult(
            None,
            baseline_count,
            comparison_count,
            None,
            None,
            baseline_period,
            comparison_period,
            population.context,
            ANNUALIZATION_METHOD,
            MetricUnavailable("unavailable", "metric period is outside overall analysis period"),
        )
    if not _complete_calendar_period(baseline_period) or not _complete_calendar_period(
        comparison_period
    ):
        return RetentionResult(
            None,
            baseline_count,
            comparison_count,
            None,
            None,
            baseline_period,
            comparison_period,
            population.context,
            ANNUALIZATION_METHOD,
            MetricUnavailable("unavailable", "period is not complete calendar-year aligned"),
        )
    baseline_annualized = Decimal(baseline_count) / Decimal(
        baseline_period.end.year - baseline_period.start.year + 1
    )
    comparison_annualized = Decimal(comparison_count) / Decimal(
        comparison_period.end.year - comparison_period.start.year + 1
    )
    if baseline_annualized == 0:
        return RetentionResult(
            None,
            baseline_count,
            comparison_count,
            baseline_annualized,
            comparison_annualized,
            baseline_period,
            comparison_period,
            population.context,
            ANNUALIZATION_METHOD,
            MetricUnavailable("unavailable", "baseline annualized transaction count is zero"),
        )
    return RetentionResult(
        comparison_annualized / baseline_annualized,
        baseline_count,
        comparison_count,
        baseline_annualized,
        comparison_annualized,
        baseline_period,
        comparison_period,
        population.context,
        ANNUALIZATION_METHOD,
    )


def maximum_drawdown(
    population: TransactionPopulation, period: AnalysisPeriod | None = None
) -> MddResult:
    """Calculate observed monthly-median peak-to-later-trough drawdown."""
    selected_period = period or population.context.period
    if not _contained_in_context(selected_period, population.context.period):
        return MddResult(
            None,
            (),
            None,
            None,
            population.context,
            selected_period,
            PRICE_SERIES_METHOD,
            MISSING_MONTH_METHOD,
            MetricUnavailable("unavailable", "metric period is outside overall analysis period"),
        )
    observations = monthly_median_prices(population, selected_period)
    if len(observations) < 2:
        return MddResult(
            None,
            observations,
            None,
            None,
            population.context,
            selected_period,
            PRICE_SERIES_METHOD,
            MISSING_MONTH_METHOD,
            MetricUnavailable("unavailable", "fewer than two observed months"),
        )
    peak = observations[0]
    best_peak = peak
    best_trough = observations[0]
    best_value = Decimal(0)
    for observation in observations[1:]:
        value = observation.median_krw / peak.median_krw - Decimal(1)
        if value < best_value:
            best_value, best_peak, best_trough = value, peak, observation
        if observation.median_krw > peak.median_krw:
            peak = observation
    return MddResult(
        best_value,
        observations,
        best_peak,
        best_trough,
        population.context,
        selected_period,
        PRICE_SERIES_METHOD,
        MISSING_MONTH_METHOD,
    )


def analyze(
    transactions: Iterable[NormalizedTransaction],
    context: AnalysisContext,
    *,
    turnover_period: AnalysisPeriod | None = None,
    household: HouseholdEvidence | None = None,
    baseline_period: AnalysisPeriod | None = None,
    comparison_period: AnalysisPeriod | None = None,
    data_status: str = DataCoverageStatus.COMPLETE,
) -> AnalysisResult:
    """Compute all M2 metrics from one shared population with established coverage."""
    if data_status not in (DataCoverageStatus.COMPLETE, DataCoverageStatus.VALID_EMPTY):
        raise ValueError("data_status must be 'complete' or 'valid_empty'")
    population = build_population(transactions, context)
    known = tuple(
        transaction
        for transaction in population.raw
        if transaction.apartment_id == context.apartment.internal_id
        and context.period.includes(transaction.contract_date)
    )
    grouping = ExclusiveAreaGroupingPolicy()
    available_groups = grouping.group(transaction.exclusive_area_sqm for transaction in known)
    turnover_result = None
    if turnover_period is not None and household is not None:
        turnover_result = turnover(population, turnover_period, household)
    retention_result = None
    if baseline_period is not None and comparison_period is not None:
        retention_result = retention(population, baseline_period, comparison_period)
    annual_periods = _complete_year_periods(context.period)
    annual_household = household or HouseholdEvidence(None, "complex", None)
    annual_results = tuple(
        turnover(population, year_period, annual_household) for year_period in annual_periods
    )
    return AnalysisResult(
        population,
        yearly_price_summaries(population),
        monthly_median_prices(population),
        turnover_result,
        retention_result,
        maximum_drawdown(population),
        annual_results,
        available_groups,
        grouping.name,
        context.period,
        data_status,
    )


def _is_eligible(transaction: NormalizedTransaction, context: AnalysisContext) -> bool:
    return (
        transaction.apartment_id == context.apartment.internal_id
        and context.period.includes(transaction.contract_date)
        and context.area_selection.includes(transaction.exclusive_area_sqm)
        and context.inclusion_policy.includes(transaction)
    )


def _within(
    transactions: Sequence[NormalizedTransaction], period: AnalysisPeriod
) -> tuple[NormalizedTransaction, ...]:
    return tuple(
        transaction for transaction in transactions if period.includes(transaction.contract_date)
    )


def _by_year(
    transactions: Iterable[NormalizedTransaction],
) -> dict[int, tuple[NormalizedTransaction, ...]]:
    grouped: dict[int, list[NormalizedTransaction]] = {}
    for transaction in transactions:
        grouped.setdefault(transaction.contract_date.year, []).append(transaction)
    return {year: tuple(items) for year, items in grouped.items()}


def _mean(transactions: Sequence[NormalizedTransaction]) -> Decimal | None:
    return (
        None
        if not transactions
        else Decimal(sum(item.price_krw for item in transactions)) / Decimal(len(transactions))
    )


def _median(transactions: Sequence[NormalizedTransaction]) -> Decimal:
    prices = sorted(item.price_krw for item in transactions)
    middle = len(prices) // 2
    if len(prices) % 2:
        return Decimal(prices[middle])
    return (Decimal(prices[middle - 1]) + Decimal(prices[middle])) / Decimal(2)


def _complete_calendar_period(period: AnalysisPeriod) -> bool:
    return period.start == date(period.start.year, 1, 1) and period.end == date(
        period.end.year, 12, 31
    )


def _contained_in_context(period: AnalysisPeriod, context_period: AnalysisPeriod) -> bool:
    return context_period.start <= period.start and period.end <= context_period.end


def _complete_year_periods(period: AnalysisPeriod) -> tuple[AnalysisPeriod, ...]:
    start_year = (
        period.start.year
        if period.start == date(period.start.year, 1, 1)
        else period.start.year + 1
    )
    end_year = (
        period.end.year if period.end == date(period.end.year, 12, 31) else period.end.year - 1
    )
    return tuple(
        AnalysisPeriod(date(year, 1, 1), date(year, 12, 31))
        for year in range(start_year, end_year + 1)
    )

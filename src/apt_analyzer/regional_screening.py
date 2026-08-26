"""Regional candidate caching, bounded ingestion, and scalar screening."""

from __future__ import annotations

from collections.abc import Callable, Iterable, Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, date, datetime
from decimal import Decimal
from enum import StrEnum
from typing import Protocol

from apt_analyzer.analytics import (
    DataCoverageStatus,
    HouseholdEvidence,
    analyze,
    discover_area_groups,
)
from apt_analyzer.apartment_data import ApartmentCandidate, IdentityResolution
from apt_analyzer.comparison import CommonAnalysisConfig
from apt_analyzer.domain import (
    AnalysisContext,
    AnalysisPeriod,
    Apartment,
    AreaSelection,
    NormalizedTransaction,
)


class CandidateRefreshState(StrEnum):
    """States distinguishing cache freshness, emptiness, and source failure."""

    FRESH = "fresh"
    VALID_EMPTY = "valid_empty"
    CACHE_MISS = "cache_miss"
    STALE = "stale"
    EXTERNAL_FAILURE = "external_failure"


@dataclass(frozen=True, slots=True)
class RegionalCandidate(ApartmentCandidate):
    """Candidate with explicit source and region provenance."""


@dataclass(frozen=True, slots=True)
class CandidateRefreshReport:
    """Deterministic result of reading or refreshing one source-region snapshot."""

    state: CandidateRefreshState
    candidates: tuple[RegionalCandidate, ...] = ()
    refreshed_at: str | None = None
    skipped: bool = False
    previous_state: CandidateRefreshState | None = None
    error: str | None = None


@dataclass(slots=True)
class _Snapshot:
    candidates: tuple[RegionalCandidate, ...]
    refreshed_at: str


class CandidateCache:
    """Small deterministic source/region cache suitable for injected source boundaries."""

    def __init__(self, clock: Callable[[], datetime] | None = None) -> None:
        """Create a cache with an injectable clock for deterministic tests."""
        self._clock = clock or (lambda: datetime.now(UTC).replace(microsecond=0))
        self._snapshots: dict[tuple[str, str], _Snapshot] = {}

    def read(
        self, source_name: str, region_code: str, *, cutoff: datetime | None = None
    ) -> CandidateRefreshReport:
        """Read a source-region snapshot and classify its freshness."""
        snapshot = self._snapshots.get((source_name, region_code))
        if snapshot is None:
            return CandidateRefreshReport(CandidateRefreshState.CACHE_MISS)
        state = CandidateRefreshState.FRESH
        if cutoff is not None and snapshot.refreshed_at < cutoff.isoformat():
            state = CandidateRefreshState.STALE
        if not snapshot.candidates and state is CandidateRefreshState.FRESH:
            state = CandidateRefreshState.VALID_EMPTY
        return CandidateRefreshReport(state, snapshot.candidates, snapshot.refreshed_at)

    def refresh(
        self,
        source_name: str,
        region_code: str,
        fetch: Callable[[], Iterable[RegionalCandidate]],
        *,
        cutoff: datetime | None = None,
        force: bool = False,
    ) -> CandidateRefreshReport:
        """Atomically replace a snapshot, preserving it when the source fails."""
        previous = self.read(source_name, region_code, cutoff=cutoff)
        if not force and previous.state in (
            CandidateRefreshState.FRESH,
            CandidateRefreshState.VALID_EMPTY,
        ):
            return CandidateRefreshReport(
                previous.state, previous.candidates, previous.refreshed_at, True
            )
        try:
            candidates = tuple(
                sorted(fetch(), key=lambda c: (c.source_id, c.name, c.legal_dong_code))
            )
            timestamp = self._clock().isoformat()
            self._snapshots[(source_name, region_code)] = _Snapshot(candidates, timestamp)
            state = (
                CandidateRefreshState.VALID_EMPTY if not candidates else CandidateRefreshState.FRESH
            )
            return CandidateRefreshReport(state, candidates, timestamp)
        except Exception as error:  # noqa: BLE001
            return CandidateRefreshReport(
                CandidateRefreshState.EXTERNAL_FAILURE,
                previous.candidates,
                previous.refreshed_at,
                previous_state=previous.state,
                error=str(error),
            )


class PersistentCandidateStore(Protocol):
    """SQLite candidate persistence operations."""

    def load_candidate_snapshot(
        self, source_name: str, region_code: str
    ) -> Sequence[Mapping[str, object]]:
        """Load typed metadata rows."""
        ...

    def region_coverage(self, source_name: str, region_code: str) -> Mapping[str, str] | None:
        """Load region freshness state."""
        ...

    def region_attempt(self, source_name: str, region_code: str) -> Mapping[str, str] | None:
        """Load the latest candidate-source attempt."""
        ...

    def record_region_failure(
        self, source_name: str, region_code: str, *, attempted_at: str, error: str
    ) -> None:
        """Persist an external failure without replacing successful coverage."""
        ...

    def save_candidate_snapshot(
        self,
        source_name: str,
        region_code: str,
        candidates: Iterable[RegionalCandidate],
        *,
        fetched_at: str,
    ) -> None:
        """Persist an atomic candidate snapshot."""
        ...


class SQLiteCandidateCache:
    """Persistent candidate cache backed by ``SQLiteStore`` region snapshots."""

    def __init__(
        self, store: PersistentCandidateStore, clock: Callable[[], datetime] | None = None
    ) -> None:
        """Create a persistent cache using a SQLiteStore-compatible object."""
        self._store = store
        self._clock = clock or (lambda: datetime.now(UTC).replace(microsecond=0))

    def read(
        self, source_name: str, region_code: str, *, cutoff: datetime | None = None
    ) -> CandidateRefreshReport:
        """Read typed candidate metadata and persisted freshness state."""
        rows = self._store.load_candidate_snapshot(source_name, region_code)
        coverage = self._store.region_coverage(source_name, region_code)
        attempt = self._store.region_attempt(source_name, region_code)
        if coverage is None and attempt is None:
            return CandidateRefreshReport(CandidateRefreshState.CACHE_MISS)
        candidates = tuple(
            RegionalCandidate(
                str(row["source_id"]),
                str(row["name"]),
                str(row["legal_dong_code"]),
                str(row["lot_address"]),
                str(row["road_address"]),
            )
            for row in rows
        )
        successful_state = (
            CandidateRefreshState.CACHE_MISS
            if coverage is None
            else (
                CandidateRefreshState.VALID_EMPTY
                if coverage["result_state"] == "valid_empty"
                else CandidateRefreshState.FRESH
            )
        )
        if (
            coverage is not None
            and cutoff is not None
            and coverage["fetched_at"] < cutoff.isoformat()
        ):
            successful_state = CandidateRefreshState.STALE
        if attempt is not None and attempt["status"] == "failed":
            return CandidateRefreshReport(
                CandidateRefreshState.EXTERNAL_FAILURE,
                candidates,
                None if coverage is None else coverage["fetched_at"],
                previous_state=successful_state,
                error=attempt.get("error") or "external candidate source failed",
            )
        return CandidateRefreshReport(
            successful_state,
            candidates,
            None if coverage is None else coverage["fetched_at"],
        )

    def refresh(
        self,
        source_name: str,
        region_code: str,
        fetch: Callable[[], Iterable[RegionalCandidate]],
        *,
        cutoff: datetime | None = None,
        force: bool = False,
    ) -> CandidateRefreshReport:
        """Replace one persisted snapshot atomically, preserving failures."""
        previous = self.read(source_name, region_code, cutoff=cutoff)
        if not force and previous.state in (
            CandidateRefreshState.FRESH,
            CandidateRefreshState.VALID_EMPTY,
        ):
            return CandidateRefreshReport(
                previous.state, previous.candidates, previous.refreshed_at, True
            )
        try:
            candidates = tuple(sorted(fetch(), key=lambda c: (c.source_id, c.name)))
            timestamp = self._clock().isoformat()
            self._store.save_candidate_snapshot(
                source_name, region_code, candidates, fetched_at=timestamp
            )
            state = (
                CandidateRefreshState.VALID_EMPTY if not candidates else CandidateRefreshState.FRESH
            )
            return CandidateRefreshReport(state, candidates, timestamp)
        except Exception as error:  # noqa: BLE001
            attempted_at = self._clock().isoformat()
            self._store.record_region_failure(
                source_name, region_code, attempted_at=attempted_at, error=str(error)
            )
            return CandidateRefreshReport(
                CandidateRefreshState.EXTERNAL_FAILURE,
                previous.candidates,
                previous.refreshed_at,
                previous_state=previous.state,
                error=str(error),
            )


@dataclass(frozen=True, slots=True)
class RegionalIngestPlan:
    """Immutable bounded request for regional candidate and transaction ingestion."""

    regions: tuple[str, ...]
    period: AnalysisPeriod
    candidate_source_ids: frozenset[str] = frozenset()
    source_name: str = "K-APT apartment list"
    refresh_before: datetime | None = None

    def __post_init__(self) -> None:
        """Reject unbounded or ambiguous ingestion scopes."""
        if not self.regions or any(not value.strip() for value in self.regions):
            raise ValueError("regions must be an explicit non-empty set")
        if len(set(self.regions)) != len(self.regions):
            raise ValueError("regions must be unique")
        if not self.source_name.strip():
            raise ValueError("source_name must not be empty")


@dataclass(frozen=True, slots=True)
class RegionalIngestReport:
    """Deterministic aggregate of bounded regional ingestion work."""

    candidates_seen: int
    candidates_resolved: int
    candidate_failures: tuple[str, ...]
    updates: Mapping[str, object]
    candidate_refresh: Mapping[str, CandidateRefreshReport]


class RegionalSource(Protocol):
    """Injected source boundary needed by bounded regional ingestion."""

    def list_region(self, region: str) -> Sequence[ApartmentCandidate]:
        """List candidates for one region."""
        ...

    def resolve(
        self, candidate: ApartmentCandidate
    ) -> tuple[ApartmentCandidate, IdentityResolution]:
        """Resolve source identity to an internal apartment."""
        ...

    def retrieve(
        self, candidate: ApartmentCandidate, apartment: Apartment, period: AnalysisPeriod
    ) -> Iterable[NormalizedTransaction]:
        """Retrieve normalized transactions for one bounded month."""
        ...


class RegionalStore(PersistentCandidateStore, Protocol):
    """Minimal persistence boundary used by regional ingestion."""

    def save_apartment(self, apartment: Apartment) -> None:
        """Persist an internal apartment identity."""
        ...

    def update_incremental(
        self,
        apartment: Apartment,
        period: AnalysisPeriod,
        fetch_month: Callable[[str], Iterable[NormalizedTransaction]],
        *,
        refresh_before: datetime | None,
        source_name: str,
    ) -> object:
        """Persist one apartment's monthly incremental updates."""
        ...

    def save_candidate_snapshot(
        self,
        source_name: str,
        region_code: str,
        candidates: Iterable[RegionalCandidate],
        *,
        fetched_at: str,
    ) -> None:
        """Persist regional candidate metadata."""
        ...

    def link_candidate_resolution(
        self,
        source_name: str,
        region_code: str,
        source_id: str,
        apartment_id: str,
        *,
        resolved_at: str,
    ) -> None:
        """Persist candidate identity linkage."""
        ...


def ingest_regional(
    plan: RegionalIngestPlan,
    *,
    source: RegionalSource,
    store: RegionalStore,
) -> RegionalIngestReport:
    """Resolve and incrementally persist only candidates in the plan's regions."""
    seen = resolved = 0
    failures: list[str] = []
    updates: dict[str, object] = {}
    refresh_reports: dict[str, CandidateRefreshReport] = {}
    scoped_candidates: list[tuple[str, RegionalCandidate]] = []
    cache = SQLiteCandidateCache(store)
    for region in plan.regions:
        refresh = cache.refresh(
            plan.source_name,
            region,
            lambda selected_region=region: tuple(
                RegionalCandidate(
                    c.source_id, c.name, c.legal_dong_code, c.lot_address, c.road_address
                )
                for c in source.list_region(selected_region)
            ),
            cutoff=plan.refresh_before,
        )
        refresh_reports[region] = refresh
        if refresh.state is CandidateRefreshState.EXTERNAL_FAILURE:
            failures.append(f"{region}:candidate-refresh:{refresh.error}")
            continue
        for candidate in refresh.candidates:
            if not candidate.legal_dong_code.startswith(region):
                raise ValueError(
                    f"candidate {candidate.source_id} does not belong to requested region {region}"
                )
            scoped_candidates.append((region, candidate))
    source_ids = [candidate.source_id for _, candidate in scoped_candidates]
    if len(source_ids) != len(set(source_ids)):
        raise ValueError("candidate source ID appears in more than one requested region")
    missing = plan.candidate_source_ids - set(source_ids)
    failures.extend(f"candidate:{source_id}:not-found" for source_id in sorted(missing))
    for region, candidate in sorted(
        scoped_candidates, key=lambda item: (item[0], item[1].source_id)
    ):
        if plan.candidate_source_ids and candidate.source_id not in plan.candidate_source_ids:
            continue
        seen += 1
        try:
            enriched, identity = source.resolve(candidate)
            if identity.apartment is None or identity.status.value != "resolved":
                failures.append(f"{region}:{candidate.source_id}:unresolved")
                continue
            resolved += 1
            apartment = identity.apartment
            timestamp = datetime.now(UTC).replace(microsecond=0).isoformat()
            store.link_candidate_resolution(
                plan.source_name,
                region,
                candidate.source_id,
                apartment.internal_id,
                resolved_at=timestamp,
            )
            store.save_apartment(apartment)
            report = store.update_incremental(
                apartment,
                plan.period,
                lambda month, item=enriched, target=apartment: source.retrieve(
                    item, target, _month_period(month)
                ),
                refresh_before=plan.refresh_before,
                source_name="MOLIT apartment sale transactions",
            )
            updates[apartment.internal_id] = report
        except Exception as error:  # noqa: BLE001 - partial source failures are reported
            failures.append(f"{region}:{candidate.source_id}:{error}")
    return RegionalIngestReport(seen, resolved, tuple(failures), updates, refresh_reports)


@dataclass(frozen=True, slots=True)
class CandidateScreenRule:
    """One fixed-unit scalar comparison rule."""

    metric: str
    operator: str
    value: Decimal
    unit: str
    method: str = "overall-period eligible population"


@dataclass(frozen=True, slots=True)
class CandidateScreenResult:
    """Screen outcome with values, unavailable metrics, and explicit disclaimer."""

    candidate_id: str
    included: bool
    values: Mapping[str, Decimal]
    unavailable: Mapping[str, str]
    exclusions: tuple[str, ...]
    context: AnalysisContext
    data_status: str
    disclaimer: str = "Historical screening only; this is not an investment recommendation."


SUPPORTED_UNITS = {
    "median_price_krw": "KRW",
    "median_area_sqm": "sqm",
    "transaction_count": "count",
    "turnover_ratio": "ratio",
    "retention_ratio": "ratio",
    "mdd_ratio": "ratio",
}
SUPPORTED_METHODS = {
    "median_price_krw": "overall-period eligible population",
    "median_area_sqm": "overall-period eligible population",
    "transaction_count": "overall-period eligible population",
    "turnover_ratio": "complete-calendar-year-average",
    "retention_ratio": "complete-calendar-year-average",
    "mdd_ratio": "observed monthly median",
}
OPERATORS = {"eq", "ne", "gt", "gte", "lt", "lte"}


def screen_candidates(
    candidates: Sequence[Apartment],
    transactions: Mapping[str, Sequence[NormalizedTransaction]],
    config: CommonAnalysisConfig,
    rules: Sequence[CandidateScreenRule],
    *,
    coverage: Mapping[str, Mapping[str, str]] | None = None,
    households: Mapping[str, HouseholdEvidence] | None = None,
) -> tuple[CandidateScreenResult, ...]:
    """Apply all rules with one common analysis configuration."""
    if not rules:
        raise ValueError("at least one screening rule is required")
    if config.price_series_method != "observed monthly median":
        raise ValueError("unsupported price series method")
    if config.area_grouping_policy != "integer-floor-exclusive-area":
        raise ValueError("unsupported area grouping policy")
    for rule in rules:
        if rule.metric not in SUPPORTED_UNITS or rule.unit != SUPPORTED_UNITS[rule.metric]:
            raise ValueError(f"invalid unit for metric {rule.metric}")
        if rule.operator not in OPERATORS:
            raise ValueError(f"unsupported operator: {rule.operator}")
        if rule.method != SUPPORTED_METHODS[rule.metric]:
            raise ValueError(f"invalid method for metric {rule.metric}")
    candidate_ids = {candidate.internal_id for candidate in candidates}
    if len(candidate_ids) != len(candidates):
        raise ValueError("screening candidates must have distinct internal IDs")
    if set(transactions) - candidate_ids:
        raise ValueError("transactions mapping contains an unknown candidate")
    if set(households or {}) - candidate_ids:
        raise ValueError("households mapping contains an unknown candidate")
    for apartment_id, records in transactions.items():
        if any(record.apartment_id != apartment_id for record in records):
            raise ValueError("transaction apartment ID does not match mapping candidate")
    required_months = _months(config.overall_period)
    results: list[CandidateScreenResult] = []
    for apartment in candidates:
        records = tuple(
            record
            for record in transactions.get(apartment.internal_id, ())
            if config.overall_period.includes(record.contract_date)
        )
        unavailable: dict[str, str] = {}
        values: dict[str, Decimal] = {}
        exclusions: list[str] = []
        candidate_coverage: Mapping[str, str] = (
            coverage.get(apartment.internal_id, {}) if coverage is not None else {}
        )
        if coverage is not None and (
            set(candidate_coverage) != set(required_months)
            or any(
                state not in {"complete", "valid_empty"} for state in candidate_coverage.values()
            )
        ):
            unavailable["coverage"] = "requested monthly coverage is incomplete"
        all_valid_empty = bool(candidate_coverage) and all(
            state == "valid_empty" for state in candidate_coverage.values()
        )
        selected_group = None
        if config.area_group_key is not None:
            selected_group = next(
                (
                    group
                    for group in discover_area_groups(records)
                    if group.key == config.area_group_key
                ),
                None,
            )
            if selected_group is None:
                unavailable["area_group"] = "requested area group is absent from candidate evidence"
        context = AnalysisContext(
            apartment,
            config.overall_period,
            AreaSelection.all()
            if selected_group is None
            else AreaSelection.for_group(selected_group),
            config.inclusion_policy,
        )
        result = analyze(
            records,
            context,
            turnover_period=config.turnover_period,
            household=(households or {}).get(
                apartment.internal_id,
                HouseholdEvidence(
                    None,
                    "complex" if config.area_group_key is None else config.area_group_key,
                    None,
                ),
            ),
            baseline_period=config.baseline_period,
            comparison_period=config.comparison_period,
            mdd_period=config.mdd_period,
            data_status=(
                DataCoverageStatus.VALID_EMPTY
                if all_valid_empty and not records
                else DataCoverageStatus.COMPLETE
            ),
        )
        eligible = result.population.eligible
        metrics: dict[str, Decimal | None] = {
            "median_price_krw": _median([Decimal(t.price_krw) for t in eligible]),
            "median_area_sqm": _median([t.exclusive_area_sqm for t in eligible]),
            "transaction_count": Decimal(len(eligible)),
            "turnover_ratio": result.turnover.value if result.turnover else None,
            "retention_ratio": result.retention.value if result.retention else None,
            "mdd_ratio": result.mdd.value,
        }
        reasons = {
            "turnover_ratio": (
                result.turnover.unavailable.reason
                if result.turnover and result.turnover.unavailable
                else "metric unavailable"
            ),
            "retention_ratio": (
                result.retention.unavailable.reason
                if result.retention and result.retention.unavailable
                else "metric unavailable"
            ),
            "mdd_ratio": (
                result.mdd.unavailable.reason if result.mdd.unavailable else "metric unavailable"
            ),
        }
        for rule in rules:
            value = metrics[rule.metric]
            if value is None or "coverage" in unavailable or "area_group" in unavailable:
                unavailable.setdefault(rule.metric, reasons.get(rule.metric, "metric unavailable"))
                exclusions.append(f"{rule.metric}: unavailable")
            else:
                values[rule.metric] = value
                if not _matches(value, rule):
                    exclusions.append(f"{rule.metric}: rule failed")
        results.append(
            CandidateScreenResult(
                apartment.internal_id,
                not exclusions and not unavailable,
                values,
                unavailable,
                tuple(exclusions),
                context,
                result.data_status,
            )
        )
    return tuple(results)


def _median(values: Sequence[Decimal]) -> Decimal | None:
    if not values:
        return None
    ordered = sorted(values)
    middle = len(ordered) // 2
    return ordered[middle] if len(ordered) % 2 else (ordered[middle - 1] + ordered[middle]) / 2


def _matches(value: Decimal, rule: CandidateScreenRule) -> bool:
    return {
        "eq": value == rule.value,
        "ne": value != rule.value,
        "gt": value > rule.value,
        "gte": value >= rule.value,
        "lt": value < rule.value,
        "lte": value <= rule.value,
    }[rule.operator]


def _months(period: AnalysisPeriod) -> tuple[str, ...]:
    start, end = period.start, period.end
    year, month = start.year, start.month
    result: list[str] = []
    while (year, month) <= (end.year, end.month):
        result.append(f"{year:04d}{month:02d}")
        month += 1
        if month == 13:
            year, month = year + 1, 1
    return tuple(result)


def _month_period(month: str) -> AnalysisPeriod:
    year, number = int(month[:4]), int(month[4:])
    start = date(year, number, 1)
    if number == 12:
        end = date(year + 1, 1, 1)
    else:
        end = date(year, number + 1, 1)
    return AnalysisPeriod(start, date.fromordinal(end.toordinal() - 1))

"""Independent descriptive analysis for an explicit regional peer group."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from decimal import ROUND_HALF_EVEN, Decimal
from itertools import combinations


@dataclass(frozen=True, slots=True)
class MetricDefinition:
    """Identify one scalar metric without redefining its upstream meaning."""

    metric: str
    unit: str
    method: str

    def __post_init__(self) -> None:
        """Reject incomplete metadata that would make results uninterpretable."""
        if not self.metric.strip() or not self.unit.strip() or not self.method.strip():
            raise ValueError("metric definition fields must not be empty")


@dataclass(frozen=True, slots=True)
class MetricObservation:
    """Carry one candidate's available values and explicit unavailable states."""

    candidate_id: str
    values: Mapping[str, Decimal]
    unavailable: Mapping[str, str]


@dataclass(frozen=True, slots=True)
class MetricDistribution:
    """Describe observed values with explicit population and quantile semantics."""

    metric: str
    unit: str
    method: str
    sample_size: int
    missing_count: int
    minimum: Decimal | None
    q1: Decimal | None
    median: Decimal | None
    q3: Decimal | None
    maximum: Decimal | None
    quantile_method: str = "inclusive linear interpolation"


@dataclass(frozen=True, slots=True)
class MetricCorrelation:
    """Expose one pairwise-complete Spearman relationship and its evidence count."""

    left_metric: str
    right_metric: str
    sample_size: int
    value: Decimal | None
    unavailable_reason: str | None
    method: str = "Spearman midrank, rounded to 6 decimal places"


@dataclass(frozen=True, slots=True)
class CandidateRelativeProfile:
    """Report descriptive percentiles without assigning a quality direction."""

    candidate_id: str
    values: Mapping[str, Decimal]
    percentiles: Mapping[str, Decimal]
    unavailable: Mapping[str, str]


@dataclass(frozen=True, slots=True)
class RegionalProfile:
    """Aggregate distributions, correlations, and candidate-relative positions."""

    distributions: Mapping[str, MetricDistribution]
    correlations: tuple[MetricCorrelation, ...]
    candidates: tuple[CandidateRelativeProfile, ...]
    disclaimer: str = (
        "Historical descriptive analysis only; this is not an investment recommendation, "
        "and a higher percentile does not mean better."
    )


def profile_metrics(
    observations: Sequence[MetricObservation],
    definitions: Sequence[MetricDefinition],
) -> RegionalProfile:
    """Profile scalar observations without changing their upstream calculation contracts.

    Missing values are excluded independently per metric. Percentiles are empirical
    midranks within the supplied peer group. Correlations use only observations where
    both metrics are available.
    """
    if not definitions:
        raise ValueError("at least one metric definition is required")
    candidate_ids = [item.candidate_id for item in observations]
    if any(not value.strip() for value in candidate_ids) or len(candidate_ids) != len(
        set(candidate_ids)
    ):
        raise ValueError("candidate IDs must be non-empty and distinct")
    metrics = [definition.metric for definition in definitions]
    if len(metrics) != len(set(metrics)):
        raise ValueError("metric definitions must be distinct")
    supported = set(metrics)
    for observation in observations:
        if set(observation.values) - supported or set(observation.unavailable) - supported:
            raise ValueError("observation contains an undefined metric")
        if set(observation.values) & set(observation.unavailable):
            raise ValueError("metric cannot be both available and unavailable")

    values_by_metric = {
        metric: tuple(
            observation.values[metric]
            for observation in observations
            if metric in observation.values
        )
        for metric in metrics
    }
    distributions = {
        definition.metric: _distribution(
            definition,
            values_by_metric[definition.metric],
            len(observations),
        )
        for definition in definitions
    }
    correlations = tuple(
        _correlation(left, right, observations) for left, right in combinations(metrics, 2)
    )
    profiles: list[CandidateRelativeProfile] = []
    for observation in sorted(observations, key=lambda item: item.candidate_id):
        unavailable = {
            metric: observation.unavailable.get(metric, "metric unavailable")
            for metric in metrics
            if metric not in observation.values
        }
        percentiles = {
            metric: _midrank_percentile(value, values_by_metric[metric])
            for metric, value in observation.values.items()
        }
        profiles.append(
            CandidateRelativeProfile(
                observation.candidate_id,
                dict(observation.values),
                percentiles,
                unavailable,
            )
        )
    return RegionalProfile(distributions, correlations, tuple(profiles))


def _distribution(
    definition: MetricDefinition,
    values: Sequence[Decimal],
    population_size: int,
) -> MetricDistribution:
    ordered = tuple(sorted(values))
    if not ordered:
        return MetricDistribution(
            definition.metric,
            definition.unit,
            definition.method,
            0,
            population_size,
            None,
            None,
            None,
            None,
            None,
        )
    return MetricDistribution(
        definition.metric,
        definition.unit,
        definition.method,
        len(ordered),
        population_size - len(ordered),
        ordered[0],
        _quantile(ordered, Decimal("0.25")),
        _quantile(ordered, Decimal("0.5")),
        _quantile(ordered, Decimal("0.75")),
        ordered[-1],
    )


def _quantile(values: Sequence[Decimal], probability: Decimal) -> Decimal:
    if len(values) == 1:
        return values[0]
    position = probability * Decimal(len(values) - 1)
    lower_index = int(position)
    upper_index = min(lower_index + 1, len(values) - 1)
    fraction = position - Decimal(lower_index)
    return values[lower_index] + (values[upper_index] - values[lower_index]) * fraction


def _midrank_percentile(value: Decimal, population: Sequence[Decimal]) -> Decimal:
    less = sum(item < value for item in population)
    equal = sum(item == value for item in population)
    return (Decimal(less) + Decimal(equal) / 2) / Decimal(len(population))


def _correlation(
    left_metric: str,
    right_metric: str,
    observations: Sequence[MetricObservation],
) -> MetricCorrelation:
    pairs = tuple(
        (item.values[left_metric], item.values[right_metric])
        for item in observations
        if left_metric in item.values and right_metric in item.values
    )
    if len(pairs) < 2:
        return MetricCorrelation(
            left_metric,
            right_metric,
            len(pairs),
            None,
            "fewer than two pairwise-complete observations",
        )
    left_ranks = _midranks(tuple(left for left, _ in pairs))
    right_ranks = _midranks(tuple(right for _, right in pairs))
    left_mean = sum(left_ranks, Decimal(0)) / Decimal(len(left_ranks))
    right_mean = sum(right_ranks, Decimal(0)) / Decimal(len(right_ranks))
    left_delta = tuple(rank - left_mean for rank in left_ranks)
    right_delta = tuple(rank - right_mean for rank in right_ranks)
    left_variance = sum((value * value for value in left_delta), Decimal(0))
    right_variance = sum((value * value for value in right_delta), Decimal(0))
    if left_variance == 0 or right_variance == 0:
        return MetricCorrelation(
            left_metric,
            right_metric,
            len(pairs),
            None,
            "constant pairwise observations",
        )
    covariance = sum(
        (left * right for left, right in zip(left_delta, right_delta, strict=True)),
        Decimal(0),
    )
    value = (covariance / (left_variance * right_variance).sqrt()).quantize(
        Decimal("0.000001"),
        rounding=ROUND_HALF_EVEN,
    )
    if value == 0:
        value = Decimal(0)
    return MetricCorrelation(left_metric, right_metric, len(pairs), value, None)


def _midranks(values: Sequence[Decimal]) -> tuple[Decimal, ...]:
    ordered = sorted((value, index) for index, value in enumerate(values))
    ranks = [Decimal(0)] * len(values)
    start = 0
    while start < len(ordered):
        end = start + 1
        while end < len(ordered) and ordered[end][0] == ordered[start][0]:
            end += 1
        rank = (Decimal(start + 1) + Decimal(end)) / 2
        for _, original_index in ordered[start:end]:
            ranks[original_index] = rank
        start = end
    return tuple(ranks)

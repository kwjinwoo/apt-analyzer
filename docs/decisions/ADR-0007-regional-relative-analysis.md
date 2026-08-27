---
id: ADR-0007
title: Independent regional relative analysis
status: accepted
date: 2026-08-27
supersedes: []
superseded_by: null
related_requirements: [R-021, R-015, R-019]
---

# ADR-0007: Independent regional relative analysis

## Status

Accepted

## Context

M6 requires the first broader analysis domain to remain independently testable and
interpretable. M5 already provides bounded regional evidence and comparable scalar
metrics, while rental, nearby-complex, and complex-characteristic candidates require
additional source and policy decisions. A regional profile can therefore broaden the
analysis without introducing another external domain or changing liquidity semantics.

## Decision

Introduce relative regional analysis as a descriptive consumer of existing scalar
metric values and explicit unavailable states. The caller supplies an explicit regional
peer group under one common analysis context.

For each metric, report the observed count, missing count, minimum, quartiles and median
using inclusive linear interpolation, and maximum. Candidate percentile is the
empirical midrank `(values below + half of tied values) / available values`. Calculate
pairwise Spearman correlation from midranks, expose the pairwise-complete sample count,
round to six decimal places using half-even rounding, and return unavailable when fewer
than two paired observations exist or either paired series is constant.

Do not assign favorable direction to percentiles or correlations. Output must state
that the result is historical descriptive evidence, not an investment recommendation,
and that a higher percentile does not mean better.

## Rationale

The direction reuses validated M5 boundaries, makes distributions and missingness
visible, and keeps the new statistics downstream of the liquidity core. Midranks handle
ties deterministically; pairwise counts prevent correlations from concealing different
effective populations.

## Alternatives considered

### Composite ranking

Rejected because distributions and relationships are not evidence for stable weights,
prediction, or investment quality.

### New rental or complex-characteristic domain

Deferred because each requires additional source identity, normalization, metric, and
freshness decisions before it can be interpreted independently.

### Imputation or listwise deletion

Rejected because both can hide why a metric is unavailable or discard valid evidence
for unrelated metric pairs.

## Consequences

The profile is meaningful only for its displayed peer group and context. Small samples,
selection effects, sparse transactions, source corrections, and correlated size or area
mix remain interpretation limits. Other M6 candidate domains remain future work rather
than implied by this decision.

## Related documentation

- [R-021](../requirements/R-021-regional-relative-profile.md)
- [Metric definitions](../domain/metrics.md#regional-relative-profile)
- [Roadmap M6](../roadmap.md#m6-broader-apartment-analysis)

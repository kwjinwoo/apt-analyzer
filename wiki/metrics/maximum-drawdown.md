---
title: Maximum Drawdown
type: metric
role: topic
status: active
updated: 2026-08-30
aliases:
  - MDD
  - Price drawdown
tags:
  - price-resilience
  - sparse-series
---

# Maximum Drawdown

## Scope

Maximum drawdown connects an observed representative price series to the largest preceding-peak-to-later-trough decline within the selected analysis context.

## Knowledge

The normative initial definition is maintained in [Metric definitions](../../docs/domain/metrics.md#maximum-drawdown). The graph begins before the formula: identity, area selection, transaction eligibility, monthly aggregation, and sparse evidence determine the series on which the formula operates.

Monthly median price reduces sensitivity to individual trades but does not make apartment prices continuous. A one-transaction month has weak evidence, and a month with no transaction has no observed price. Missing-month treatment and minimum evidence are unresolved and must not be hidden by presentation continuity.

The MDD value is interpretable only with the peak and trough months and prices, price method, population, and inclusion policy. It measures observed historical behavior rather than future downside or fair value.

R-024 also requires monthly MDD evidence to follow the overall interval while
making any completed-month rolling default boundaries visible; this does not
change the observed, gap-preserving price-series semantics.

## Graph connections

- Operates on [Price-series evidence](../data/price-series-evidence.md).
- Uses eligible transactions from [Transaction population](../data/transaction-population.md).
- Receives population and price method from [Analysis context](../domain/analysis-context.md).
- Is affected by [Area group](../domain/area-group.md).
- Shares unusual-record risks with [Transaction quality](../data/transaction-quality.md).

## Requirements

- [R-011: Maximum drawdown](../../docs/requirements/R-011-maximum-drawdown.md)
- [R-012: Maximum-drawdown interval](../../docs/requirements/R-012-mdd-interval.md)
- [R-014: Price visualization](../../docs/requirements/R-014-price-visualization.md)
- [R-018: Outlier-impact inspection](../../docs/requirements/R-018-outlier-impact.md)
- [R-019: Visible analysis context](../../docs/requirements/R-019-analysis-context.md)
- [R-024: Period-driven analysis and completed-month rolling metrics](../../docs/requirements/R-024-period-driven-analysis.md)

## Decisions and open questions

- [OQ-003: Missing months in the price series](../../docs/open-questions.md#oq-003-missing-months-in-the-price-series)
- [OQ-006: Default direct-transaction policy](../../docs/open-questions.md#oq-006-default-direct-transaction-policy)
- [OQ-007: Outlier comparison policy](../../docs/open-questions.md#oq-007-outlier-comparison-policy)
- [OQ-009: Minimum evidence for monthly price observations](../../docs/open-questions.md#oq-009-minimum-evidence-for-monthly-price-observations)

## Evidence and interpretation risks

- Sparse observations can make unit-specific differences look like market movement.
- Carry-forward or interpolation can create unobserved price evidence.
- Direct or unusual transactions can become the peak or trough.
- Mixing area groups can change the price population over time.
- A visually continuous line can obscure long no-trade intervals.

## Verify in the repository

[`maximum_drawdown`](../../src/apt_analyzer/analytics.py) uses observed monthly medians without interpolation, carries its effective period and method labels, and returns peak/trough observations or an explicit sparse-evidence unavailable state. Representative evidence is in [`test_m2.py`](../../tests/test_m2.py).

## Related pages

- [Price-series evidence](../data/price-series-evidence.md)
- [Transaction quality](../data/transaction-quality.md)
- [Analysis context](../domain/analysis-context.md)
- [Open decision map](../project/open-decision-map.md)

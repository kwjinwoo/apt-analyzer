---
title: Price-Series Evidence
type: data
role: topic
status: active
updated: 2026-08-21
aliases:
  - Monthly price evidence
  - Sparse price series
tags:
  - price
  - sparsity
---

# Price-Series Evidence

## Scope

Price-series evidence describes what irregular monthly apartment transactions can support about historical price movement before a price-derived metric is interpreted.

## Knowledge

Monthly median eligible transaction price is the accepted initial aggregation for MDD and price visualization. Aggregation reduces individual noise but does not create an observed value in a no-trade month. One-transaction months are observed but weakly representative.

The sequence is indexed by observed months, while elapsed calendar time still matters to interpretation. Dropping missing months, carrying a prior value forward, and interpolating each encode different claims. No missing-month transformation has been accepted.

Area composition, floor, building, transaction type, cancellations, and unusual records can change the monthly population. A continuous chart line can visually overstate evidence unless gaps and observation strength remain visible.

## Graph connections

- Is built from [Transaction population](transaction-population.md).
- Inherits source uncertainty from [Transaction quality](transaction-quality.md).
- Is segmented by [Area group](../domain/area-group.md).
- Is interpreted with [Analysis context](../domain/analysis-context.md).
- Provides the ordered observations for [Maximum drawdown](../metrics/maximum-drawdown.md).
- Connects visual requirements in the [Requirement map](../project/requirement-map.md).

## Requirements

- [R-007: Periodic transaction aggregation](../../docs/requirements/R-007-periodic-aggregation.md)
- [R-011: Maximum drawdown](../../docs/requirements/R-011-maximum-drawdown.md)
- [R-012: Maximum-drawdown interval](../../docs/requirements/R-012-mdd-interval.md)
- [R-014: Price visualization](../../docs/requirements/R-014-price-visualization.md)

## Decisions and open questions

- [OQ-003: Missing months in the price series](../../docs/open-questions.md#oq-003-missing-months-in-the-price-series)
- [OQ-009: Minimum evidence for monthly price observations](../../docs/open-questions.md#oq-009-minimum-evidence-for-monthly-price-observations)
- Monthly median price is the accepted initial default; missing-month and minimum-evidence policies are not accepted.

## Evidence and interpretation risks

- A single unit-specific transaction can define a month's median.
- Long no-trade intervals can separate the reported peak and trough.
- Changing area composition can resemble price movement.
- An outlier policy can remove the observation that defines MDD.
- Visual interpolation can be mistaken for observed market evidence.

## Verify in the repository

No implementation evidence exists yet. When price series exist, verify monthly grouping, median behavior for even and odd counts, missing-month representation, observation counts, active filters, and sparse real-complex examples.

## Related pages

- [Maximum drawdown](../metrics/maximum-drawdown.md)
- [Transaction population](transaction-population.md)
- [Transaction quality](transaction-quality.md)
- [Open decision map](../project/open-decision-map.md)

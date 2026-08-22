---
title: Area Group
type: domain
role: topic
status: active
updated: 2026-08-21
aliases:
  - Exclusive-area group
  - Area classification
tags:
  - exclusive-area
  - population
---

# Area Group

## Scope

An area group connects precise source-reported exclusive areas to a market-facing selection used to define one analysis population.

## Knowledge

Raw exclusive area and area group are different facts. The raw value preserves source precision; the derived group supports selection and comparison. Grouping values such as `84.81`, `84.92`, and `84.97` can be useful, but the boundary between nearby values is not universally determined by rounding.

Area selection affects transaction volume, price summaries, retention, and MDD because it changes the eligible records. It affects turnover differently: filtering the numerator does not create an exact area-level rate unless the denominator is the household count for that same area group.

The grouping policy must remain replaceable and independently testable. Integer-level grouping is an initial experiment, not a permanent domain truth.

## Graph connections

- Helps define [Transaction population](../data/transaction-population.md).
- Is carried as part of [Analysis context](analysis-context.md).
- Constrains denominator interpretation in [Turnover rate](../metrics/turnover-rate.md).
- Changes the observations available to [Price-series evidence](../data/price-series-evidence.md).
- Affects comparison validity in the [Requirement map](../project/requirement-map.md).

## Requirements

- [R-004: Available-area detection](../../docs/requirements/R-004-area-detection.md)
- [R-005: Exclusive-area grouping](../../docs/requirements/R-005-area-grouping.md)
- [R-006: Area-filtered analysis](../../docs/requirements/R-006-area-filter.md)
- [R-016: Apartment comparison](../../docs/requirements/R-016-apartment-comparison.md)

## Decisions and open questions

- [OQ-002: Area-group boundary](../../docs/open-questions.md#oq-002-area-group-boundary)
- [OQ-008: Area-filtered turnover presentation](../../docs/open-questions.md#oq-008-area-filtered-turnover-presentation)
- No area-grouping ADR has been accepted yet.

## Evidence and interpretation risks

- Nearby raw areas may represent distinct unit products.
- One grouping rule may not match market convention across all complexes.
- Historical transactions may not expose every currently available unit type.
- A common label across complexes does not by itself prove a comparable physical or market segment.

## Verify in the repository

No implementation evidence exists yet. When grouping exists, verify raw-area preservation, deterministic classification, replaceable policy boundaries, area-filter propagation, and real-complex distribution tests.

## Related pages

- [Transaction population](../data/transaction-population.md)
- [Analysis context](analysis-context.md)
- [Turnover rate](../metrics/turnover-rate.md)
- [Maximum drawdown](../metrics/maximum-drawdown.md)

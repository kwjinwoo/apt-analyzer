---
title: Analysis Context
type: domain
role: topic
status: active
updated: 2026-08-21
aliases:
  - Metric context
  - Analysis configuration
tags:
  - reproducibility
  - interpretation
---

# Analysis Context

## Scope

Analysis context is the complete set of conditions needed to interpret, compare, and reproduce an analytics result.

## Knowledge

A metric value is not self-describing. The selected apartment identity, area selection, date boundaries, metric-specific periods, price aggregation, transaction inclusion policy, and denominator scope determine what the value means.

Context must travel with a result rather than depending on session state or interface defaults. Human-readable and machine-readable outputs need equivalent context. Comparison requires common context across subjects while still exposing subject-specific evidence limitations such as missing household counts.

The context establishes reproducibility but does not make incompatible evidence comparable. For example, sharing the label `84㎡` does not prove equivalent area groups, and using the same MDD formula does not remove differences in price-series sparsity.

## Graph connections

- Identifies the subject through [Apartment identity](apartment-identity.md).
- Selects an area population through [Area group](area-group.md).
- Materializes eligibility through [Transaction population](../data/transaction-population.md).
- Supplies periods and denominator scope to [Turnover rate](../metrics/turnover-rate.md).
- Supplies baseline and comparison periods to [Transaction retention rate](../metrics/transaction-retention-rate.md).
- Supplies population and price method to [Maximum drawdown](../metrics/maximum-drawdown.md).

## Requirements

- [R-003: Transaction query period](../../docs/requirements/R-003-query-period.md)
- [R-006: Area-filtered analysis](../../docs/requirements/R-006-area-filter.md)
- [R-016: Apartment comparison](../../docs/requirements/R-016-apartment-comparison.md)
- [R-019: Visible analysis context](../../docs/requirements/R-019-analysis-context.md)

## Decisions and open questions

- [OQ-004: Partial-year annualization](../../docs/open-questions.md#oq-004-partial-year-annualization)
- [OQ-006: Default direct-transaction policy](../../docs/open-questions.md#oq-006-default-direct-transaction-policy)
- [OQ-008: Area-filtered turnover presentation](../../docs/open-questions.md#oq-008-area-filtered-turnover-presentation)

## Evidence and interpretation risks

- Hidden defaults can make two identical-looking values non-comparable.
- Context can be lost when converting domain results into CLI, JSON, export, or UI forms.
- A common configuration cannot compensate for missing or differently scoped source evidence.
- Historical source corrections can make a previously reproducible result stale.

## Verify in the repository

No implementation evidence exists yet. When results exist, verify that context is represented at the domain boundary, preserved through interfaces and exports, and asserted by representative acceptance tests.

## Related pages

- [MVP knowledge map](../project/mvp-knowledge-map.md)
- [Requirement map](../project/requirement-map.md)
- [Transaction quality](../data/transaction-quality.md)
- [Price-series evidence](../data/price-series-evidence.md)

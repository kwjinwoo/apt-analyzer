---
title: Analysis Context
type: domain
role: topic
status: active
updated: 2026-09-03
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

Context must travel with a result rather than depending on session state or interface defaults. Human-readable and machine-readable outputs need equivalent context. Comparison requires common context across subjects, including the MDD period, while still exposing subject-specific evidence limitations such as missing household counts or absent area groups. Persisted monthly coverage carries source-specific freshness evidence; see [ADR-0004](../../docs/decisions/ADR-0004-sqlite-persistence-and-freshness.md).

The context establishes reproducibility but does not make incompatible evidence comparable. For example, sharing the label `84㎡` does not prove equivalent area groups, and using the same MDD formula does not remove differences in price-series sparsity.

Single-apartment human results separate an always-visible comparable core-metric summary from a collapsed but inspectable reproducibility table, while machine JSON retains equivalent context.

[R-024](../../docs/requirements/R-024-period-driven-analysis.md) and [ADR-0010](../../docs/decisions/ADR-0010-completed-month-rolling-analysis.md) add accepted period-driven defaults: an explicit overall interval, visible completed-month derivation methods, and explicit overrides. The rolling anchor is chosen by calendar containment; required turnover/retention spans are consecutive and cannot skip months with missing or failed coverage. Overrides remain subject to metric validity rules and may be unavailable. The defaults do not resolve arbitrary partial-year annualization.

[R-026](../../docs/requirements/R-026-chart-preview.md) adds an exploratory
selection context nested inside the current official context. It reuses the
official apartment, area, inclusion, household, coverage, and overall-period
evidence, but its values do not replace the official result or export.

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
- [R-024: Period-driven analysis and completed-month rolling metrics](../../docs/requirements/R-024-period-driven-analysis.md)
- [R-026: Non-mutating chart period preview](../../docs/requirements/R-026-chart-preview.md)

## Decisions and open questions

- [OQ-006: Default direct-transaction policy](../../docs/open-questions.md#oq-006-default-direct-transaction-policy)
- [OQ-008: Area-filtered turnover presentation](../../docs/open-questions.md#oq-008-area-filtered-turnover-presentation)
- [OQ-004: Partial-year annualization](../../docs/open-questions.md#oq-004-partial-year-annualization)

## Evidence and interpretation risks

- Hidden defaults can make two identical-looking values non-comparable.
- Context can be lost when converting domain results into CLI, JSON, export, or UI forms.
- A common configuration cannot compensate for missing or differently scoped source evidence.
- Historical source corrections can make a previously reproducible result stale.

## Verify in the repository

[`AnalysisContext`](../../src/apt_analyzer/domain.py) represents the subject, inclusive period, area selection, and transaction inclusion policy. [`AnalysisResult`](../../src/apt_analyzer/analytics.py) carries one shared population across M2 metrics, discovered area groups, annual turnover, metric context, and explicit data coverage status; [`cli.py`](../../src/apt_analyzer/cli.py) preserves equivalent JSON/text context. [`comparison.py`](../../src/apt_analyzer/comparison.py) applies one common context including MDD period. Representative behavior is covered by [`test_m2.py`](../../tests/test_m2.py) and [`test_m3.py`](../../tests/test_m3.py).

## Related pages

- [MVP knowledge map](../project/mvp-knowledge-map.md)
- [Requirement map](../project/requirement-map.md)
- [Transaction quality](../data/transaction-quality.md)
- [Price-series evidence](../data/price-series-evidence.md)

---
title: Transaction Retention Rate
type: metric
role: topic
status: active
updated: 2026-09-07
aliases:
  - Downturn transaction retention
tags:
  - liquidity
  - relative-activity
---

# Transaction Retention Rate

## Scope

Transaction retention relates annualized eligible activity in a comparison period to annualized eligible activity in a baseline period.

## Knowledge

The chart preview supports a 12-month selection against its immediately prior
baseline, or a 24-month selection split into first-year baseline and final-year
comparison under [R-028](../../docs/requirements/R-028-chart-preview-retention-split.md).

The normative definition is maintained in [Metric definitions](../../docs/domain/metrics.md#transaction-retention-rate). Retention is contextual: it describes two selected periods under one population policy, not a permanent characteristic of an apartment complex.

Both periods must use the same identity, area group, transaction inclusion rules, and annualization semantics. The ratio normalizes against prior activity rather than household count, so it answers a different question from turnover. A zero baseline is not an ordinary zero-percent case; the ratio is undefined and needs an explicit result policy. The accepted [ADR-0010](../../docs/decisions/ADR-0010-completed-month-rolling-analysis.md) defines the single-analysis default anchored by calendar boundaries at the latest fully contained month, comparing its 12 consecutive months with the preceding non-overlapping 12, with the full 24-month span wholly inside the overall interval. Every month in the span needs successful or valid-empty coverage; any gap makes the default unavailable rather than skipping backward. Legacy comparison/screening flows retain their prior complete-year behavior.

For the current R-028 chart preview, an exact selected 12 months remains the
comparison window against the immediately preceding 12-month baseline. An
exact selected 24 months is split into first-year baseline and final-year
comparison. Other lengths remain unavailable; both windows must fit the overall
context and preserve the official result.

## Graph connections

- Uses two views of [Transaction population](../data/transaction-population.md).
- Receives baseline, comparison, area, and inclusion settings from [Analysis context](../domain/analysis-context.md).
- Complements size-normalized activity in [Turnover rate](turnover-rate.md).
- Shares cancellation, direct-transaction, and correction risks with [Transaction quality](../data/transaction-quality.md).
- Contributes to the comparison flow in the [MVP knowledge map](../project/mvp-knowledge-map.md).

## Requirements

- [R-010: Transaction retention rate](../../docs/requirements/R-010-transaction-retention-rate.md)
- [R-016: Apartment comparison](../../docs/requirements/R-016-apartment-comparison.md)
- [R-019: Visible analysis context](../../docs/requirements/R-019-analysis-context.md)
- [R-024: Period-driven analysis and completed-month rolling metrics](../../docs/requirements/R-024-period-driven-analysis.md)
- [R-026: Non-mutating chart period preview](../../docs/requirements/R-026-chart-preview.md)
- [R-028: Duration-aware chart preview retention split](../../docs/requirements/R-028-chart-preview-retention-split.md)

## Decisions and open questions

- [OQ-005: Zero transaction-retention baseline](../../docs/open-questions.md#oq-005-zero-transaction-retention-baseline)
- [OQ-006: Default direct-transaction policy](../../docs/open-questions.md#oq-006-default-direct-transaction-policy)
- [OQ-004: Partial-year annualization](../../docs/open-questions.md#oq-004-partial-year-annualization)

## Evidence and interpretation risks

- Changing the baseline period can reverse the interpretation.
- Different annualization rules can make numerator and denominator incompatible.
- Low baseline activity can make the ratio unstable even when nonzero.
- Historical corrections can affect one period more than the other.
- Retention does not normalize for household count and must not be labeled turnover.

## Verify in the repository

[`retention`](../../src/apt_analyzer/analytics.py) uses the shared eligible population, consistent complete-year annualization, and an explicit zero-baseline unavailable state. Representative evidence is in [`test_m2.py`](../../tests/test_m2.py).
Adjacent completed 12-month preview windows use the rolling-retention method;
24-month previews split into adjacent 12-month windows. Representative
coverage is in [`test_analysis_preview_splits_24_month_retention_into_baseline_and_comparison`](../../tests/test_web.py)
and [`test_chart_drag_previews_metrics_without_mutating_official_analysis`](../../tests/test_web_e2e.py).

## Related pages

- [Turnover rate](turnover-rate.md)
- [Transaction population](../data/transaction-population.md)
- [Analysis context](../domain/analysis-context.md)
- [Requirement map](../project/requirement-map.md)

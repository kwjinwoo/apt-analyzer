---
title: Transaction Retention Rate
type: metric
role: topic
status: active
updated: 2026-08-21
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

The normative definition is maintained in [Metric definitions](../../docs/domain/metrics.md#transaction-retention-rate). Retention is contextual: it describes two selected periods under one population policy, not a permanent characteristic of an apartment complex.

Both periods must use the same identity, area group, transaction inclusion rules, and annualization semantics. The ratio normalizes against prior activity rather than household count, so it answers a different question from turnover. A zero baseline is not an ordinary zero-percent case; the ratio is undefined and needs an explicit result policy.

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

## Decisions and open questions

- [OQ-004: Partial-year annualization](../../docs/open-questions.md#oq-004-partial-year-annualization)
- [OQ-005: Zero transaction-retention baseline](../../docs/open-questions.md#oq-005-zero-transaction-retention-baseline)
- [OQ-006: Default direct-transaction policy](../../docs/open-questions.md#oq-006-default-direct-transaction-policy)

## Evidence and interpretation risks

- Changing the baseline period can reverse the interpretation.
- Different annualization rules can make numerator and denominator incompatible.
- Low baseline activity can make the ratio unstable even when nonzero.
- Historical corrections can affect one period more than the other.
- Retention does not normalize for household count and must not be labeled turnover.

## Verify in the repository

[`retention`](../../src/apt_analyzer/analytics.py) uses the shared eligible population, consistent complete-year annualization, and an explicit zero-baseline unavailable state. Representative evidence is in [`test_m2.py`](../../tests/test_m2.py).

## Related pages

- [Turnover rate](turnover-rate.md)
- [Transaction population](../data/transaction-population.md)
- [Analysis context](../domain/analysis-context.md)
- [Requirement map](../project/requirement-map.md)

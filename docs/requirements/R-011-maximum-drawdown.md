---
id: R-011
title: Maximum drawdown
status: accepted
priority: P0
created: 2026-08-21
updated: 2026-08-31
origin: "Initial requirements R10"
supersedes: []
superseded_by: null
related_requirements: [R-003, R-006, R-012, R-014, R-017, R-019]
related_decisions: []
---

# R-011: Maximum drawdown

## Intent

Users need an interpretable historical measure of the largest observed price decline without treating irregular individual transactions as a continuous market price.

## Requirement

The system calculates maximum drawdown over a selected price series, using monthly median eligible transaction price as the initial default.

## Acceptance criteria

- **AC-1:** The price population applies the selected apartment, area, period, and inclusion policy.
- **AC-2:** Monthly representative prices use an explicit aggregation method.
- **AC-3:** Drawdown is measured from a preceding peak to a later trough.
- **AC-4:** The result exposes the MDD value and price-series method.
- **AC-5:** Insufficient evidence returns an explicit unavailable or qualified result rather than an invented value.
- **AC-6:** Human presentation identifies MDD as a percentage (`%`) while
  machine results retain the exact signed ratio.

## Constraints

- Missing months must not be silently interpolated.
- Sparse and unusual transactions can materially affect the result and must remain inspectable.

## Non-goals

- Predicting future drawdown or establishing a fair price.

## Verification

### Automated

- [`test_mdd_reports_peak_trough_and_sparse_unavailable_state`](../../tests/test_m2.py) and [`test_mdd_subperiod_is_effective_context_and_serializable`](../../tests/test_m2.py) cover observed monthly medians, sparse evidence, effective period, method labels, and explicit MDD context.

### Manual or data validation

- Inspect MDD inputs and results for sparse and active real complexes.

### Verification gaps

- AC-1 through AC-5 have no implementation evidence yet.

## Open questions

- [OQ-003: Missing months in the price series](../open-questions.md#oq-003-missing-months-in-the-price-series)
- [OQ-006: Default direct-transaction policy](../open-questions.md#oq-006-default-direct-transaction-policy)
- [OQ-009: Minimum evidence for monthly price observations](../open-questions.md#oq-009-minimum-evidence-for-monthly-price-observations)

## Related documentation

- [Maximum drawdown](../domain/metrics.md#maximum-drawdown)
- [Monthly median price](../domain/metrics.md#monthly-median-price)

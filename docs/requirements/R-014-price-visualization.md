---
id: R-014
title: Price visualization
status: accepted
priority: P1
created: 2026-08-21
updated: 2026-08-21
origin: "Initial requirements R12"
supersedes: []
superseded_by: null
related_requirements: [R-011, R-012, R-019]
related_decisions: []
---

# R-014: Price visualization

## Intent

Users need to inspect the price observations behind summary statistics and maximum drawdown.

## Requirement

The user can view the representative transaction-price series over time, with monthly median eligible price as the initial default.

## Acceptance criteria

- **AC-1:** Every plotted value identifies its period and aggregation method.
- **AC-2:** The visualization uses the active apartment, area, date interval, and inclusion policy.
- **AC-3:** Months with no observed eligible price are distinguishable from observed values.
- **AC-4:** When MDD is present, its peak and trough can be identified on the same series.

## Constraints

- Visual continuity must not imply observed prices in missing months.

## Non-goals

- Interpolating a continuous apartment valuation curve.

## Verification

### Automated

Not established yet.

### Manual or data validation

- Visual inspection will be required once a presentation interface exists.

### Verification gaps

- AC-1 through AC-4 have no implementation evidence yet.

## Open questions

- [OQ-003: Missing months in the price series](../open-questions.md#oq-003-missing-months-in-the-price-series)
- [OQ-009: Minimum evidence for monthly price observations](../open-questions.md#oq-009-minimum-evidence-for-monthly-price-observations)

## Related documentation

- [Monthly median price](../domain/metrics.md#monthly-median-price)
- [MDD interval requirement](R-012-mdd-interval.md)

---
id: R-012
title: Maximum-drawdown interval
status: accepted
priority: P0
created: 2026-08-21
updated: 2026-08-21
origin: "Initial requirements R10-1"
supersedes: []
superseded_by: null
related_requirements: [R-011, R-014, R-019]
related_decisions: []
---

# R-012: Maximum-drawdown interval

## Intent

An MDD percentage is not sufficiently interpretable without the observations that produced it.

## Requirement

The maximum-drawdown result identifies the peak and subsequent trough observations that define the reported drawdown.

## Acceptance criteria

- **AC-1:** The result includes peak month and peak representative price.
- **AC-2:** The result includes trough month and trough representative price.
- **AC-3:** The trough occurs after or at a later observation than the peak according to the series order.
- **AC-4:** Peak and trough values use the same price series and analysis context as the MDD value.

## Constraints

- Calendar gaps between observations must remain distinguishable from observed stable prices.

## Non-goals

- Explaining the market cause of the drawdown interval.

## Verification

### Automated

Not established yet.

### Manual or data validation

None.

### Verification gaps

- AC-1 through AC-4 have no implementation evidence yet.

## Open questions

- [OQ-003: Missing months in the price series](../open-questions.md#oq-003-missing-months-in-the-price-series)

## Related documentation

- [Maximum drawdown requirement](R-011-maximum-drawdown.md)
- [Price visualization requirement](R-014-price-visualization.md)

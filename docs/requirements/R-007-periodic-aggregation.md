---
id: R-007
title: Periodic transaction aggregation
status: accepted
priority: P0
created: 2026-08-21
updated: 2026-08-21
origin: "Initial requirements R7"
supersedes: []
superseded_by: null
related_requirements: [R-003, R-006, R-017, R-019]
related_decisions: []
---

# R-007: Periodic transaction aggregation

## Intent

Users need comparable summaries of transaction activity and prices over time, beginning with annual analysis and allowing later monthly or quarterly extension.

## Requirement

The system aggregates eligible transactions by calendar year and reports transaction count, mean price, median price, maximum price, and minimum price.

## Acceptance criteria

- **AC-1:** Each represented year reports the five required statistics from one consistent eligible population.
- **AC-2:** Years with no eligible transactions are distinguishable from missing data or acquisition failure.
- **AC-3:** Area selection, date interval, and inclusion policy are applied before aggregation.
- **AC-4:** The aggregation design does not prevent later monthly or quarterly grouping.

## Constraints

- Monetary values must not lose precision through presentation formatting.
- Averages across heterogeneous areas require the active area selection to remain visible.

## Non-goals

- Quarterly output in the initial MVP.

## Verification

### Automated

Not established yet.

### Manual or data validation

- Compare yearly counts with public transaction records for validation complexes.

### Verification gaps

- AC-1 through AC-4 have no implementation evidence yet.

## Open questions

None.

## Related documentation

- [Transaction volume](../domain/metrics.md#transaction-volume)
- [Price summary](../domain/metrics.md#price-summary)

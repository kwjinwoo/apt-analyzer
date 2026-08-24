---
id: R-015
title: Metric-based apartment screening
status: accepted
priority: P1
created: 2026-08-21
updated: 2026-08-21
origin: "Initial requirements R13"
supersedes: []
superseded_by: null
related_requirements: [R-007, R-008, R-010, R-011, R-016, R-019]
related_decisions: []
---

# R-015: Metric-based apartment screening

## Intent

After metrics are validated across multiple complexes, users should be able to discover candidates that satisfy explicit historical liquidity and price-resilience conditions.

## Requirement

The user can filter a comparable set of apartment complexes by explicit ranges or thresholds for price, area, transaction count, turnover, transaction retention, and MDD.

## Acceptance criteria

- **AC-1:** Each filter exposes its metric, operator, value, unit, and analysis context.
- **AC-2:** All candidate metrics are computed under comparable period, area, aggregation, and inclusion semantics.
- **AC-3:** Missing or unavailable metrics are not treated as passing a filter.
- **AC-4:** Results expose the values responsible for inclusion.
- **AC-5:** Screening output is not presented as an investment recommendation.

## Constraints

- Regional-scale data acquisition and comparable precomputation must be validated before screening is relied upon.
- A fixed composite score is not part of this requirement.

## Non-goals

- Predictive ranking, fair-value estimation, or investment scoring.

## Verification

### Automated

Not established yet.

### Manual or data validation

- Validate that result membership can be reproduced from displayed metric values and context.

### Verification gaps

- AC-1 through AC-5 have no implementation evidence yet.

## Open questions

- [OQ-008: Area-filtered turnover presentation](../open-questions.md#oq-008-area-filtered-turnover-presentation)

## Related documentation

- [Comparison requirement](R-016-apartment-comparison.md)
- [Roadmap M5](../roadmap.md#m5-regional-ingestion-and-screening)

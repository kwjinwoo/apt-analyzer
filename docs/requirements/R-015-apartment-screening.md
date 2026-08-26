---
id: R-015
title: Metric-based apartment screening
status: accepted
priority: P1
created: 2026-08-21
updated: 2026-08-26
origin: "Initial requirements R13"
supersedes: []
superseded_by: null
related_requirements: [R-007, R-008, R-010, R-011, R-016, R-019]
related_decisions: [ADR-0006]
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

- [`test_screening_computes_all_metrics_with_common_area_and_household_context`](../../tests/test_m5.py)
  covers AC-1, AC-2, and AC-4 for all six supported metrics under one common context.
- [`test_screening_validates_units_methods_and_ne_unavailable`](../../tests/test_m5.py)
  and [`test_screening_distinguishes_valid_empty_from_incomplete_coverage`](../../tests/test_m5.py)
  cover AC-1 and AC-3, including the rule that an unavailable metric cannot pass `ne`.
- [`test_real_m5_cli_json_and_text_are_equivalent`](../../tests/test_m5.py) covers
  equivalent reproducible output and the AC-5 historical-screening disclaimer.
- Regional cache, ingestion bounds, schema migration, and indexed requested-period
  evidence are covered by the other representative M5 acceptance tests in that module.

### Manual or data validation

- Validate that result membership can be reproduced from displayed metric values and context.

### Verification gaps

- Automated fixtures cover AC-1 through AC-5. Multi-region real-source membership remains
  a manual data-validation activity because deterministic tests do not call external APIs.

## Open questions

- [OQ-008: Area-filtered turnover presentation](../open-questions.md#oq-008-area-filtered-turnover-presentation)

## Related documentation

- [Comparison requirement](R-016-apartment-comparison.md)
- [Roadmap M5](../roadmap.md#m5-regional-ingestion-and-screening)

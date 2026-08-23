---
id: R-008
title: Multi-year turnover rate
status: accepted
priority: P0
created: 2026-08-21
updated: 2026-08-21
origin: "Initial requirements R8"
supersedes: []
superseded_by: null
related_requirements: [R-003, R-006, R-009, R-017, R-019]
related_decisions: []
---

# R-008: Multi-year turnover rate

## Intent

Raw transaction counts are strongly affected by complex size. Users need transaction activity normalized by the relevant household population.

## Requirement

The user can obtain a turnover rate for a selected period, defined as annualized eligible transaction count divided by the applicable household count.

## Acceptance criteria

- **AC-1:** Eligible transactions in the selected turnover period are counted consistently.
- **AC-2:** The count is annualized using an explicit duration policy.
- **AC-3:** The annualized count is divided by the applicable household count.
- **AC-4:** The result exposes the period, transaction count, annualization method, household count, area selection, and inclusion policy.
- **AC-5:** An exact turnover percentage is not returned when the required household count is unknown or invalid.

## Constraints

- An area-filtered transaction numerator does not establish an exact area-level turnover rate without an area-specific household denominator.
- Partial-year annualization is not yet defined.

## Non-goals

- Treating turnover as a prediction or investment recommendation.

## Verification

### Automated

- [`test_successful_annual_and_multiyear_turnover_expose_context_and_evidence`](../../tests/test_m2.py) covers successful annualized arithmetic, the explicit annualization method, and denominator context; [`test_metric_period_outside_context_is_unavailable_and_household_source_required`](../../tests/test_m2.py) covers invalid-period, source, and denominator failures.

### Manual or data validation

- Validate household counts and input transaction counts for real complexes.

### Verification gaps

- AC-1 through AC-5 have no implementation evidence yet.

## Open questions

- [OQ-004: Partial-year annualization](../open-questions.md#oq-004-partial-year-annualization)
- [OQ-008: Area-filtered turnover presentation](../open-questions.md#oq-008-area-filtered-turnover-presentation)

## Related documentation

- [Turnover rate](../domain/metrics.md#turnover-rate)
- [Area-filtered analysis](R-006-area-filter.md)

---
id: R-008
title: Multi-year turnover rate
status: accepted
priority: P0
created: 2026-08-21
updated: 2026-09-12
origin: "Initial requirements R8"
supersedes: []
superseded_by: null
related_requirements: [R-003, R-006, R-009, R-017, R-019, R-031]
related_decisions: [ADR-0010, ADR-0017]
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
- **AC-6:** Human presentation identifies turnover as a percentage (`%`) while
  machine results retain the exact ratio.
- **AC-7:** When an explicit K-APT apartment-detail request returns a valid
  positive whole-complex household count, the local workspace persists that
  sourced denominator and can explicitly refresh it. Later analysis may use
  the persisted evidence without contacting the external source.
- **AC-8:** A verified Building HUB snapshot may supply the matching denominator for a selected single-apartment area group.

## Constraints

- An area-filtered transaction numerator does not establish an exact area-level turnover rate without an area-specific household denominator.
- Partial-year annualization remains unresolved; the completed-month defaults in [ADR-0010](../decisions/ADR-0010-completed-month-rolling-analysis.md) avoid that question without defining a general partial-year policy.

## Non-goals

- Treating turnover as a prediction or investment recommendation.
- Implicit external household refresh during analysis or re-analysis.

## Verification

### Automated

- [`test_successful_annual_and_multiyear_turnover_expose_context_and_evidence`](../../tests/test_m2.py) covers successful annualized arithmetic, the explicit annualization method, and denominator context; [`test_metric_period_outside_context_is_unavailable_and_household_source_required`](../../tests/test_m2.py) covers invalid-period, source, and denominator failures.

### Manual or data validation

- Validate household counts and input transaction counts for real complexes.

### Verification gaps

- [`test_selected_kapt_households_are_persisted_and_used_offline_for_percent_metrics`](../../tests/test_web.py) covers selection-time persistence, persisted fallback, percentage presentation, and analysis/re-analysis without acquisition. [`test_explicit_household_refresh_preserves_last_good_evidence_on_failure`](../../tests/test_web.py) covers explicit refresh and last-good-evidence preservation. Legacy calendar-year calculations remain covered by the domain tests above.
- [`test_verified_inventory_derives_floor_group_denominator_and_provenance`](../../tests/test_web.py) covers verified Building HUB area-group derivation, exact aggregation, provenance, and offline preview reuse.

## Open questions

- [OQ-004: Partial-year annualization](../open-questions.md#oq-004-partial-year-annualization)
- [OQ-008: Area-filtered turnover presentation](../open-questions.md#oq-008-area-filtered-turnover-presentation)
- [ADR-0017: Verified exact inventory denominator](../decisions/ADR-0017-area-inventory-turnover-denominator.md)

## Related documentation

- [Turnover rate](../domain/metrics.md#turnover-rate)
- [Area-filtered analysis](R-006-area-filter.md)

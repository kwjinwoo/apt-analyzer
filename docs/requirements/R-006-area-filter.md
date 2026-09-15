---
id: R-006
title: Area-filtered analysis
status: accepted
priority: P0
created: 2026-08-21
updated: 2026-09-12
origin: "Initial requirements R6"
supersedes: []
superseded_by: null
related_requirements: [R-004, R-005, R-008, R-010, R-011, R-019, R-031]
related_decisions: [ADR-0017]
---

# R-006: Area-filtered analysis

## Intent

Apartment areas often represent different market segments. Users need every downstream analysis to use the same selected population.

## Requirement

The user can select all areas or one discovered area group, and the selection is applied consistently to downstream transaction and price analytics.

## Acceptance criteria

- **AC-1:** “All areas” includes every otherwise eligible transaction for the selected complex.
- **AC-2:** Selecting an area group excludes transactions outside that group's classification.
- **AC-3:** Volume, price summaries, retention, and MDD use the same filtered population.
- **AC-4:** The active area selection is visible in the analysis context.
- **AC-5:** Turnover uses a verified same-group inventory denominator when available and remains unavailable otherwise.

## Constraints

- Exact area-level turnover requires a verified household count for the selected area group.

## Non-goals

- Area-level turnover when a verified area-specific denominator is unavailable.

## Verification

### Automated

- [`test_all_area_selection_includes_any_raw_area`](../../tests/test_domain.py) covers the domain contract for AC-1.
- [`test_transaction_volume_uses_explicit_population_without_external_api`](../../tests/test_transaction_volume.py) covers AC-2 and AC-4 for transaction volume.
- [`test_non_volume_metrics_use_same_area_type_and_cancellation_population`](../../tests/test_m2.py) covers AC-2 and AC-3 across summaries and MDD.
- [`test_area_group_turnover_rejects_whole_complex_denominator_scope`](../../tests/test_m2.py) covers AC-5; [`test_verified_inventory_derives_floor_group_denominator_and_provenance`](../../tests/test_web.py) covers the verified single-analysis path.

### Manual or data validation

None.

### Verification gaps

- Verified single-analysis inventory denominator is covered by [R-031](R-031-area-group-inventory-denominator.md); comparison and screening remain open.

## Open questions

- [OQ-008: Area-filtered turnover presentation](../open-questions.md#oq-008-area-filtered-turnover-presentation)

## Related documentation

- [Area-filtered transaction activity](../domain/glossary.md#area-filtered-transaction-activity)
- [Shared metric rules](../domain/metrics.md#shared-rules)

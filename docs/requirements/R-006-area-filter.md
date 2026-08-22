---
id: R-006
title: Area-filtered analysis
status: accepted
priority: P0
created: 2026-08-21
updated: 2026-08-21
origin: "Initial requirements R6"
supersedes: []
superseded_by: null
related_requirements: [R-004, R-005, R-008, R-010, R-011, R-019]
related_decisions: []
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
- **AC-5:** Turnover output does not imply an unsupported area-level denominator.

## Constraints

- Exact area-level turnover requires the household count for the selected area group.

## Non-goals

- Exact area-level turnover before an area-specific household denominator is available.

## Verification

### Automated

Not established yet.

### Manual or data validation

None.

### Verification gaps

- AC-1 through AC-5 have no implementation evidence yet.

## Open questions

- [OQ-008: Area-filtered turnover presentation](../open-questions.md#oq-008-area-filtered-turnover-presentation)

## Related documentation

- [Area-filtered transaction activity](../domain/glossary.md#area-filtered-transaction-activity)
- [Shared metric rules](../domain/metrics.md#shared-rules)

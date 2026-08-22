---
id: R-003
title: Transaction query period
status: accepted
priority: P0
created: 2026-08-21
updated: 2026-08-22
origin: "Initial requirements R3"
supersedes: []
superseded_by: null
related_requirements: [R-002, R-019]
related_decisions: []
---

# R-003: Transaction query period

## Intent

Users need control over the historical evidence acquired and analyzed, while date boundaries must remain reproducible.

## Requirement

The user can specify the start and end dates for transaction retrieval and analysis.

## Acceptance criteria

- **AC-1:** The start and end dates are explicit inputs.
- **AC-2:** Transactions outside the requested interval are not included in the resulting analysis population.
- **AC-3:** Invalid or reversed intervals are rejected rather than silently corrected.
- **AC-4:** The effective date interval is visible in the analysis context.

## Constraints

- Date-boundary inclusion semantics must be consistent across acquisition, filtering, and metrics.

## Non-goals

- A predefined market-cycle classification.

## Verification

### Automated

- [`test_analysis_period_rejects_reversed_boundaries`](../../tests/test_domain.py) covers AC-3.
- [`test_transaction_volume_uses_explicit_population_without_external_api`](../../tests/test_transaction_volume.py) covers AC-1, AC-2, and AC-4 at the domain-analytics boundary.

### Manual or data validation

None.

### Verification gaps

- Retrieval-adapter and user-interface coverage is not established yet.

## Open questions

- [OQ-004: Partial-year annualization](../open-questions.md#oq-004-partial-year-annualization)

## Related documentation

- [Analysis period](../domain/glossary.md#analysis-period)
- [Analysis context requirement](R-019-analysis-context.md)

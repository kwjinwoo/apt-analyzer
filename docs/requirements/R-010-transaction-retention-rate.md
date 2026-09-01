---
id: R-010
title: Transaction retention rate
status: accepted
priority: P0
created: 2026-08-21
updated: 2026-08-30
origin: "Initial requirements R9"
supersedes: []
superseded_by: null
related_requirements: [R-003, R-006, R-017, R-019]
related_decisions: [ADR-0010]
---

# R-010: Transaction retention rate

## Intent

Users need to measure how much transaction activity remained during one market period relative to a selected baseline.

## Requirement

The user can select a baseline period and comparison period and obtain the comparison period's annualized eligible transaction count divided by the baseline period's annualized eligible transaction count.

## Acceptance criteria

- **AC-1:** Baseline and comparison periods are explicit inputs.
- **AC-2:** Eligible transaction counts are annualized consistently for both periods.
- **AC-3:** Both periods use the same apartment, area selection, and inclusion policy.
- **AC-4:** The result exposes both periods and annualized counts.
- **AC-5:** A zero baseline is represented without returning a misleading ordinary percentage.
- **AC-6:** Human presentation identifies retention as a percentage (`%`) while
  machine results retain the exact ratio and its comparison meaning.

## Constraints

- Retention is relative to the selected periods and must not be presented as an intrinsic, context-free property.
- The default period relationship and completed-month eligibility follow [ADR-0010](../decisions/ADR-0010-completed-month-rolling-analysis.md); arbitrary partial-year annualization remains unresolved.

## Non-goals

- Automatically classifying or labeling market-cycle periods; deterministic
  completed-month default selection follows [ADR-0010](../decisions/ADR-0010-completed-month-rolling-analysis.md).

## Verification

### Automated

- [`test_retention_annualizes_differing_complete_period_lengths`](../../tests/test_m2.py) covers successful annualized comparison arithmetic; [`test_turnover_and_retention_make_unsupported_and_zero_baseline_explicit`](../../tests/test_m2.py) covers complete-period and zero-baseline unavailable states.

### Manual or data validation

None.

### Verification gaps

- Single-apartment completed-month retention is exercised through the R-024
  web and rolling-period tests; comparison/screening retain their legacy
  calendar-year behavior.

## Open questions

- [OQ-004: Partial-year annualization](../open-questions.md#oq-004-partial-year-annualization)
- [OQ-005: Zero transaction-retention baseline](../open-questions.md#oq-005-zero-transaction-retention-baseline)

## Related documentation

- [Transaction retention rate](../domain/metrics.md#transaction-retention-rate)
- [Analysis context](R-019-analysis-context.md)

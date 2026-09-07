---
id: R-025
title: Chart period selection
status: superseded
priority: P1
created: 2026-09-01
updated: 2026-09-01
origin: "User-approved chart period workflow"
supersedes: []
superseded_by: R-026
related_requirements: [R-008, R-010, R-011, R-019, R-024]
related_decisions: [ADR-0010, ADR-0011]
---

# R-025: Chart period selection

## Intent

Make deliberate chart-based period overrides reproducible and accessible.

This outcome was superseded by [R-026](R-026-chart-preview.md), which keeps
chart exploration non-mutating and leaves official overrides in the manual editor.

## Requirement

The user can explicitly select whole months from the single-apartment volume chart and apply, cancel, or restore metric periods without changing calculations accidentally.

## Acceptance criteria

- **AC-1:** Selection is opt-in, month-snapped, keyboard-accessible, and visibly summarized.
- **AC-2:** Turnover and retention selections use completed, contiguous calendar windows; retention derives its adjacent baseline. MDD accepts selected months.
- **AC-3:** Apply submits through the existing result editor; invalid or incomplete selections remain unavailable and do not submit. Cancel clears pending state and restore removes only the selected target override.
- **AC-4:** Manual period inputs remain authoritative and no external refresh occurs.

## Constraints

Only exact completed-month rolling overrides are resolved here; arbitrary partial-year annualization remains governed by OQ-004 and ADR-0010.

## Non-goals

- Arbitrary annualization or comparison/screening chart selection.

## Related documentation

- [R-024](R-024-period-driven-analysis.md)

## Verification

### Automated

- [test_analyze_routes_arbitrary_non_jan_twelve_month_turnover_to_rolling](../../tests/test_m2.py)
- [test_analyze_routes_adjacent_non_jan_retention_to_rolling](../../tests/test_m2.py)
- [test_analyze_marks_in_progress_exact_rolling_windows_unavailable](../../tests/test_m2.py)
- The former button-gated browser interaction is no longer current behavior.
  Current chart-preview verification is recorded in [R-026](R-026-chart-preview.md).

### Verification gaps

None.

## Open questions

- [OQ-004: Partial-year annualization](../open-questions.md#oq-004-partial-year-annualization)

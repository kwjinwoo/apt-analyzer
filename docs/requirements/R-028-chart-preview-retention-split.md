---
id: R-028
title: Duration-aware chart preview retention split
status: accepted
priority: P1
created: 2026-09-07
updated: 2026-09-07
origin: "User-approved 24-month chart preview retention interpretation"
supersedes: [R-027]
superseded_by: null
related_requirements: [R-010, R-024, R-027]
related_decisions: [ADR-0010, ADR-0013, ADR-0014]
---

# R-028: Duration-aware chart preview retention split

## Intent

Make a 24-month chart selection a natural year-over-year retention comparison.

## Requirement

The chart preview shall preserve R-027's direct, accessible, persisted-only,
non-mutating preview and duration-aware turnover outcomes, while interpreting
an exact 24-month selection as its first 12 months versus its last 12 months.

## Acceptance criteria

- **AC-1:** Direct dragging of the volume chart is accessible, makes one
  persisted-only preview request on release, shows a responsive selection and
  supports dismissal and stale-response protection.
- **AC-2:** The preview preserves official summary/editor/export state and keeps
  volume and price evidence together in a default-collapsed accessible section.
- **AC-3:** Turnover uses selected-period semantics for 12 months, annual-average
  semantics for exact 12-month multiples, and cumulative non-annualized
  semantics for other valid whole-month lengths, with complete coverage and
  compatible household evidence.
- **AC-4:** A 24-month completed selection uses the first 12 months as baseline
  and last 12 months as comparison, showing both periods and counts.
- **AC-5:** A 12-month selection remains comparison against the immediately
  preceding 12-month baseline; all other lengths leave retention unavailable.
- **AC-6:** Both windows are contiguous, complete, inside the official context,
  and use identical population and coverage rules; zero baseline is unavailable.
- **AC-7:** MDD and volume preview behavior, touch scrolling, Korean unavailable
  reasons, and persisted-only non-mutating calculation remain unchanged.

## Constraints

No arbitrary equal-halves or annualization is introduced. OQ-005 remains the
zero-baseline policy reference.

## Non-goals

Retention for lengths other than 12 or 24 months, and changes to official
analysis, export, turnover, MDD, or acquisition.

## Verification

### Automated

- [`test_analysis_preview_splits_24_month_retention_into_baseline_and_comparison`](../../tests/test_web.py) — AC-4.
- [`test_analysis_preview_uses_offline_context_without_mutating_official_result`](../../tests/test_web.py) and [`test_chart_drag_previews_metrics_without_mutating_official_analysis`](../../tests/test_web_e2e.py) — AC-1 through AC-3 and AC-5 through AC-7.

### Manual or data validation

None.

### Verification gaps

None.

## Open questions

- [OQ-005: Zero-transaction retention baseline](../open-questions.md#oq-005-zero-transaction-retention-baseline)

## Related documentation

- [R-027](R-027-chart-preview-turnover.md)
- [ADR-0014](../decisions/ADR-0014-chart-preview-retention-split.md)

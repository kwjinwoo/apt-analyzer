---
id: R-026
title: Non-mutating chart period preview
status: superseded
priority: P1
created: 2026-09-03
updated: 2026-09-03
origin: "User-approved direct chart preview workflow"
supersedes: [R-025]
superseded_by: R-027
related_requirements: [R-019, R-024]
related_decisions: [ADR-0010, ADR-0012]
---

# R-026: Non-mutating chart period preview

This requirement is retained for history. [R-027](R-027-chart-preview-turnover.md)
supersedes its turnover-duration restriction.

## Intent

Allow users to inspect a selected monthly range without changing the official analysis.

## Requirement

Dragging the monthly volume chart presents a server-computed, accessible preview of the selected range while preserving the official result, editor, and export. Duration-aware turnover semantics are defined by [R-027](R-027-chart-preview-turnover.md).

## Acceptance criteria

- **AC-1:** The monthly volume chart accepts direct whole-month dragging without
  selection-mode, target, apply, cancel, or restore controls. During movement it
  shows the inclusive band, period, and month count; release makes exactly one
  preview request and movement makes none.
- **AC-2:** Any valid selected range reports eligible transaction volume and MDD,
  including units and peak-to-trough evidence or a clear Korean unavailable reason.
- **AC-3:** Turnover is available only for exactly 12 consecutive completed months
  with compatible household and coverage evidence. Retention compares that exact
  selection with the immediately preceding 12 months when both lie within the
  official overall context and have complete coverage. Other ranges remain
  explicitly unavailable without annualization.
- **AC-4:** Preview calculation uses only the persisted evidence and population
  policy of the current official analysis and performs no external refresh.
- **AC-5:** Preview does not mutate the official summary, advanced editor,
  application result, or analysis export. Escape and outside click clear it; a
  new drag replaces it, and stale responses cannot overwrite the new selection.
- **AC-6:** Raw monthly volume and price evidence remain accessible together
  inside one default-collapsed section, independently of the collapsed
  three-month moving-average table.
- **AC-7:** The preview card and selection remain usable without horizontal
  overflow at 390 CSS pixels, while touch interaction preserves vertical page
  scrolling.

## Constraints

Exact 12 completed months are required for turnover and the retention comparison
window. Retention additionally requires the adjacent prior 12 months inside the
overall interval. No external refresh or arbitrary annualization occurs.

## Non-goals

Price-chart selection, comparison/screening interaction, and official period override through dragging.

## Verification

### Automated

- [`test_analysis_preview_uses_offline_context_without_mutating_official_result`](../../tests/test_web.py)
  covers persisted-only metric values, population filtering, evidence, and export
  immutability for AC-2 through AC-5.
- [`test_analysis_preview_uses_cumulative_turnover_and_unavailable_retention`](../../tests/test_web.py)
  and [`test_analysis_preview_rejects_non_month_boundaries_and_outside_period`](../../tests/test_web.py)
  cover range validity and unavailable semantics for AC-2 and AC-3.
- [Direct-preview range helper tests](../../frontend/src/main.test.ts) cover
  reverse drags, inclusive month counts, and whole-month request boundaries for AC-1.
- [`test_chart_drag_previews_metrics_without_mutating_official_analysis`](../../tests/test_web_e2e.py)
  covers real mouse dragging, one release request, metric presentation, official
  result immutability, dismissal, combined evidence disclosure, and 390-pixel
  layout for AC-1 and AC-5 through AC-7.

### Manual or data validation

None.

### Verification gaps

None.

## Open questions

- [OQ-004: Partial-year annualization](../open-questions.md#oq-004-partial-year-annualization)

## Related documentation

- [R-019](R-019-analysis-context.md)
- [ADR-0012](../decisions/ADR-0012-direct-chart-preview.md)

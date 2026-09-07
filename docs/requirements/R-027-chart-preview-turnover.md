---
id: R-027
title: Duration-aware chart preview turnover
status: superseded
priority: P1
created: 2026-09-03
updated: 2026-09-03
origin: "User-approved duration-aware chart preview"
supersedes: [R-026]
superseded_by: R-028
related_requirements: [R-008, R-019, R-024, R-026]
related_decisions: [ADR-0010, ADR-0012, ADR-0013]
---

# R-027: Duration-aware chart preview turnover

This requirement is retained for history; [R-028](R-028-chart-preview-retention-split.md)
supersedes it for chart-preview retention interpretation.

## Intent

Make non-mutating chart previews useful for complete whole-month selections of
different lengths without changing official analysis semantics.

## Requirement

The chart preview shall calculate selected-period turnover according to its
whole-month duration while preserving persisted-evidence, household, coverage,
and non-mutating preview boundaries.

## Acceptance criteria

- **AC-1:** The monthly volume chart directly accepts accessible whole-month
  dragging, shows a persistent selection band and summary, requests one
  persisted-evidence-only preview on release, and supports dismissal, stale
  response protection, touch scrolling, and responsive layout.
- **AC-2:** Raw monthly volume and price evidence remain together in a
  default-collapsed accessible section, while the official metric summary,
  editor, and export remain unchanged by preview.
- **AC-3:** Exactly 12 completed months show selected-period turnover; an exact
  multiple of 12 months shows eligible transactions divided by years and the
  applicable households as an explicitly labelled annual average.
- **AC-4:** Other valid completed whole-month lengths show cumulative eligible
  transactions divided by applicable households, explicitly labelled cumulative
  and never annualized.
- **AC-5:** Missing or invalid household evidence, incomplete coverage, invalid
  boundaries, and selections outside the overall context remain unavailable
  with clear reasons; retention and MDD semantics remain unchanged.
- **AC-6:** Preview uses persisted evidence only and does not mutate official
  result, editor, or export state.

## Constraints

Official analysis retains its existing metric policies. Arbitrary partial-year
annualization remains unresolved under OQ-004; cumulative preview values are
not annualized.

## Non-goals

Changing retention, MDD, official analysis, export, acquisition, or external
refresh behavior.

## Verification

### Automated

- [`test_analysis_preview_uses_annual_average_for_complete_24_month_selection`](../../tests/test_web.py) — AC-3.
- [`test_analysis_preview_uses_cumulative_turnover_and_unavailable_retention`](../../tests/test_web.py) — AC-4 and retention part of AC-5.
- [`test_analysis_preview_rejects_incompatible_household_scope_for_duration`](../../tests/test_web.py), [`test_analysis_preview_preserves_coverage_and_completion_reasons`](../../tests/test_web.py), and [`test_analysis_preview_rejects_non_month_boundaries_and_outside_period`](../../tests/test_web.py) — AC-5.
- [Direct-preview range helper tests](../../frontend/src/main.test.ts) and [`test_chart_drag_previews_metrics_without_mutating_official_analysis`](../../tests/test_web_e2e.py) — AC-1.
- [`test_analysis_preview_uses_offline_context_without_mutating_official_result`](../../tests/test_web.py) and the same E2E test — AC-2 and AC-6.

### Manual or data validation

None.

### Verification gaps

None.

## Open questions

- [OQ-004: Partial-year annualization](../open-questions.md#oq-004-partial-year-annualization)

## Related documentation

- [R-026](R-026-chart-preview.md)
- [Metric definitions](../domain/metrics.md)
- [ADR-0013](../decisions/ADR-0013-duration-aware-chart-preview-turnover.md)

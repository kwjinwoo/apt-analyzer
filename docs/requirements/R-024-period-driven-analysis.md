---
id: R-024
title: Period-driven analysis and completed-month rolling metrics
status: accepted
priority: P0
created: 2026-08-30
updated: 2026-08-31
origin: "User-approved period-driven analysis UX"
supersedes: []
superseded_by: null
related_requirements: [R-003, R-007, R-008, R-010, R-011, R-013, R-014, R-019, R-020]
related_decisions: [ADR-0010]
---

# R-024: Period-driven analysis and completed-month rolling metrics

## Intent

Users need a simpler analysis workflow centered on one explicit overall period,
while still being able to reproduce metric-specific choices and inspect monthly
evidence without mistaking partial or missing data for observations.

## Requirement

The analysis workspace lets the user submit an overall period, derives visible
completed-month metric periods and monthly evidence from persisted data, and
allows period adjustment and advanced overrides while preserving reproducible
effective periods, methods, coverage states, and analysis context.

## Acceptance criteria

- **AC-1:** The initial analysis input centers on explicit overall start and end
  dates. Area, transaction inclusion, household, and metric-specific overrides
  remain available as advanced controls.
- **AC-2:** Monthly eligible transaction counts and observed monthly median
  prices use the overall analysis interval. Price gaps remain gaps; no
  interpolation is introduced.
- **AC-3:** For each eligible completed chart month, a trailing three-complete-
  month arithmetic mean of monthly eligible transaction counts uses that month
  and the two immediately preceding consecutive completed months. It is a
  supporting time series, not a replacement for monthly observations or a
  normalized liquidity metric. All three months must be wholly contained in
  the overall interval. A valid-empty member contributes zero; missing, failed,
  or incomplete coverage makes that point a gap.
- **AC-4:** The automatic rolling anchor is the latest calendar month whose
  calendar boundaries are wholly contained in the overall interval. It is not
  selected by searching backward for usable coverage. An in-progress boundary
  month may appear in monthly charts/tables with an explicit partial or
  incomplete interpretation, but is excluded from rolling windows.
- **AC-5:** Default turnover uses the 12 consecutive completed calendar months
  ending at that anchor, with the entire span wholly contained in the overall
  interval, and the applicable household denominator. Every month in that span
  must have successful or valid-empty coverage; any missing, failed, or
  incomplete month makes it unavailable. Missing, invalid,
  source-less, or wrong-scope household evidence also makes it unavailable.
- **AC-6:** Default retention compares that 12-month window with the immediately
  preceding 12 consecutive, non-overlapping completed calendar months under
  identical population and inclusion semantics. The full 24-month span must be
  wholly contained in the overall interval and every month must have successful
  or valid-empty coverage; any missing, failed, or incomplete month makes it
  unavailable. A zero baseline is unavailable.
- **AC-7:** Fewer than 12 qualifying completed months makes default turnover
  unavailable; fewer than 24 makes default retention unavailable. The system
  does not stretch, interpolate, or silently annualize a shorter interval.
- **AC-8:** The results panel accepts an edited overall period and advanced
  metric-specific overrides. Resubmission recalculates metrics and charts;
  explicit overrides take precedence, remain subject to the authoritative
  metric validity rules, and may produce explicit unavailable results. Visible
  effective periods and methods identify the result; overrides do not promise
  arbitrary partial-year annualization.
- **AC-9:** Initial analysis and period re-analysis use persisted evidence only
  and never implicitly call external APIs. Missing coverage remains visible and
  directs the user to the separate update workflow.
- **AC-10:** Human-readable and machine-readable results expose the overall
  period, derived or overridden effective periods, derivation method,
  coverage/partial states, area and inclusion policy, and applicable household
  evidence.

## Constraints

- Rolling defaults use exact completed calendar-month windows; this requirement
  does not resolve arbitrary partial-year annualization in [OQ-004](../open-questions.md#oq-004-partial-year-annualization).
- Rolling turnover still requires a valid applicable household denominator, and
  area-filtered activity does not create an area-level denominator.
- Monthly price gaps remain unobserved and must not be filled by interpolation
  or carry-forward.
- The local single-user SQLite boundary and separate explicit evidence-update
  workflow remain unchanged.

## Non-goals

- Arbitrary partial-year annualization, day-count annualization, or market-cycle
  detection/classification.
- Implicit external refresh during analysis or re-analysis, recommendations,
  or investment interpretation. Household evidence may be acquired by an
  explicit K-APT refresh or reused from an already-required explicit apartment
  detail request under [R-008](R-008-turnover-rate.md).

## Verification

### Automated

- [`test_completed_month_periods_use_fixed_today_and_overall_boundaries`](../../tests/test_m2.py) covers the injectable calendar anchor and default 12-month period derivation.
- [`test_analysis_renders_korean_reproducible_context`](../../tests/test_web.py), [`test_result_editor_round_trips_advanced_context_and_overrides`](../../tests/test_web.py), and [`test_rolling_export_uses_fixed_completed_months_and_keeps_partial_month_evidence`](../../tests/test_web.py) cover persisted-only analysis, result-editor state preservation, the fixed-date 12/24-month export contract, and partial-month state separation.
- [`test_monthly_transaction_trend_preserves_consecutive_gap`](../../tests/test_m2.py), [`test_rolling_public_calculations_reject_non_calendar_windows`](../../tests/test_m2.py), and [`test_rolling_defaults_are_independent_of_metric_overrides`](../../tests/test_m2.py) cover gap propagation, rolling-window validity, and independent override precedence.
- Frontend chart-series tests cover monthly null gaps and the supporting three-month trend dataset. [`test_browser_workspace_full_deterministic_flow`](../../tests/test_web_e2e.py) covers browser re-analysis and advanced-setting preservation.

### Manual or data validation

None.

### Verification gaps

- Household scope/source failures and zero-baseline retention retain their
  existing domain-test evidence; household evidence persistence and fallback
  are covered by the selection/persistence tests.
- Existing comparison, screening, and CLI paths continue to use their prior
  complete-calendar-year behavior; this requirement changes only the single-
  apartment analysis path.

## Open questions

- [OQ-004: Partial-year annualization](../open-questions.md#oq-004-partial-year-annualization)

## Related documentation

- [R-008: Multi-year turnover rate](R-008-turnover-rate.md)
- [R-007: Periodic transaction aggregation](R-007-periodic-aggregation.md)
- [R-010: Transaction retention rate](R-010-transaction-retention-rate.md)
- [R-019: Visible analysis context](R-019-analysis-context.md)
- [R-020: Local browser analysis workspace](R-020-local-browser-analysis-workspace.md)
- [ADR-0010: Completed-month rolling analysis](../decisions/ADR-0010-completed-month-rolling-analysis.md)

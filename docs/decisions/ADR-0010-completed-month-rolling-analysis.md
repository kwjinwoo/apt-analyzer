---
id: ADR-0010
title: Completed-month rolling analysis
status: accepted
date: 2026-08-30
supersedes: []
superseded_by: null
related_requirements: [R-008, R-010, R-019, R-020, R-024]
---

# ADR-0010: Completed-month rolling analysis

## Status

Accepted

## Context

The analysis workspace currently exposes metric-specific periods and uses
complete-calendar-year behavior with fallback period logic. A simpler workflow
needs one overall period, monthly evidence, and reproducible defaults that do
not imply unsupported annualization for partial or in-progress periods.

## Decision

Center initial analysis on explicit overall start and end dates while retaining
area, inclusion, household, and metric-specific overrides as advanced controls.
Use the selected interval for monthly eligible counts and observed monthly
median prices, preserving gaps. Show a trailing three-complete-month arithmetic
mean as a supporting trend time series only: each completed chart month uses
that month and its two immediately preceding consecutive completed months,
with all three wholly contained in the overall interval; missing, failed, or
incomplete members produce a gap.

Anchor automatic windows to the latest calendar month whose calendar boundaries
are wholly contained in the overall interval, regardless of whether its
coverage is usable. The default turnover window is the 12 consecutive calendar
months ending at that anchor, with the entire span wholly contained in the
overall interval, with the applicable household denominator. The
default retention window compares that window with the immediately preceding
12 consecutive, non-overlapping calendar months using identical population and
inclusion semantics. The full 24-month span must also be wholly contained in
the overall interval. Every month in the required span must have successful or
valid-empty coverage; any missing, failed, or incomplete month makes that
default unavailable rather than causing an earlier month to be selected.
Fewer than 12 calendar months makes turnover unavailable; fewer than 24 makes
retention unavailable. In-progress months may be displayed with an explicit
partial/incomplete state but never enter automatic rolling windows. Explicit
overrides take precedence, remain subject to authoritative metric validity
rules, may be unavailable, and their effective periods and derivation methods
travel with the result; they do not establish arbitrary partial-year
annualization.

Analysis and period re-analysis consume persisted evidence only. Missing
coverage remains visible and sends the user to the separate update workflow.

## Rationale

Completed-month windows avoid arbitrary day-count annualization, prevent
partial boundary months from distorting defaults, and make the latest available
trend comparable across complexes. Visible derivation metadata preserves
reproducibility when defaults or overrides are used.

## Alternatives considered

### All metrics use the overall period

Rejected because it hides incompatible metric durations and makes turnover and
retention interpretation depend on arbitrary user boundaries.

### One-month turnover or retention defaults

Rejected because one month is noisy and retention requires a meaningful,
non-overlapping baseline.

### Arbitrary day-count annualization

Rejected because partial-year conventions remain unresolved and can imply false
precision.

### Hidden automatic periods or display-only chart clipping

Rejected because users must be able to reproduce the actual calculation; period
changes must recalculate metrics, not only alter the visible chart range.

### Implicit external refresh

Rejected because analysis must remain deterministic and separate from explicit
evidence acquisition.

## Consequences

### Positive

- The common path has a simple overall-period input while advanced controls remain available.
- Monthly gaps and coverage states remain visible and rolling metrics have explicit support requirements.

### Negative

- Retention needs up to 24 completed months before a default value is available.
- Excluding the in-progress month introduces a lag in the latest rolling result.
- Monthly sparsity and noise remain visible and can make short-term trends unstable.
- Implementation must migrate from current complete-calendar-year behavior and
  `_form_period` fallback semantics.

### Follow-up

- Validate rolling-window results and migration behavior with deterministic
  persisted-evidence tests before claiming implementation coverage.
- Revisit aliasing or labeling of partial-year annualization only when OQ-004 is
  explicitly resolved; this decision avoids that question for defaults but does
  not resolve it generally.

## Related documentation

- [R-008: Multi-year turnover rate](../requirements/R-008-turnover-rate.md)
- [R-010: Transaction retention rate](../requirements/R-010-transaction-retention-rate.md)
- [R-019: Visible analysis context](../requirements/R-019-analysis-context.md)
- [R-020: Local browser analysis workspace](../requirements/R-020-local-browser-analysis-workspace.md)
- [R-024: Period-driven analysis and completed-month rolling metrics](../requirements/R-024-period-driven-analysis.md)
- [OQ-004: Partial-year annualization](../open-questions.md#oq-004-partial-year-annualization)

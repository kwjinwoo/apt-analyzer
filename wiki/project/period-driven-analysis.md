---
title: Period-Driven Analysis
type: project
role: topic
status: active
updated: 2026-08-31
aliases:
  - Completed-month rolling analysis
  - Simple analysis period UX
tags:
  - analysis-context
  - rolling-metrics
  - accepted
---

# Period-Driven Analysis

## Scope

This page maps the accepted R-024/ADR-0010 contract for a simple overall-period
analysis workflow and completed-calendar-month rolling metrics.

## Knowledge

The accepted contract centers the initial UI on explicit overall dates while
retaining advanced controls. Monthly eligible counts and observed median prices
use that interval and preserve gaps. The anchor is the latest calendar month
whose boundaries are wholly contained in the interval, not a backward search
for usable coverage. Turnover uses the 12 consecutive calendar months ending
there; retention uses those 12 plus the preceding non-overlapping 12. Every
required month needs successful or valid-empty coverage, so any missing,
failed, or incomplete month makes the default unavailable. For each completed
chart month, a three-month arithmetic count mean uses that month and the two
immediately preceding consecutive months, all wholly inside the overall
interval, as a supporting time series only.
Overrides follow metric validity rules and may be unavailable; no implicit
refresh or interpolation occurs. Explicit K-APT detail selection or household
refresh can persist a whole-complex denominator for later offline turnover;
area-filtered analysis does not silently reuse that complex-wide denominator.

The single-apartment analysis path now derives the completed-month defaults and
exports the selected context; comparison, screening, and legacy CLI paths still
expose their prior `complete-calendar-year-average` behavior. The web retains
`_form_period` for explicit metric overrides and unaffected flows.

## Graph connections

- Defines period semantics for [Analysis context](../domain/analysis-context.md).
- Extends [Turnover rate](../metrics/turnover-rate.md) and [Transaction retention rate](../metrics/transaction-retention-rate.md).
- Preserves monthly gaps relevant to [Price-series evidence](../data/price-series-evidence.md) and [Maximum drawdown](../metrics/maximum-drawdown.md).
- Is delivered through the local workspace boundary in [R-020](../../docs/requirements/R-020-local-browser-analysis-workspace.md).

## Requirements

- [R-024: Period-driven analysis and completed-month rolling metrics](../../docs/requirements/R-024-period-driven-analysis.md) — accepted; representative implementation evidence is in [`test_m2.py`](../../tests/test_m2.py), [`test_web.py`](../../tests/test_web.py), and [`test_web_e2e.py`](../../tests/test_web_e2e.py).
- [R-008: Multi-year turnover rate](../../docs/requirements/R-008-turnover-rate.md)
- [R-010: Transaction retention rate](../../docs/requirements/R-010-transaction-retention-rate.md)

## Decisions and open questions

- [ADR-0010: Completed-month rolling analysis](../../docs/decisions/ADR-0010-completed-month-rolling-analysis.md) is accepted.
- [OQ-004: Partial-year annualization](../../docs/open-questions.md#oq-004-partial-year-annualization) remains unresolved; ADR-0010 avoids it only for defaults.

## Evidence and interpretation risks

- Persisted household evidence can become stale; its source and fetch time must remain visible, and explicit refresh failure must preserve the last valid value.
- Excluding the in-progress month creates a visible lag in the latest default window.
- Monthly sparsity and noise remain interpretation limits; supporting trends are not normalized liquidity metrics.

## Verify in the repository

[`analytics.py`](../../src/apt_analyzer/analytics.py) provides the injectable
completed-month derivation and rolling metric helpers. [`web/__init__.py`](../../src/apt_analyzer/web/__init__.py)
passes the local analysis clock and emits trend/export context for the single-
apartment flow. [`test_m2.py`](../../tests/test_m2.py) and [`test_web.py`](../../tests/test_web.py)
are representative evidence; [`test_web_e2e.py`](../../tests/test_web_e2e.py)
covers period re-analysis and the default-collapsed supporting trend table.

## Related pages

- [Analysis context](../domain/analysis-context.md)
- [Turnover rate](../metrics/turnover-rate.md)
- [Transaction retention rate](../metrics/transaction-retention-rate.md)
- [Price-series evidence](../data/price-series-evidence.md)
- [Maximum drawdown](../metrics/maximum-drawdown.md)

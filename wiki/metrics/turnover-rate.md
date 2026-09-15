---
title: Turnover Rate
type: metric
role: topic
status: active
updated: 2026-09-12
aliases:
  - Apartment turnover
tags:
  - liquidity
  - household-normalization
---

# Turnover Rate

## Scope

Turnover rate connects eligible transaction activity with the household population used as its denominator.

## Knowledge

The normative definition is maintained in [Metric definitions](../../docs/domain/metrics.md#turnover-rate). The important graph relationship is that the numerator, duration policy, and denominator scope must describe compatible populations.

Whole-complex turnover can normalize transactions by total households. If transactions are filtered to an area group while only total households are known, the result is area-filtered activity against a whole-complex denominator. A verified Building HUB snapshot can provide an exact matching denominator for a single-apartment analysis under [R-031](../../docs/requirements/R-031-area-group-inventory-denominator.md).

Annualization makes periods comparable only when boundary and duration semantics are explicit. Complete calendar-year turnover is simpler than arbitrary-date or partial-year turnover, which remains unresolved.

The accepted [ADR-0010](../../docs/decisions/ADR-0010-completed-month-rolling-analysis.md) defines the single-analysis default anchored by calendar boundaries at the latest fully contained month, using the 12 consecutive calendar months ending there, with that entire span wholly inside the overall interval, and a valid applicable household denominator. Every month needs successful or valid-empty coverage; any gap makes the default unavailable rather than selecting an earlier month. Whole-complex K-APT household evidence can be persisted during explicit apartment-detail selection or refresh and reused by offline analysis; it is not borrowed for an area-filtered numerator.

The superseded R-026 chart preview is replaced by [R-027](../../docs/requirements/R-027-chart-preview-turnover.md),
uses selected-period turnover for 12 months, an explicitly labelled annual
average for exact 12-month multiples, and cumulative (not annualized) turnover
for other valid whole-month lengths. The preview remains separate from the
official result; [ADR-0013](../../docs/decisions/ADR-0013-duration-aware-chart-preview-turnover.md)
records this extension.

## Graph connections

- Uses eligible counts from [Transaction population](../data/transaction-population.md).
- Receives period, area, and denominator scope from [Analysis context](../domain/analysis-context.md).
- Is constrained by [Area group](../domain/area-group.md).
- Depends on household evidence attached to [Apartment identity](../domain/apartment-identity.md).
- Complements relative activity measured by [Transaction retention rate](transaction-retention-rate.md).

## Requirements

- [R-008: Multi-year turnover rate](../../docs/requirements/R-008-turnover-rate.md)
- [R-009: Annual turnover rate](../../docs/requirements/R-009-annual-turnover-rate.md)
- [R-019: Visible analysis context](../../docs/requirements/R-019-analysis-context.md)
- [R-024: Period-driven analysis and completed-month rolling metrics](../../docs/requirements/R-024-period-driven-analysis.md)
- [R-026: Non-mutating chart period preview](../../docs/requirements/R-026-chart-preview.md)
- [R-027: Duration-aware chart preview turnover](../../docs/requirements/R-027-chart-preview-turnover.md)

## Decisions and open questions

- [OQ-004: Partial-year annualization](../../docs/open-questions.md#oq-004-partial-year-annualization)
- [OQ-008: Area-filtered turnover presentation](../../docs/open-questions.md#oq-008-area-filtered-turnover-presentation)
- [ADR-0017](../../docs/decisions/ADR-0017-area-inventory-turnover-denominator.md) resolves the single-analysis area denominator; comparison and screening remain outside its scope. OQ-004 remains unresolved for arbitrary partial-year annualization.
- [ADR-0010](../../docs/decisions/ADR-0010-completed-month-rolling-analysis.md) is accepted for completed-month defaults; OQ-004 remains unresolved generally.

## Evidence and interpretation risks

- An incorrect household count creates a precise but invalid rate.
- Household-count scope can change across sources or over time.
- Area filtering can invite an unsupported area-level interpretation.
- Short or partial periods can exaggerate annualized activity.
- Cancellation and transaction-type policies change the numerator.

## Verify in the repository

[`turnover`](../../src/apt_analyzer/analytics.py) retains the explicit `complete-calendar-year-average` path for legacy flows. Single-apartment web analysis uses completed-month rolling defaults and can use a persisted verified Building HUB group denominator. Representative evidence is in [`test_m2.py`](../../tests/test_m2.py) and [`test_web.py`](../../tests/test_web.py); latest-query evidence is not historical as-of inventory.
An exact 12-month completed-month preview uses the rolling method; exact
multi-year selections use the preview annual-average method and other whole
month selections use the preview cumulative method;
representative endpoint and browser regressions are named in
[R-027](../../docs/requirements/R-027-chart-preview-turnover.md).

## Related pages

- [Transaction retention rate](transaction-retention-rate.md)
- [Analysis context](../domain/analysis-context.md)
- [Transaction quality](../data/transaction-quality.md)
- [Open decision map](../project/open-decision-map.md)

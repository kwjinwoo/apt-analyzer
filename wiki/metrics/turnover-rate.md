---
title: Turnover Rate
type: metric
role: topic
status: active
updated: 2026-08-31
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

Whole-complex turnover can normalize transactions by total households. If transactions are filtered to an area group while only total households are known, the result is area-filtered activity against a whole-complex denominator, not an exact area-level turnover rate.

Annualization makes periods comparable only when boundary and duration semantics are explicit. Complete calendar-year turnover is simpler than arbitrary-date or partial-year turnover, which remains unresolved.

The accepted [ADR-0010](../../docs/decisions/ADR-0010-completed-month-rolling-analysis.md) defines the single-analysis default anchored by calendar boundaries at the latest fully contained month, using the 12 consecutive calendar months ending there, with that entire span wholly inside the overall interval, and a valid applicable household denominator. Every month needs successful or valid-empty coverage; any gap makes the default unavailable rather than selecting an earlier month. Whole-complex K-APT household evidence can be persisted during explicit apartment-detail selection or refresh and reused by offline analysis; it is not borrowed for an area-filtered numerator.

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

## Decisions and open questions

- [OQ-004: Partial-year annualization](../../docs/open-questions.md#oq-004-partial-year-annualization)
- [OQ-008: Area-filtered turnover presentation](../../docs/open-questions.md#oq-008-area-filtered-turnover-presentation)
- No separate ADR has resolved area-filter presentation; OQ-004 remains unresolved for arbitrary partial-year annualization.
- [ADR-0010](../../docs/decisions/ADR-0010-completed-month-rolling-analysis.md) is accepted for completed-month defaults; OQ-004 remains unresolved generally.

## Evidence and interpretation risks

- An incorrect household count creates a precise but invalid rate.
- Household-count scope can change across sources or over time.
- Area filtering can invite an unsupported area-level interpretation.
- Short or partial periods can exaggerate annualized activity.
- Cancellation and transaction-type policies change the numerator.

## Verify in the repository

[`turnover`](../../src/apt_analyzer/analytics.py) retains the explicit `complete-calendar-year-average` path for legacy flows. Single-apartment web analysis uses completed-month rolling defaults and can use persisted K-APT whole-complex household evidence. Representative evidence is in [`test_m2.py`](../../tests/test_m2.py) and [`test_web.py`](../../tests/test_web.py); area-specific denominator policy remains unresolved.

## Related pages

- [Transaction retention rate](transaction-retention-rate.md)
- [Analysis context](../domain/analysis-context.md)
- [Transaction quality](../data/transaction-quality.md)
- [Open decision map](../project/open-decision-map.md)

---
title: MVP Knowledge Map
type: project
role: topic
status: active
updated: 2026-08-22
aliases:
  - MVP dependency map
tags:
  - mvp
  - dependency-map
---

# MVP Knowledge Map

## Scope

This hub connects the knowledge dependencies required for the first end-to-end apartment liquidity and price-resilience analysis.

## Knowledge

The initial product outcome is not a collection of independent formulas. Reliable comparison depends on a chain from source identity and quality through a shared population and visible context to interpreted metrics.

```text
Apartment search and source records
        ↓
Apartment identity
        ↓
Normalized, traceable transactions
        ↓
Area grouping and transaction population
        ↓
Visible analysis context
        ├── Transaction volume and price summary
        ├── Turnover rate
        ├── Transaction retention rate
        └── Maximum drawdown and its interval
                ↓
Comparable apartment results
```

The dependency order explains why product UI is deferred until data and metric semantics can be validated independently.

## Graph connections

- Starts with [Apartment identity](../domain/apartment-identity.md) and [Transaction quality](../data/transaction-quality.md).
- Defines populations through [Area group](../domain/area-group.md) and [Transaction population](../data/transaction-population.md).
- Preserves interpretation through [Analysis context](../domain/analysis-context.md).
- Produces [Turnover rate](../metrics/turnover-rate.md), [Transaction retention rate](../metrics/transaction-retention-rate.md), and [Maximum drawdown](../metrics/maximum-drawdown.md).
- Is constrained by unresolved dependencies in the [Open decision map](open-decision-map.md).

## Requirements

- See the [Requirement map](requirement-map.md) for the complete relationship among R-001 through R-019.
- The end-to-end comparison outcome is defined by [R-016](../../docs/requirements/R-016-apartment-comparison.md).
- Reproducibility across the flow is defined by [R-019](../../docs/requirements/R-019-analysis-context.md).

## Decisions and open questions

- [ADR-0001: Documentation as context and navigation](../../docs/decisions/ADR-0001-documentation-policy.md)
- See the [Open decision map](open-decision-map.md) for unresolved domain and metric policies.

## Evidence and interpretation risks

- A valid metric can still be meaningless if identity, population, or context is wrong.
- Comparison magnifies inconsistencies because one hidden difference can favor one subject.
- Downstream UI convenience must not silently redefine upstream policy.
- Persistence and caching can preserve stale or misidentified evidence if source freshness is hidden.

## Verify in the repository

Initial foundation evidence exists in the source-independent values in [`domain.py`](../../src/apt_analyzer/domain.py) and the pure transaction-volume boundary in [`analytics.py`](../../src/apt_analyzer/analytics.py). Representative tests are in [`test_domain.py`](../../tests/test_domain.py) and [`test_transaction_volume.py`](../../tests/test_transaction_volume.py). Acquisition, identity resolution, normalization adapters, the remaining metrics, and an end-to-end acceptance path remain unimplemented.

## Related pages

- [Requirement map](requirement-map.md)
- [Open decision map](open-decision-map.md)
- [Analysis context](../domain/analysis-context.md)
- [Transaction population](../data/transaction-population.md)

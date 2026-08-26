---
title: MVP Knowledge Map
type: project
role: topic
status: active
updated: 2026-08-26
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
SQLite coverage and freshness
        ↓
Comparable apartment results
        ↓
Local browser workspace (M4)
        ↓
Bounded regional ingestion and screening (M5)
```

The dependency order explains why the browser workspace consumes validated data and
metric semantics rather than redefining them. The local-web workspace now provides
search/explicit selection, SQLite update, analysis, and deterministic result export
routes around the existing M1-M3 boundaries. M5 reuses the same context and metrics for
explicitly scoped regional evidence and excludes unavailable values from filters.

## Graph connections

- Starts with [Apartment identity](../domain/apartment-identity.md) and [Transaction quality](../data/transaction-quality.md).
- Defines populations through [Area group](../domain/area-group.md) and [Transaction population](../data/transaction-population.md).
- Preserves interpretation through [Analysis context](../domain/analysis-context.md).
- Produces [Turnover rate](../metrics/turnover-rate.md), [Transaction retention rate](../metrics/transaction-retention-rate.md), and [Maximum drawdown](../metrics/maximum-drawdown.md).
- Is constrained by unresolved dependencies in the [Open decision map](open-decision-map.md).
- Is presented through the accepted [local browser workspace requirement](../../docs/requirements/R-020-local-browser-analysis-workspace.md)
  and [local-web stack decision](../../docs/decisions/ADR-0005-local-web-delivery-stack.md).
- Uses the [local runtime configuration](local-runtime-configuration.md) invariant for server-side credentials.
- Extends into [Regional ingestion and screening](regional-ingestion-and-screening.md)
  without an implicit nationwide transaction preload.

## Requirements

- See the [Requirement map](requirement-map.md) for the complete relationship among R-001 through R-020.
- The end-to-end comparison outcome is defined by [R-016](../../docs/requirements/R-016-apartment-comparison.md).
- Reproducibility across the flow is defined by [R-019](../../docs/requirements/R-019-analysis-context.md).

## Decisions and open questions

- [ADR-0001: Documentation as context and navigation](../../docs/decisions/ADR-0001-documentation-policy.md)
- [ADR-0004: SQLite persistence, migrations, and monthly freshness](../../docs/decisions/ADR-0004-sqlite-persistence-and-freshness.md)
- [ADR-0005: Local-web delivery stack](../../docs/decisions/ADR-0005-local-web-delivery-stack.md)
- See the [Open decision map](open-decision-map.md) for unresolved domain and metric policies.

## Evidence and interpretation risks

- A valid metric can still be meaningless if identity, population, or context is wrong.
- Comparison magnifies inconsistencies because one hidden difference can favor one subject.
- Downstream UI convenience must not silently redefine upstream policy.
- Persistence and caching can preserve stale or misidentified evidence if source freshness is hidden.

## Verify in the repository

M2 analytics and M3 persistence/comparison evidence are implemented in [`analytics.py`](../../src/apt_analyzer/analytics.py), [`persistence.py`](../../src/apt_analyzer/persistence.py), and [`comparison.py`](../../src/apt_analyzer/comparison.py). Representative M3 tests are in [`test_m3.py`](../../tests/test_m3.py); the CLI entry point is [`cli.py`](../../src/apt_analyzer/cli.py). The web boundary is implemented in [`web`](../../src/apt_analyzer/web/__init__.py) and covered by [`test_web.py`](../../tests/test_web.py).
Regional ingestion and screening are implemented in [`regional_screening.py`](../../src/apt_analyzer/regional_screening.py)
and covered by [`test_m5.py`](../../tests/test_m5.py).

## Related pages

- [Requirement map](requirement-map.md)
- [Open decision map](open-decision-map.md)
- [Analysis context](../domain/analysis-context.md)
- [Transaction population](../data/transaction-population.md)
- [Local runtime configuration](local-runtime-configuration.md)
- [Regional ingestion and screening](regional-ingestion-and-screening.md)

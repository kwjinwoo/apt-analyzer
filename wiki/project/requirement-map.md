---
title: Requirement Map
type: project
role: topic
status: active
updated: 2026-09-12
aliases:
  - Requirement knowledge graph
tags:
  - requirements
  - traceability
---

# Requirement Map

## Scope

This hub groups the twenty-nine catalogued requirements by knowledge dependency
instead of repeating their normative text.

## Knowledge

Identity and acquisition establish the subject and records. Population requirements establish which records belong to an analysis. Metric requirements operate on that common population. Interpretation and presentation requirements preserve context. Comparison and screening reuse the same semantics across multiple subjects.

```text
Identity and acquisition
  R-001 → R-002 → R-003

Population
  R-004 → R-005 → R-006
  R-017 → R-018

Analytics
  R-007
  R-008 → R-009
  R-010
  R-011 → R-012

Interpretation and presentation
  R-013 (P0)
  R-014 (P0)
  R-019

Local interface
  R-020 → R-001/R-002/R-013/R-014/R-016/R-017/R-019

Local preferences
  R-023 → R-001/R-016/R-020

Period-driven analysis
  R-024 → R-003/R-008/R-010/R-011/R-013/R-014/R-019/R-020
  R-025 (superseded by R-026)
  R-026 (superseded by R-027) → R-008/R-010/R-011/R-019/R-024
  R-027 (superseded by R-028) → R-008/R-026
  R-028 → R-010/R-027
  R-029 → R-001/R-019/R-020/R-023

Multi-complex use
  R-016 → R-015 → R-021
  R-030 → R-029/R-019/R-020
  R-031 → R-006/R-008/R-030
```

The arrows express knowledge dependency, not implementation order or control flow.

## Graph connections

- Identity requirements connect through [Apartment identity](../domain/apartment-identity.md).
- Population requirements connect through [Area group](../domain/area-group.md), [Transaction population](../data/transaction-population.md), and [Transaction quality](../data/transaction-quality.md).
- Analytics requirements connect through [Turnover rate](../metrics/turnover-rate.md), [Transaction retention rate](../metrics/transaction-retention-rate.md), and [Maximum drawdown](../metrics/maximum-drawdown.md).
- Interpretation depends on [Analysis context](../domain/analysis-context.md) and [Price-series evidence](../data/price-series-evidence.md).
- End-to-end dependency is summarized by the [MVP knowledge map](mvp-knowledge-map.md).
- The local interface boundary is defined by [R-020](../../docs/requirements/R-020-local-browser-analysis-workspace.md)
  and [ADR-0005](../../docs/decisions/ADR-0005-local-web-delivery-stack.md).
- Local saved interests are mapped by [R-023](../../docs/requirements/R-023-saved-apartment-interests.md)
  and [Saved apartment interests](saved-apartment-interests.md).
- Period defaults and rolling metrics are mapped by [R-024](../../docs/requirements/R-024-period-driven-analysis.md)
  and [Period-driven analysis](period-driven-analysis.md).
- Current direct chart exploration, duration-aware turnover, and 12/24-month
  retention preview behavior are governed by [R-028](../../docs/requirements/R-028-chart-preview-retention-split.md)
  and [ADR-0014](../../docs/decisions/ADR-0014-chart-preview-retention-split.md).
  R-026/R-027 and ADR-0012/ADR-0013 remain historical superseded decisions.
- Persisted complex profile facts and distinct transaction observations are
  governed by [R-029](../../docs/requirements/R-029-apartment-profile.md) and
  [ADR-0015](../../docs/decisions/ADR-0015-source-labeled-apartment-profile.md),
  with navigation in [Apartment profile](../domain/apartment-profile.md).
- Exact inventory is governed by [R-030](../../docs/requirements/R-030-exact-area-inventory.md)
  and [ADR-0016](../../docs/decisions/ADR-0016-exact-area-inventory-source.md),
  with navigation in [Exact area inventory](../domain/exact-area-inventory.md).
- Area turnover denominator derivation is governed by [R-031](../../docs/requirements/R-031-area-group-inventory-denominator.md)
  and [ADR-0017](../../docs/decisions/ADR-0017-area-inventory-turnover-denominator.md).
- Regional descriptive interpretation extends through [Regional relative analysis](regional-relative-analysis.md).

## Requirements

- The authoritative catalog is [Requirements](../../docs/requirements/index.md).
- Each wiki concept page links only the requirements that materially constrain it.

## Decisions and open questions

- Requirement relationships affected by unresolved policy are collected in the [Open decision map](open-decision-map.md).
- Requirement semantics are governed by [ADR-0001](../../docs/decisions/ADR-0001-documentation-policy.md), which keeps current behavior authoritative in code and tests. Interface choices are recorded in [ADR-0005](../../docs/decisions/ADR-0005-local-web-delivery-stack.md).

## Evidence and interpretation risks

- This map can become stale when a requirement is added, superseded, or materially changed.
- A link expresses relevance, not proof of implementation coverage.
- Priority and milestone order must be read from the requirement catalog and roadmap rather than inferred from graph position.

## Verify in the repository

Initial domain evidence is linked from R-003, R-006, R-017, and R-019. R-013, R-014,
and R-020 now have local workspace implementation evidence; representative tests remain
linked from each Requirement document rather than duplicated in this map. R-015 has
bounded regional cache, ingestion, and screening evidence linked from its Requirement.
R-021 has independent profile and live multi-region evidence linked from its Requirement.

## Related pages

- [MVP knowledge map](mvp-knowledge-map.md)
- [Open decision map](open-decision-map.md)
- [Regional ingestion and screening](regional-ingestion-and-screening.md)
- [Regional relative analysis](regional-relative-analysis.md)
- [Analysis context](../domain/analysis-context.md)
- [Transaction population](../data/transaction-population.md)
- [Saved apartment interests](saved-apartment-interests.md)
- [Period-driven analysis](period-driven-analysis.md)
- [Apartment profile](../domain/apartment-profile.md)

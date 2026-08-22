---
title: Requirement Map
type: project
role: topic
status: active
updated: 2026-08-21
aliases:
  - Requirement knowledge graph
tags:
  - requirements
  - traceability
---

# Requirement Map

## Scope

This hub groups the nineteen initial requirements by knowledge dependency instead of repeating their normative text.

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
  R-013
  R-014
  R-019

Multi-complex use
  R-016 → R-015
```

The arrows express knowledge dependency, not implementation order or control flow.

## Graph connections

- Identity requirements connect through [Apartment identity](../domain/apartment-identity.md).
- Population requirements connect through [Area group](../domain/area-group.md), [Transaction population](../data/transaction-population.md), and [Transaction quality](../data/transaction-quality.md).
- Analytics requirements connect through [Turnover rate](../metrics/turnover-rate.md), [Transaction retention rate](../metrics/transaction-retention-rate.md), and [Maximum drawdown](../metrics/maximum-drawdown.md).
- Interpretation depends on [Analysis context](../domain/analysis-context.md) and [Price-series evidence](../data/price-series-evidence.md).
- End-to-end dependency is summarized by the [MVP knowledge map](mvp-knowledge-map.md).

## Requirements

- The authoritative catalog is [Requirements](../../docs/requirements/index.md).
- Each wiki concept page links only the requirements that materially constrain it.

## Decisions and open questions

- Requirement relationships affected by unresolved policy are collected in the [Open decision map](open-decision-map.md).
- Requirement semantics are governed by [ADR-0001](../../docs/decisions/ADR-0001-documentation-policy.md), which keeps current behavior authoritative in code and tests.

## Evidence and interpretation risks

- This map can become stale when a requirement is added, superseded, or materially changed.
- A link expresses relevance, not proof of implementation coverage.
- Priority and milestone order must be read from the requirement catalog and roadmap rather than inferred from graph position.

## Verify in the repository

No implementation evidence exists yet. As tests appear, representative evidence remains linked from each Requirement document rather than duplicated in this map.

## Related pages

- [MVP knowledge map](mvp-knowledge-map.md)
- [Open decision map](open-decision-map.md)
- [Analysis context](../domain/analysis-context.md)
- [Transaction population](../data/transaction-population.md)

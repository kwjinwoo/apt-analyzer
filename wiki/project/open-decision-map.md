---
title: Open Decision Map
type: project
role: topic
status: active
updated: 2026-09-08
aliases:
  - Open-question graph
  - Unresolved policy map
tags:
  - decisions
  - risks
---

# Open Decision Map

## Scope

This hub maps unresolved questions to the concepts and requirements they can change. It does not choose among candidate policies.

## Knowledge

Open questions are high-impact graph nodes because one decision can cascade across population construction, metric meaning, presentation, and comparison. The authoritative status and evidence needed for each question remain in [Open questions](../../docs/open-questions.md).

| Open question | Primary concepts affected |
|---|---|
| OQ-001 Stable apartment identity | Identity, transaction retrieval, household metadata, comparison |
| OQ-002 Area-group boundary | Area discovery, filtering, price population, cross-complex comparison |
| OQ-003 Missing price months | Price-series evidence, MDD, price visualization |
| OQ-004 Partial-year annualization | Turnover, retention, analysis context; ADR-0010 avoids it only for completed-month defaults |
| OQ-005 Zero retention baseline | Retention result semantics |
| OQ-006 Direct-transaction default | Transaction population, price series, every metric |
| OQ-007 Outlier comparison | Transaction quality, price summaries, MDD |
| OQ-008 Area-filtered turnover | Area group, denominator scope, turnover presentation |
| OQ-009 Monthly evidence threshold | Price-series evidence, MDD qualification, visualization |
| OQ-010 Exact area-by-household inventory source | Apartment profile, household inventory granularity, Building HUB identity and reconciliation |

When a question is resolved, the accepted ADR becomes the authority, affected living pages receive cascade updates, and this table points to the ADR instead of deleting the historical relationship.

## Graph connections

- Identity uncertainty centers on [Apartment identity](../domain/apartment-identity.md).
- Area uncertainty centers on [Area group](../domain/area-group.md).
- Population policy centers on [Transaction population](../data/transaction-population.md) and [Transaction quality](../data/transaction-quality.md).
- Duration and denominator questions affect [Turnover rate](../metrics/turnover-rate.md) and [Transaction retention rate](../metrics/transaction-retention-rate.md).
- Sparse evidence questions affect [Price-series evidence](../data/price-series-evidence.md) and [Maximum drawdown](../metrics/maximum-drawdown.md).

## Requirements

- The [Requirement map](requirement-map.md) shows which accepted outcomes depend on these concepts.
- Individual Requirement pages link directly to their applicable open questions.

## Decisions and open questions

- OQ-001 is resolved for the initial version; OQ-002 through OQ-010 remain unresolved as of 2026-09-08.
- [ADR-0010](../../docs/decisions/ADR-0010-completed-month-rolling-analysis.md) accepts completed-month defaults while OQ-004 remains unresolved for arbitrary partial-year annualization.

## Evidence and interpretation risks

- A candidate may be repeated often enough to look accepted when it is not.
- Resolving one question can expose a new constraint in another concept.
- Removing a resolved question without cascade updates leaves stale wiki claims.
- An implementation choice made before a decision can accidentally become policy.

## Verify in the repository

No implementation evidence exists yet. When code appears, check that unresolved candidates have not been embedded as invisible defaults and that accepted ADRs have representative tests.

## Related pages

- [MVP knowledge map](mvp-knowledge-map.md)
- [Requirement map](requirement-map.md)
- [Analysis context](../domain/analysis-context.md)
- [Transaction quality](../data/transaction-quality.md)

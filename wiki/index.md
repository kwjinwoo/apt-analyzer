# apt-analyzer Wiki

This is an LLM-maintained knowledge graph compiled from project documentation and, once present, verified code and tests. It connects concepts and evidence; it is not authoritative for current behavior or product policy.

Start with the topic closest to the question, follow its graph connections, and then verify the linked authoritative sources.

## Domain

- [Apartment identity](domain/apartment-identity.md) — How records from different sources are resolved to one analysis subject.
- [Area group](domain/area-group.md) — How raw exclusive areas, market-facing groups, and analysis populations relate.
- [Analysis context](domain/analysis-context.md) — The conditions required to interpret and reproduce an analysis result.

## Metrics

- [Turnover rate](metrics/turnover-rate.md) — How transaction activity, household denominators, area filters, and annualization interact.
- [Transaction retention rate](metrics/transaction-retention-rate.md) — How comparable annualized activity is related across baseline and comparison periods.
- [Maximum drawdown](metrics/maximum-drawdown.md) — How monthly price evidence, sparsity, peak, and trough determine an observed drawdown.

## Data

- [Transaction population](data/transaction-population.md) — How identity, dates, area, cancellation, transaction type, and outliers define eligibility.
- [Transaction quality](data/transaction-quality.md) — How source corrections, duplicates, parsing, and traceability affect confidence.
- [Price-series evidence](data/price-series-evidence.md) — What monthly transaction observations can and cannot support about price movement.

## Project maps

- [MVP knowledge map](project/mvp-knowledge-map.md) — End-to-end dependency map for the initial product outcome.
- [Requirement map](project/requirement-map.md) — Cross-cutting relationships among the twenty accepted requirements.
- [Open decision map](project/open-decision-map.md) — Unresolved questions and the concepts they currently affect.
- [Local runtime configuration](project/local-runtime-configuration.md) — Server-side credential loading and local workspace configuration invariants.

## Operating instructions

Use the repository [`$query-project-wiki` skill](../.agents/skills/query-project-wiki/SKILL.md) to retrieve scoped knowledge and repository navigation. See [wiki maintenance instructions](AGENTS.md) before ingesting, correcting, decomposing, archiving, or otherwise modifying the graph.

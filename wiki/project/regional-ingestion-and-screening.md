---
title: Regional ingestion and screening
type: project
role: topic
status: active
updated: 2026-08-26
aliases: []
tags:
  - regional-ingestion
  - screening
---

# Regional ingestion and screening

## Scope

M5 provides bounded regional candidate caching, SQLite persistence, and reusable
historical scalar screening.

## Knowledge

Regions and requested periods are explicit. Candidate cache states distinguish valid
empty, miss/stale, and external failure. Successful coverage and the latest source
attempt are persisted separately, so a later failure does not erase usable evidence.
Transaction evidence carries complete, valid-empty, or failed monthly state. Screening
shares one analysis configuration; unavailable metrics cannot satisfy a rule.

## Graph connections

- [Requirement Map](requirement-map.md)
- [Transaction population](../data/transaction-population.md)
- [Analysis context](../domain/analysis-context.md)

## Requirements

- [R-015 apartment screening](../../docs/requirements/R-015-apartment-screening.md)

## Decisions and open questions

- [ADR-0006](../../docs/decisions/ADR-0006-regional-cache-and-screening.md) records
  bounded scope and indefinite local retention.

## Evidence and interpretation risks

The scale script's timing is environment-dependent; its index-plan evidence is the
stable query-bound evidence. This is historical screening, not investment advice.

## Verify in the repository

Inspect [`m5.py`](../../src/apt_analyzer/m5.py),
[`persistence.py`](../../src/apt_analyzer/persistence.py), and
[`validate_m5_scale.py`](../../scripts/validate_m5_scale.py). Representative contracts
are in [`test_m5.py`](../../tests/test_m5.py), including persisted cache states, bounded
ingestion, schema migration/index evidence, comparable metrics, missing-value exclusion,
and real CLI JSON/text equivalence.

## Related pages

- [MVP knowledge map](mvp-knowledge-map.md)

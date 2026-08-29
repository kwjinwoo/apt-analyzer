---
title: Regional ingestion and screening
type: project
role: topic
status: active
updated: 2026-08-28
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
shares one analysis configuration; unavailable metrics cannot satisfy a rule. The M7
local browser workspace exposes this persisted workflow at `/screen` and provides an
equivalent `/export?kind=screening` JSON contract with visible values, coverage,
context, and the historical non-recommendation disclaimer.

## Graph connections

- [Requirement Map](requirement-map.md)
- [Transaction population](../data/transaction-population.md)
- [Analysis context](../domain/analysis-context.md)

## Requirements

- [R-015 apartment screening](../../docs/requirements/R-015-apartment-screening.md)
- [R-022 local productized analysis and screening workspace](../../docs/requirements/R-022-local-productized-screening.md)

## Decisions and open questions

- [ADR-0006](../../docs/decisions/ADR-0006-regional-cache-and-screening.md) records
  bounded scope and indefinite local retention.
- [ADR-0008](../../docs/decisions/ADR-0008-interactive-province-list-freshness.md) records
  the 24-hour interactive province-list freshness and stale fallback policy.

## Evidence and interpretation risks

The scale script's timing is environment-dependent; its index-plan evidence is the
stable query-bound evidence. This is historical screening, not investment advice.

Interactive K-APT province-list search reuses a persisted full-province snapshot for
24 hours across local restarts and name queries. At expiry it synchronously
revalidates the complete province and atomically replaces the snapshot only after
success; a failed refresh keeps matching stale candidates visible with the last
successful refresh time. This list cache is separate from K-APT detail and
transaction evidence.

## Verify in the repository

Inspect [`regional_screening.py`](../../src/apt_analyzer/regional_screening.py) and
the `/screen` route in [`web/__init__.py`](../../src/apt_analyzer/web/__init__.py),
[`persistence.py`](../../src/apt_analyzer/persistence.py), and
[`validate_m5_scale.py`](../../scripts/validate_m5_scale.py). Representative contracts
are in [`test_m5.py`](../../tests/test_m5.py), including persisted cache states, bounded
ingestion, schema migration/index evidence, comparable metrics, missing-value exclusion,
and real CLI JSON/text equivalence. The product interface contract is covered by
[`test_web.py`](../../tests/test_web.py).

## Related pages

- [MVP knowledge map](mvp-knowledge-map.md)
- [Regional relative analysis](regional-relative-analysis.md)

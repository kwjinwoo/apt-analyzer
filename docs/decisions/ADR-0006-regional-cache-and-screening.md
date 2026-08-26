---
id: ADR-0006
title: Regional candidate cache and bounded screening
status: accepted
date: 2026-08-26
supersedes: []
superseded_by: null
related_requirements: [R-015, R-001, R-002, R-003]
---

# ADR-0006: Regional candidate cache and bounded screening

## Status

Accepted

## Context

Regional screening must remain reproducible without implicitly preloading nationwide
transaction history or hiding unavailable source coverage.

## Decision

Cache candidate metadata only for explicitly named regions. Require an explicit,
non-empty region set and requested period for ingestion; preserve valid-empty,
cache-miss/stale, and external-failure states. Retain normalized evidence and
successful monthly coverage indefinitely in the selected local SQLite database. Persist
the latest candidate and transaction acquisition attempt separately from successful
coverage so a failure cannot erase good evidence or masquerade as a valid empty result.
Screening applies one common analysis configuration and treats unavailable metrics as
non-matches, with historical-screening disclaimer output.

The initial scalar filters are overall-period eligible transaction median price in KRW,
overall-period eligible median exclusive area in square metres, eligible transaction
count, turnover ratio, transaction-retention ratio, and MDD ratio. Each rule carries one
of `eq`, `ne`, `gt`, `gte`, `lt`, or `lte`, its fixed unit, and its calculation method;
a range is two explicit boundary rules. Existing analytics definitions and unavailable
states control turnover, retention, and MDD.

## Rationale

Explicit scope prevents accidental nationwide loading and makes screening evidence
reproducible across refreshes and local databases.

## Alternatives considered

Implicit nationwide preload and automatic cleanup were rejected because they obscure
scope, risk destructive loss, and conflict with accepted retention policy.

## Consequences

SQLite schema v3 stores regional snapshots and indexed period-bounded transactions.
Cleanup, background refresh, recommendation ranking, and web screening remain outside
this milestone.

## Related documentation

- [R-015](../requirements/R-015-apartment-screening.md)
- [Roadmap M5](../roadmap.md#m5-regional-ingestion-and-screening)

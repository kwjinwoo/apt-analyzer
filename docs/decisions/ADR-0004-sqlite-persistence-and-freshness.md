---
id: ADR-0004
title: SQLite persistence, migrations, and monthly freshness
status: accepted
date: 2026-08-23
supersedes: []
superseded_by: null
related_requirements: [R-002, R-016, R-019]
---
# ADR-0004: SQLite persistence, migrations, and monthly freshness
## Status
Accepted
## Context
M3 needs repeatable local acquisition and comparison without coupling analytics to a server or adding a runtime dependency.
## Decision
Use a stdlib SQLite adapter with deterministic, atomic schema migrations. Legacy transaction backfills and exact-duplicate collapse commit together with the version update. Store normalized transactions with a source-aware full-record uniqueness key, and store successful monthly coverage keyed by apartment, source, and month with fetched-at timestamps. Missing or stale months are fetched through an injected callable; valid-empty responses are successful coverage, while exceptions, provenance mismatches, or apartment/month mismatches remain failures and do not create coverage. Unsupported schema versions are rejected.
## Rationale
SQLite is locally portable and transactional. Explicit coverage and freshness prevent caches from hiding stale evidence, while full-record keys preserve corrected source evidence.
## Alternatives considered
### In-memory-only acquisition
Rejected because repeated runs would lose coverage and provenance.
### External database dependency
Rejected for the local MVP because it adds deployment and runtime coupling without improving the bounded contract.
## Consequences
Comparison can load reproducible local evidence and apply one common analysis context. Refresh policy remains caller-controlled; external acquisition and credentials remain outside this adapter.
## Related documentation
- [R-016](../requirements/R-016-apartment-comparison.md)
- [R-019](../requirements/R-019-analysis-context.md)

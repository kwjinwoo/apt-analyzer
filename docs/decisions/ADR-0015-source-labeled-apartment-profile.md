---
id: ADR-0015
title: Source-labeled persisted apartment profile
status: accepted
date: 2026-09-08
supersedes: []
superseded_by: null
related_requirements: [R-029, R-019, R-020, R-023]
---

# ADR-0015: Source-labeled persisted apartment profile

## Status

Accepted

## Context

The result needs durable complex facts, but K-APT profile data and transaction
records describe different kinds of evidence. A profile must survive offline
analysis and remain attributable to its source and retrieval time.

## Decision

Persist the optional K-APT apartment profile and its source/fetched timestamp in
the local SQLite workspace. Save or replace it only during explicit live
selection or the existing explicit basic-information refresh. Preserve the
last-good profile and matching household evidence when refresh fails. Keep
K-APT's official broad area-band inventory separate from exact or grouped areas
observed among eligible transactions.

## Rationale

This preserves source provenance, supports offline results, and prevents
transaction observations from being mistaken for complete household inventory.

## Alternatives considered

### Alternative A: Infer exact unit inventory from trades

Rejected because transactions are a partial, time-bound population and do not
establish the complex's complete unit composition.

### Alternative B: Fetch profile during analysis

Rejected because analysis must be reproducible and persisted-evidence-only;
explicit acquisition remains a separate user action.

### Alternative C: Merge both sources into one area table

Rejected because official area bands and observed transaction areas have
different granularity and meanings.

## Consequences

### Positive

- Results can show useful profile facts offline with explicit provenance.
- Missing or partial source fields remain honest and do not corrupt identity or
  metric interpretation.

### Negative

- Profile data can become stale until explicitly refreshed.
- Exact unit-type inventory remains unavailable without an authoritative source.

### Follow-up

- Keep source/fetched-time evidence visible in human and machine result context.
- Review profile field availability when K-APT changes its contract.

## Related documentation

- [R-029: Persisted apartment-complex profile](../requirements/R-029-apartment-profile.md)
- [R-019: Visible analysis context](../requirements/R-019-analysis-context.md)
- [ADR-0003: Official sources and apartment identity](ADR-0003-official-sources-and-apartment-identity.md)

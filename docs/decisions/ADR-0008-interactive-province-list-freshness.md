---
id: ADR-0008
title: Interactive province-list freshness and stale fallback
status: accepted
date: 2026-08-28
supersedes: []
superseded_by: null
related_requirements: [R-001, R-020, R-022]
---

# ADR-0008: Interactive province-list freshness and stale fallback

## Status

Accepted

## Context

Interactive name search currently obtains a complete K-APT province list before
filtering locally. Repeating that source request across local server restarts is
unnecessary when the same SQLite workspace already has a recent successful list,
but silently using an expired list would hide freshness risk.

## Decision

Persist the complete K-APT province list in the configured SQLite candidate snapshot
and treat successful snapshots as fresh for exactly 24 hours. Search-name changes
within a province reuse that full snapshot. At or after expiry, the next interactive
search synchronously fetches every province page with source-cache bypass enabled and
replaces the snapshot only after the complete fetch succeeds atomically. If refresh
fails, retain and search the previous snapshot while displaying its last successful
refresh time; on a cache miss, show a failure/no-result state.

## Rationale

This preserves responsive repeated local searches while making stale evidence visible
and preventing partial source results from overwriting a known-good snapshot.

## Alternatives considered

### Background refresh

Rejected because the local synchronous web boundary does not need background jobs and
the user should see the revalidation state attached to the active search.

### Delete expired snapshots

Rejected because stale candidates remain useful fallback evidence when revalidation is
temporarily unavailable.

## Consequences

### Positive

- Restarts and repeated name queries avoid unnecessary K-APT list calls within 24 hours.
- Expiry, source failure, and last-success time remain visible to the user.

### Negative

- The first search after expiry waits for a complete province revalidation.
- Local counts and freshness apply only to the configured SQLite workspace, not portal-global state.

## Related documentation

- [R-001](../requirements/R-001-apartment-search.md)
- [R-020](../requirements/R-020-local-browser-analysis-workspace.md)
- [R-022](../requirements/R-022-local-productized-screening.md)
- [ADR-0006](ADR-0006-regional-cache-and-screening.md)

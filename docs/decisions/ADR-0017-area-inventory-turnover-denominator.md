---
id: ADR-0017
title: Verified exact inventory denominator for area turnover
status: accepted
date: 2026-09-12
supersedes: []
superseded_by: null
related_requirements: [R-031, R-008, R-030]
---

# ADR-0017: Verified exact inventory denominator for area turnover

## Status

Accepted

## Context

An area-filtered transaction population needs a matching household denominator. K-APT's complex total is incompatible with a selected area group, while transaction observations are incomplete.

## Decision

For one selected apartment analysis, derive the denominator from the last verified Building HUB snapshot by applying the active integer-floor grouping policy to every exact inventory area. Preserve K-APT's complex total for all-area analysis.

## Rationale

This keeps numerator and denominator scope aligned without introducing a new grouping rule or network access during analysis.

## Alternatives considered

- Use the K-APT complex total: rejected for area scope mismatch.
- Infer households from transactions: rejected as incomplete.
- Add a separate area grouping policy: rejected as unnecessary scope expansion.

## Consequences

### Positive

- Area turnover can use a verified matching denominator and clear provenance.

### Negative

- No verified snapshot means area turnover remains unavailable.

### Follow-up

Revalidate current-query evidence when source schema or grouping policy changes; do not interpret it as historical inventory.

## Related documentation

- [R-031](../requirements/R-031-area-group-inventory-denominator.md)
- [R-030](../requirements/R-030-exact-area-inventory.md)

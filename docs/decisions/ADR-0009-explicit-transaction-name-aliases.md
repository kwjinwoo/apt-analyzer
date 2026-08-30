---
id: ADR-0009
title: Explicit source-scoped transaction-name aliases
status: accepted
date: 2026-08-30
supersedes: []
superseded_by: null
related_requirements: [R-001, R-002]
---

# ADR-0009: Explicit source-scoped transaction-name aliases

## Status

Accepted

## Context

Some K-APT complexes are reported by MOLIT as several component names even
though the selected K-APT candidate represents one aggregate complex. Exact
name matching can therefore turn real same-lot transactions into a misleading
valid-empty result. Address-only or generic fuzzy matching would risk merging
unrelated complexes.

## Decision

Maintain an explicit, auditable transaction-name alias registry keyed by K-APT
source ID. A registered alias may be retrieved only when the existing exact
legal-dong and lot-address evidence also matches. The initial registry maps
`A44347025` (벽적골두산한신우성) to `벽적골두산`, `벽적골한신`, and
`벽적골우성`.

When multiple same-lot names conservatively resemble components of a selected
compound name but are not registered aliases, raise an identity mismatch that
requires explicit mapping. Never infer acceptance from this detector. A truly
empty source response remains valid empty, and exact-name behavior remains
unchanged.

## Rationale

Source-ID scoping makes the exceptional name relationship reviewable and keeps
address evidence mandatory. Raising on a plausible unmapped compound prevents
identity ambiguity from being cached as empty evidence.

## Alternatives considered

### Generic fuzzy or substring matching

Rejected because it can silently combine unrelated complexes or accept a name
without sufficient identity evidence.

### Address-only matching

Rejected because a shared parcel does not establish that transaction names
belong to the selected complex.

### Silent valid-empty fallback

Rejected because an unmapped same-lot component response is an identity failure,
not evidence that no transactions exist.

## Consequences

### Positive

- Verified aggregate-name differences can be retrieved without weakening address checks.
- Unmapped compound-name evidence remains visible as an identity failure.

### Negative

- Alias mappings require manual maintenance and can become stale when source
  naming or complex composition changes.
- A conservative detector may require review for a response that is not an
  actual aggregate relationship.

### Follow-up

- Review aliases when authoritative K-APT or MOLIT naming evidence changes.

## Related documentation

- [R-001: Apartment search](../requirements/R-001-apartment-search.md)
- [R-002: Sale transaction retrieval](../requirements/R-002-transaction-retrieval.md)
- [ADR-0003: Official sources and apartment identity](ADR-0003-official-sources-and-apartment-identity.md)

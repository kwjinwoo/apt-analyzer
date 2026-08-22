---
id: ADR-0003
title: Official sources and apartment identity
status: proposed
date: 2026-08-22
supersedes: []
superseded_by: null
related_requirements: [R-001, R-002, R-003, R-017]
---
# ADR-0003: Official sources and apartment identity
## Status
Proposed
## Context
M1 needs searchable complex metadata and sale records, but the official sources do not share one universal complex identifier. Name-only matching can silently merge distinct complexes.
## Decision
Use K-APT apartment lists for candidates and source IDs and the MOLIT apartment-sale API for transactions. Resolve a project identity only from an explicitly selected single candidate when its K-APT ID, legal-dong code, address, and normalized-name evidence can be linked explicitly. Ambiguity is a result state, never an automatic selection.

Preserve supplied source fields through normalization. Deduplicate exact repeated source rows by a deterministic digest of the complete row; differing evidence remains distinct. Cancellation records remain inspectable. Acquisition distinguishes empty data from authentication, availability, protocol, and parsing failures. Cached results expose source, fetch time, query coverage, and cached status.

The data.go.kr Encoding key in `DATA_GO_KR_SERVICE_KEY` is already percent-encoded and is inserted exactly once. This direction cannot be accepted until the K-APT detail operation needed for legal-dong and full-address linkage is accessible and the end-to-end match is validated.
## Rationale
Official evidence is reproducible, while explicit selection makes mismatches detectable. Full-row identity avoids collapsing distinguishable same-day trades where no durable transaction ID exists.
## Alternatives considered
### Display-name identity
Rejected because duplicate and variant names are common.
### Universal derived cross-source ID
Rejected because current evidence cannot guarantee permanence across renames or address corrections.
## Consequences
### Positive
- Provenance and ambiguity remain visible.
- Repeated retrieval is idempotent without discarding distinguishable trades.
### Negative
- K-APT list rows do not supply the legal-dong and full-address evidence needed to query and verify MOLIT records directly; the detail operation currently returns HTTP 403 for the configured key.
- A corrected source row has a new digest and remains separately inspectable.
### Follow-up
- Revisit renamed-complex continuity when authoritative historical evidence exists.
## Related documentation
- [R-001](../requirements/R-001-apartment-search.md)
- [R-002](../requirements/R-002-transaction-retrieval.md)
- [Apartment identity](../domain/glossary.md#apartment-identity)

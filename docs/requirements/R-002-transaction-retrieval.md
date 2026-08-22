---
id: R-002
title: Sale transaction retrieval
status: accepted
priority: P0
created: 2026-08-21
updated: 2026-08-21
origin: "Initial requirements R2"
supersedes: []
superseded_by: null
related_requirements: [R-001, R-003, R-017]
related_decisions: []
---

# R-002: Sale transaction retrieval

## Intent

All initial analytics depend on a reproducible history of actual apartment sale transactions for the selected complex.

## Requirement

The system can retrieve and normalize apartment sale transactions for a selected apartment complex.

## Acceptance criteria

- **AC-1:** Every normalized transaction includes contract date, price, exclusive area, floor, transaction type, and cancellation state when supplied by the source.
- **AC-2:** Building or unit information, construction year, and broker location are preserved when available and legally usable.
- **AC-3:** Relevant normalized values remain traceable to source data.
- **AC-4:** Repeated retrieval does not silently create duplicate transactions.
- **AC-5:** Source and parsing failures are distinguishable from a valid empty result.

## Constraints

- External source schemas do not define the analytics domain model.
- Historical corrections and cancellations must remain detectable.

## Non-goals

- Jeonse and monthly-rent transactions in the initial version.

## Verification

### Automated

Not established yet.

### Manual or data validation

- Compare retrieved records, yearly counts, cancellation states, and duplicate handling with public transaction data for at least three complexes.

### Verification gaps

- AC-1 through AC-5 have no implementation evidence yet.

## Open questions

- [OQ-001: Stable apartment identity](../open-questions.md#oq-001-stable-apartment-identity)

## Related documentation

- [Normalized transaction](../domain/glossary.md#normalized-transaction)
- [Normalization boundary](../architecture/overview.md#normalization)

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
related_decisions: [ADR-0003, ADR-0009]
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

- [`test_normalization_preserves_required_optional_and_source_values`](../../tests/test_m1.py) covers AC-1 through AC-3.
- [`test_retrieval_is_idempotent_and_enforces_date_boundaries`](../../tests/test_m1.py) covers AC-4.
- [`test_retrieval_uses_legal_code_and_rejects_name_only_address_mismatch`](../../tests/test_m1.py) covers identity-safe retrieval for AC-3 and AC-5.
- [`test_retrieval_accepts_verified_molit_aliases_for_kapt_aggregate`](../../tests/test_m1.py) and [`test_verified_alias_never_overrides_lot_or_legal_dong_evidence`](../../tests/test_m1.py) cover explicit source-scoped aliases and address-safe traceability for AC-3 and AC-5.
- [`test_unregistered_compound_name_components_require_explicit_mapping`](../../tests/test_m1.py) and [`test_unrelated_same_lot_name_remains_a_valid_empty_result`](../../tests/test_m1.py) cover conservative mismatch failure and valid-empty boundaries for AC-5.
- [`test_valid_empty_xml_is_distinct_from_failure`](../../tests/test_acquisition.py) covers the valid-empty side of AC-5.

### Manual or data validation

- Compare retrieved records, yearly counts, cancellation states, and duplicate handling with public transaction data for at least three complexes.

### Verification gaps

- Deterministic fixtures cover normalization and source outcomes. Opt-in live validation resolves and retrieves three complexes end to end for a two-month period.

## Open questions

- [OQ-001: Stable apartment identity](../open-questions.md#oq-001-stable-apartment-identity)

## Related documentation

- [Normalized transaction](../domain/glossary.md#normalized-transaction)
- [Normalization boundary](../architecture/overview.md#normalization)

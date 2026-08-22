---
id: R-017
title: Transaction inclusion policy
status: accepted
priority: P1
created: 2026-08-21
updated: 2026-08-22
origin: "Initial requirements R15"
supersedes: []
superseded_by: null
related_requirements: [R-002, R-006, R-007, R-008, R-010, R-011, R-019]
related_decisions: []
---

# R-017: Transaction inclusion policy

## Intent

Cancelled, direct, and brokered transactions can affect metrics differently. Users need explicit and reproducible control over the analysis population.

## Requirement

The system identifies cancelled, direct, and brokered transactions and applies an explicit inclusion policy to analytics.

## Acceptance criteria

- **AC-1:** Cancellation state remains distinguishable after normalization.
- **AC-2:** Direct and brokered transaction types remain distinguishable when source evidence supports them.
- **AC-3:** The policy can include or exclude supported transaction categories without modifying raw normalized records.
- **AC-4:** Raw and eligible transaction counts are visible.
- **AC-5:** Every metric result identifies the applied inclusion policy.

## Constraints

- Cancelled transactions are excluded from the default analytical population but remain inspectable and available to an explicit alternative policy.
- A valid empty result must remain distinguishable from an acquisition or parsing failure.
- Historical source corrections may require previously computed results to be refreshed.

## Non-goals

- Automatically classifying a legitimate direct transaction as an outlier.

## Verification

### Automated

- [`test_domain_values_represent_source_independent_analysis_context`](../../tests/test_domain.py) covers normalized cancellation and transaction-type representation for AC-1 and AC-2.
- [`test_transaction_volume_uses_explicit_population_without_external_api`](../../tests/test_transaction_volume.py) covers AC-3 through AC-5 for transaction volume.
- [`test_transaction_volume_distinguishes_valid_empty_population`](../../tests/test_transaction_volume.py) covers the valid-empty-result constraint.
- [`test_normalization_preserves_required_optional_and_source_values`](../../tests/test_m1.py) covers source normalization for AC-1 and AC-2.

### Manual or data validation

- Validate cancellation and transaction-type interpretation against public records for real complexes.

### Verification gaps

- Non-volume metric propagation is not established yet.

## Open questions

- [OQ-006: Default direct-transaction policy](../open-questions.md#oq-006-default-direct-transaction-policy)

## Related documentation

- [Transaction inclusion policy](../domain/glossary.md#transaction-inclusion-policy)
- [Shared metric rules](../domain/metrics.md#shared-rules)

---
id: R-001
title: Apartment search
status: accepted
priority: P0
created: 2026-08-21
updated: 2026-08-21
origin: "Initial requirements R1"
supersedes: []
superseded_by: null
related_requirements: [R-002]
related_decisions: [ADR-0003]
---

# R-001: Apartment search

## Intent

Users need to identify an analysis subject without assuming that an apartment name is unique or represented consistently across data sources.

## Requirement

The user can search for an apartment complex by name, distinguish ambiguous results by location or address, and select one result represented by a stable internal identity.

## Acceptance criteria

- **AC-1:** A name query returns matching apartment-complex candidates.
- **AC-2:** Each result exposes enough location or address information to distinguish same-name or similar-name complexes.
- **AC-3:** Selecting a result resolves it to an internal apartment ID.
- **AC-4:** Ambiguous evidence does not silently select or merge a complex.

## Constraints

- Display name alone is insufficient identity evidence.
- Identity matching across sources must remain explicit and testable.

## Non-goals

- Fuzzy ranking quality beyond what is needed to find and distinguish a known complex.

## Verification

### Automated

- [`test_resolution_never_auto_selects_ambiguous_candidates`](../../tests/test_m1.py) covers AC-3 and AC-4.
- [`test_search_uses_correct_kapt_operation_and_region_evidence`](../../tests/test_m1.py) covers AC-1 and AC-2.
- [`test_selected_candidate_is_enriched_from_kapt_detail_before_resolution`](../../tests/test_m1.py) covers detailed evidence and stable resolution for AC-2 and AC-3.

### Manual or data validation

- Validate at least one duplicated or ambiguous apartment name against real source data.

### Verification gaps

- Deterministic fixtures cover all criteria. Opt-in live validation enriches three explicit selections with K-APT legal-dong and full-address evidence before resolution.

## Open questions

- [OQ-001: Stable apartment identity](../open-questions.md#oq-001-stable-apartment-identity)

## Related documentation

- [Apartment identity](../domain/glossary.md#apartment-identity)
- [Apartment identity boundary](../architecture/overview.md#apartment-identity-resolution)

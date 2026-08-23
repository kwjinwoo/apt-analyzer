---
id: R-004
title: Available-area detection
status: accepted
priority: P0
created: 2026-08-21
updated: 2026-08-21
origin: "Initial requirements R4"
supersedes: []
superseded_by: null
related_requirements: [R-002, R-005, R-006]
related_decisions: []
---

# R-004: Available-area detection

## Intent

Area choices should come from the selected complex's observed data rather than requiring users to guess or manually type an area.

## Requirement

The system identifies and presents the exclusive-area selections available for a selected apartment complex.

## Acceptance criteria

- **AC-1:** Available choices are derived from the selected complex's eligible or known transaction data.
- **AC-2:** The user can select all areas or a discovered area group.
- **AC-3:** Raw exclusive-area values remain inspectable even when grouped for display.
- **AC-4:** An absence of area evidence is represented explicitly rather than as an invented choice.

## Constraints

- Available choices depend on the data coverage used for discovery.

## Non-goals

- Inferring apartment unit types that are absent from all available source evidence.

## Verification

### Automated

- [`test_discover_area_groups_preserves_raw_areas_with_integer_floor`](../../tests/test_m2.py) covers AC-1 through AC-4 for deterministic discovery and raw-area visibility.
- [`test_discover_area_groups_represents_absent_area_evidence_as_empty`](../../tests/test_m2.py) covers explicit absence of area evidence.

### Manual or data validation

- Compare discovered values with real transaction histories for validation complexes.

### Verification gaps

- Real-complex distribution validation remains open.

## Open questions

- [OQ-002: Area-group boundary](../open-questions.md#oq-002-area-group-boundary)

## Related documentation

- [Exclusive area](../domain/glossary.md#exclusive-area)
- [Area group](../domain/glossary.md#area-group)

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

Not established yet.

### Manual or data validation

- Compare discovered values with real transaction histories for validation complexes.

### Verification gaps

- AC-1 through AC-4 have no implementation evidence yet.

## Open questions

- [OQ-002: Area-group boundary](../open-questions.md#oq-002-area-group-boundary)

## Related documentation

- [Exclusive area](../domain/glossary.md#exclusive-area)
- [Area group](../domain/glossary.md#area-group)

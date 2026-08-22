---
id: R-005
title: Exclusive-area grouping
status: accepted
priority: P0
created: 2026-08-21
updated: 2026-08-21
origin: "Initial requirements R5"
supersedes: []
superseded_by: null
related_requirements: [R-004, R-006]
related_decisions: []
---

# R-005: Exclusive-area grouping

## Intent

Slightly different recorded exclusive areas can represent the same market-facing unit segment and should be analyzable together without destroying source precision.

## Requirement

The system can assign similar raw exclusive-area values to a replaceable area-group classification while preserving each raw value.

## Acceptance criteria

- **AC-1:** Every grouped transaction retains its raw exclusive-area value.
- **AC-2:** The derived group is distinguishable from the raw value.
- **AC-3:** The same grouping policy produces deterministic results for the same input.
- **AC-4:** Grouping behavior can be validated and replaced independently of transaction acquisition and metric calculations.

## Constraints

- Integer-level grouping is an initial candidate, not a permanently accepted market rule.
- Grouping must not imply that all units in a group are physically identical.

## Non-goals

- A universal grouping rule guaranteed to match market convention for every complex.

## Verification

### Automated

Not established yet.

### Manual or data validation

- Validate candidate grouping against exclusive-area distributions from at least three real complexes.

### Verification gaps

- AC-1 through AC-4 have no implementation evidence yet.

## Open questions

- [OQ-002: Area-group boundary](../open-questions.md#oq-002-area-group-boundary)

## Related documentation

- [Area group](../domain/glossary.md#area-group)
- [Replaceable policies](../architecture/overview.md#replaceable-policies)

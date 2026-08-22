---
id: R-016
title: Apartment comparison
status: accepted
priority: P0
created: 2026-08-21
updated: 2026-08-21
origin: "Initial requirements R14"
supersedes: []
superseded_by: null
related_requirements: [R-006, R-007, R-008, R-010, R-011, R-019]
related_decisions: []
---

# R-016: Apartment comparison

## Intent

Users need to compare candidate complexes without hidden differences in population or metric configuration invalidating the comparison.

## Requirement

The user can compare multiple apartment complexes using the same area interpretation, periods, price method, and transaction inclusion policy.

## Acceptance criteria

- **AC-1:** Each compared complex is represented by a resolved apartment identity.
- **AC-2:** Common analysis context is applied to every comparison subject.
- **AC-3:** Household count, transaction count, turnover, retention, and MDD can be presented together when available.
- **AC-4:** Unavailable values remain distinguishable from zero.
- **AC-5:** The common configuration and any subject-specific evidence limitations are visible.

## Constraints

- Area labels are not automatically comparable when grouping evidence differs across complexes.
- Exact area-level turnover requires comparable area-specific household counts.

## Non-goals

- Automatically declaring one apartment a better investment.

## Verification

### Automated

Not established yet.

### Manual or data validation

- Reproduce at least one two-complex comparison from its displayed inputs.

### Verification gaps

- AC-1 through AC-5 have no implementation evidence yet.

## Open questions

- [OQ-002: Area-group boundary](../open-questions.md#oq-002-area-group-boundary)
- [OQ-008: Area-filtered turnover presentation](../open-questions.md#oq-008-area-filtered-turnover-presentation)

## Related documentation

- [Shared metric rules](../domain/metrics.md#shared-rules)
- [Roadmap M3](../roadmap.md#m3-persistence-and-apartment-comparison)

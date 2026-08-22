---
id: R-013
title: Transaction-volume visualization
status: accepted
priority: P1
created: 2026-08-21
updated: 2026-08-21
origin: "Initial requirements R11"
supersedes: []
superseded_by: null
related_requirements: [R-007, R-019]
related_decisions: []
---

# R-013: Transaction-volume visualization

## Intent

Users need to inspect changes in transaction activity over time more quickly than a summary metric alone allows.

## Requirement

The user can view eligible transaction volume as a yearly or monthly time series.

## Acceptance criteria

- **AC-1:** Each visual observation corresponds to an explicit calendar period and transaction count.
- **AC-2:** The visualization uses the active analysis population and inclusion policy.
- **AC-3:** Missing, zero, and unavailable periods are not visually conflated.
- **AC-4:** Underlying values remain accessible without relying only on visual position.

## Constraints

- Visualization must not redefine aggregation or inclusion semantics.

## Non-goals

- Selecting a final charting framework during core analytics validation.

## Verification

### Automated

Not established yet.

### Manual or data validation

- Visual inspection will be required once a presentation interface exists.

### Verification gaps

- AC-1 through AC-4 have no implementation evidence yet.

## Open questions

None.

## Related documentation

- [Transaction volume](../domain/metrics.md#transaction-volume)
- [Periodic aggregation requirement](R-007-periodic-aggregation.md)

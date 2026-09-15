---
id: R-031
title: Verified inventory denominator for area turnover
status: accepted
priority: P1
created: 2026-09-12
updated: 2026-09-12
origin: User-approved exact inventory turnover direction
supersedes: []
superseded_by: null
related_requirements: [R-006, R-008, R-030]
related_decisions: [ADR-0017]
---

# R-031: Verified inventory denominator for area turnover

## Intent

Make single-complex area turnover interpretable when a verified exact inventory snapshot supplies the matching area-group household denominator.

## Requirement

For a selected area group, use the active area grouping policy over every area in the last verified inventory snapshot and sum matching household counts. Keep all-complex turnover on the persisted K-APT total.

## Acceptance criteria

- **AC-1:** floor-59 and floor-49 derive their matching inventory counts, including inventory-only raw areas.
- **AC-2:** Derived evidence exposes group scope, Building HUB source, and collection time in analysis and export context.
- **AC-3:** Missing, unverified, mismatched, or zero-match inventory remains unavailable; analysis and preview stay offline.

## Constraints

The evidence is a current-query last-verified snapshot, not a historical as-of-period denominator. Comparison and screening remain out of scope.

## Non-goals

Changing grouping policy, comparison, screening, or historical inventory reconstruction.

## Verification

- [Web tests](../../tests/test_web.py) — area denominator and persisted context.
- [Inventory persistence tests](../../tests/test_inventory_persistence.py) — last-verified semantics.

## Open questions

None for the accepted single-analysis case.

## Related documentation

- [R-030](R-030-exact-area-inventory.md)
- [ADR-0017](../decisions/ADR-0017-area-inventory-turnover-denominator.md)

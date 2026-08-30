---
id: R-023
title: Saved apartment interests
status: accepted
priority: P1
created: 2026-08-30
updated: 2026-08-30
origin: "User-approved MVP direction"
supersedes: []
superseded_by: null
related_requirements: [R-001, R-016, R-020, R-022]
related_decisions: [ADR-0003, ADR-0004, ADR-0005]
---

# R-023: Saved apartment interests

## Intent

Users need to keep a deliberate list of apartment complexes they may want to
inspect again, without repeating identity resolution after each local workspace
restart or changing the evidence used by analysis.

## Requirement

The user can save an explicitly resolved apartment complex as an interest, see
the saved interests after restarting the local workspace, explicitly select a
saved interest for analysis, and remove the interest as a preference without
deleting its analysis evidence.

## Acceptance criteria

- **AC-1:** Saving is available only for an explicitly resolved apartment identity
  and records enough distinguishable source and address evidence to avoid
  treating a display name as the identity.
- **AC-2:** Saved interests persist in the explicitly configured local SQLite
  workspace and are listed after a local server restart.
- **AC-3:** The saved-interest list displays each saved complex distinctly and
  lets the user explicitly select one as an analysis subject; saved interests do
  not become comparison members without an explicit comparison selection.
- **AC-4:** Saving the same resolved apartment more than once is idempotent and
  leaves one saved interest.
- **AC-5:** Removing an interest removes the preference only; cached apartment,
  transaction, and coverage evidence remains available to analysis.
- **AC-6:** Saving, listing, or removing interests does not automatically
  acquire, refresh, or preload source data or mutate active analysis/comparison
  state. Explicit selection changes only the current subject; it does not
  automatically change periods, population/inclusion settings, or comparison
  membership.

## Constraints

- Identity safety follows [ADR-0003](../decisions/ADR-0003-official-sources-and-apartment-identity.md):
  a display name alone is insufficient, and ambiguity must remain explicit.
- Persistence remains within the explicitly configured local, single-user
  SQLite workspace described by [ADR-0004](../decisions/ADR-0004-sqlite-persistence-and-freshness.md)
  and [ADR-0005](../decisions/ADR-0005-local-web-delivery-stack.md).
- Removing an interest must not remove or invalidate transaction, apartment, or
  coverage evidence.

## Non-goals

- Cloud synchronization, authentication, or multi-user interest lists.
- Automatic data refresh, acquisition, or nationwide preloading.
- Automatic comparison membership, recommendations, ranking, or investment
  decisions.

## Verification

### Automated

- [`test_saved_interest_round_trip_is_idempotent_and_migrates_v4`](../../tests/test_m3.py) covers AC-2, AC-4, and AC-5 for v4-to-v5 migration, restart persistence, idempotence, and preference-only removal.
- [`test_interest_routes_persist_idempotently_and_restore_without_comparison_membership`](../../tests/test_web.py) covers AC-1 through AC-4 and AC-6 for resolved-selection saving, Korean listing/selection, no comparison-pool mutation, and no live call on interest selection.
- [`test_interest_remove_preserves_evidence_and_requires_resolved_selection`](../../tests/test_web.py) covers AC-1 and AC-5 through AC-6 for rejected absent selection, evidence preservation, and retaining the current selection after removal.
- [`test_legacy_v1_database_migrates_and_preserves_transaction`](../../tests/test_m3.py) and [`test_schema_v3_database_migrates_to_v4_and_preserves_evidence`](../../tests/test_m3.py) cover preservation of legacy evidence through the migration chain for AC-2.

### Manual or data validation

None.

### Verification gaps

- No acceptance-criterion gap remains in deterministic local tests. Real-source validation remains out of scope for this local, network-free contract.

## Open questions

None.

## Related documentation

- [R-001: Apartment search](R-001-apartment-search.md)
- [R-016: Apartment comparison](R-016-apartment-comparison.md)
- [R-020: Local browser analysis workspace](R-020-local-browser-analysis-workspace.md)
- [R-022: Local productized analysis and screening workspace](R-022-local-productized-screening.md)
- [ADR-0003: Official sources and apartment identity](../decisions/ADR-0003-official-sources-and-apartment-identity.md)
- [ADR-0004: SQLite persistence, migrations, and monthly freshness](../decisions/ADR-0004-sqlite-persistence-and-freshness.md)
- [ADR-0005: Local-web delivery stack](../decisions/ADR-0005-local-web-delivery-stack.md)

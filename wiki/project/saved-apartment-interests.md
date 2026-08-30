---
title: Saved Apartment Interests
type: project
role: topic
status: active
updated: 2026-08-30
aliases:
  - Favorite apartments
  - Saved complexes
tags:
  - preferences
  - local-workspace
  - persistence
---

# Saved Apartment Interests

## Scope

This page maps the accepted R-023 outcome for keeping explicitly resolved
apartment complexes as local user interests.

## Knowledge

R-023 is accepted and implemented. Its outcome is a preference-only saved list
in the configured local SQLite workspace: a user may
save an explicitly resolved complex, see it after a local restart, explicitly
select it for analysis, and remove the preference without deleting analysis
evidence. Saving, listing, or removing an interest does not acquire, refresh,
or preload source data or mutate active analysis/comparison state. Explicitly
selecting a saved interest changes only the current subject; it does not
automatically change periods, population/inclusion settings, or comparison
membership.

Identity evidence remains governed by [Apartment identity](../domain/apartment-identity.md)
and the normative requirement [R-023](../../docs/requirements/R-023-saved-apartment-interests.md).

## Graph connections

- Extends the local interface boundary in [R-020](../../docs/requirements/R-020-local-browser-analysis-workspace.md).
- Relates to comparison's explicit subject selection in [R-016](../../docs/requirements/R-016-apartment-comparison.md).
- Uses the local persistence boundary in [ADR-0004](../../docs/decisions/ADR-0004-sqlite-persistence-and-freshness.md).
- Is summarized in the [MVP knowledge map](mvp-knowledge-map.md).

## Requirements

- [R-023: Saved apartment interests](../../docs/requirements/R-023-saved-apartment-interests.md) — accepted and verified by deterministic persistence and web contracts.

## Decisions and open questions

- [ADR-0003: Official sources and apartment identity](../../docs/decisions/ADR-0003-official-sources-and-apartment-identity.md) constrains identity evidence.
- [ADR-0005: Local-web delivery stack](../../docs/decisions/ADR-0005-local-web-delivery-stack.md) constrains the local browser boundary.
- R-023 currently has no open questions.

## Evidence and interpretation risks

- A display name alone is unsafe evidence for a saved interest.
- Removing a preference must not be confused with deleting cached analysis evidence.

## Verify in the repository

[`SQLiteStore.save_interest`, `SQLiteStore.list_interests`, and
`SQLiteStore.remove_interest`](../../src/apt_analyzer/persistence.py) implement
the persisted preference boundary. The `/interests/save`, `/interests/select`,
and `/interests/remove` routes in [`web`](../../src/apt_analyzer/web/__init__.py)
provide the local UI boundary. Representative contracts are covered by
[`test_m3.py`](../../tests/test_m3.py) and [`test_web.py`](../../tests/test_web.py).

## Related pages

- [Apartment identity](../domain/apartment-identity.md)
- [Requirement map](requirement-map.md)
- [MVP knowledge map](mvp-knowledge-map.md)

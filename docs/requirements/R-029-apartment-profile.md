---
id: R-029
title: Persisted apartment-complex profile
status: accepted
priority: P1
created: 2026-09-08
updated: 2026-09-15
origin: User-approved apartment result profile direction
supersedes: []
superseded_by: null
related_requirements: [R-001, R-019, R-020, R-023, R-030, R-031]
related_decisions: [ADR-0015, ADR-0016]
---

# R-029: Persisted apartment-complex profile

## Intent

Give a single-apartment result useful, source-labelled complex facts without
confusing official complex inventory with transaction observations.

## Requirement

The single-apartment result shall present persisted K-APT complex profile
evidence and equivalent machine-readable context when available, while keeping
identity, provenance, inventory granularity, and unavailable states explicit.

## Acceptance criteria

- **AC-1:** A result shows the resolved complex name/address, total households,
  and optional K-APT buildings, use-approval date, highest floor, heating,
  hall type, builder, developer, management, and sale type; when approval date
  is known it also shows completed elapsed years/months and the as-of date.
- **AC-2:** When a verified exact inventory exists, it is the primary area-by-household table with exact areas, counts, shares, Building HUB provenance, collection time, and whole-complex scope. K-APT broad bands remain secondary reference evidence labelled as comparison bands.
- **AC-2a:** Without verified exact inventory, the result says exact composition is unverified and never presents K-APT broad bands as exact.
- **AC-3:** Exact transaction-observed area groups are separately labelled as
  eligible trades, never as household inventory or complete unit composition.
- **AC-4:** Missing or partial profile evidence remains usable and says what is
  unconfirmed, with an explicit K-APT basic-information refresh path; explicit
  refresh replaces records atomically and failed refresh preserves last-good
  evidence. Saved-interest selection and analysis remain offline.
- **AC-5:** Human and machine results expose source/fetched-time provenance,
  profile facts, household evidence, area bands, and observed-area evidence
  without contact fields or raw source payload.
- **AC-6:** The presentation is accessible and responsive at narrow widths.

## Constraints

- Do not infer exact unit-type household counts from transactions or area labels.
- Keep K-APT broad area-band inventory distinct from transaction observations.
- Derived age uses completed calendar months as of the current workspace as-of
  date; future or missing approval dates have no derived age.
- Profile acquisition occurs only during explicit live selection or refresh;
  analysis and saved-interest selection must not call a source.
- Exclude telephone, fax, and homepage URL fields.

## Non-goals

- Exact per-type household inventory without an authoritative source.
- Automatic refresh, recommendations, maps, or profile redesign for comparison
  and screening.

## Verification

### Automated

- [Profile parsing and area-band validation](../../tests/test_m1.py) — AC-1, AC-2
- [Profile migration and round-trip persistence](../../tests/test_m3.py) — AC-4, AC-5
- [Selection, refresh, offline analysis, and result profile](../../tests/test_web.py) — AC-1, AC-3, AC-4, AC-5
- [Responsive profile result](../../tests/test_web_e2e.py) — AC-6

### Manual or data validation

None.

### Verification gaps

None.

## Open questions

- [OQ-010: Exact area-by-household inventory source](../open-questions.md#oq-010-exact-area-by-household-inventory-source)

## Related documentation

- [R-001: Apartment search](R-001-apartment-search.md)
- [R-019: Visible analysis context](R-019-analysis-context.md)
- [R-020: Local browser analysis workspace](R-020-local-browser-analysis-workspace.md)
- [R-023: Saved apartment interests](R-023-saved-apartment-interests.md)
- [ADR-0015: Source-labeled apartment profile](../decisions/ADR-0015-source-labeled-apartment-profile.md)

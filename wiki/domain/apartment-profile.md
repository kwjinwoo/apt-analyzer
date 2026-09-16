---
title: Apartment Profile
type: domain
role: topic
status: active
updated: 2026-09-15
aliases:
  - Complex profile
  - K-APT basic information
tags:
  - profile
  - provenance
  - households
---

# Apartment Profile

## Scope

This page maps the source-labelled K-APT complex facts shown with a
single-apartment analysis result and their distinction from transaction evidence.

## Knowledge

[R-029](../../docs/requirements/R-029-apartment-profile.md) and
[ADR-0015](../../docs/decisions/ADR-0015-source-labeled-apartment-profile.md)
establish that optional K-APT facts are persisted with source and fetched time.
Official broad area-band household inventory is separate from exact or grouped
areas observed in eligible transactions; observed counts are trades, not proof
of complete household inventory. Missing fields remain unconfirmed and do not
trigger acquisition during saved-interest selection or analysis.
When approval is present, the result also derives completed elapsed years and
months as of the current workspace as-of date; missing or future approval dates
have no age.
Exact unit-area inventory is the explicitly refreshed [Exact area inventory](exact-area-inventory.md), separate from profile bands and transaction observations. When verified, it is the primary exact composition table in the result; K-APT bands remain collapsed comparison references.

## Graph connections

- Identity and address evidence come from [Apartment identity](apartment-identity.md).
- Profile provenance travels with [Analysis context](analysis-context.md).
- Local persistence is used by [Saved apartment interests](../project/saved-apartment-interests.md).
- Transaction eligibility is described by [Transaction population](../data/transaction-population.md).

## Requirements

- [R-029: Persisted apartment-complex profile](../../docs/requirements/R-029-apartment-profile.md)
- [R-019: Visible analysis context](../../docs/requirements/R-019-analysis-context.md)
- [R-020: Local browser analysis workspace](../../docs/requirements/R-020-local-browser-analysis-workspace.md)
- [R-023: Saved apartment interests](../../docs/requirements/R-023-saved-apartment-interests.md)

## Decisions and open questions

- [ADR-0015: Source-labeled persisted apartment profile](../../docs/decisions/ADR-0015-source-labeled-apartment-profile.md)
- [ADR-0003: Official sources and apartment identity](../../docs/decisions/ADR-0003-official-sources-and-apartment-identity.md)
- [OQ-001: Stable apartment identity](../../docs/open-questions.md#oq-001-stable-apartment-identity)
- [ADR-0016: Building HUB exact-area inventory](../../docs/decisions/ADR-0016-exact-area-inventory-source.md)
- [ADR-0017: Verified exact inventory denominator](../../docs/decisions/ADR-0017-area-inventory-turnover-denominator.md)

## Evidence and interpretation risks

- K-APT area bands do not establish exact 49㎡/59㎡-style household counts.
- Transaction-observed areas are time-bound eligible trades and may omit units.
- Profile freshness and source scope matter when interpreting displayed facts.
- The Wiki is synthesis; requirements, ADRs, code, and tests are authoritative.

## Verify in the repository

[`ApartmentProfile` and `ApartmentDataService.resolve`](../../src/apt_analyzer/apartment_data.py)
parse the optional profile. [`SQLiteStore.save_profile_and_household` and
`load_profile`](../../src/apt_analyzer/persistence.py) persist source-labelled
evidence. The single-analysis profile is assembled in
[`web`](../../src/apt_analyzer/web/__init__.py); representative coverage is in
[`test_m1.py`](../../tests/test_m1.py), [`test_m3.py`](../../tests/test_m3.py),
[`test_web.py`](../../tests/test_web.py), and [`test_web_e2e.py`](../../tests/test_web_e2e.py).

## Related pages

- [Analysis context](analysis-context.md)
- [Apartment identity](apartment-identity.md)
- [Saved apartment interests](../project/saved-apartment-interests.md)
- [Transaction population](../data/transaction-population.md)

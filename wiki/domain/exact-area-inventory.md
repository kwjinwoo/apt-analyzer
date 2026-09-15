---
title: Exact Area Inventory
type: domain
role: topic
status: active
updated: 2026-09-12
aliases:
  - Building HUB inventory
tags:
  - households
  - exclusive-area
---

# Exact Area Inventory

## Scope

Exact exclusive-area household counts collected from the Building HUB register for one selected K-APT complex.

## Knowledge

[R-030](../../docs/requirements/R-030-exact-area-inventory.md) and [ADR-0016](../../docs/decisions/ADR-0016-exact-area-inventory-source.md) establish explicit refresh, conservative graph scope, Decimal preservation, K-APT reconciliation, and separate last-good/latest-attempt evidence. Transactions and K-APT broad bands do not substitute for this inventory.

## Graph connections

- Identity mapping depends on [Apartment identity](apartment-identity.md).
- Display context belongs to [Apartment profile](apartment-profile.md).
- Raw transaction areas remain governed by [Area group](area-group.md).

## Requirements

- [R-030](../../docs/requirements/R-030-exact-area-inventory.md)
- [R-031](../../docs/requirements/R-031-area-group-inventory-denominator.md)
- [R-029](../../docs/requirements/R-029-apartment-profile.md)

## Decisions and open questions

- [ADR-0016](../../docs/decisions/ADR-0016-exact-area-inventory-source.md)
- [ADR-0017](../../docs/decisions/ADR-0017-area-inventory-turnover-denominator.md)
- [OQ-010 resolution](../../docs/open-questions.md#oq-010-exact-area-by-household-inventory-source)

## Evidence and interpretation risks

Current query collection time is not an effective date. Incomplete scope, malformed units, and source failures remain non-verified. Manual 2026-09-09 replays are current-query evidence, not historical claims.

## Verify in the repository

Verify source and normalization behavior in [`building_hub.py`](../../src/apt_analyzer/building_hub.py), persistence in [`persistence.py`](../../src/apt_analyzer/persistence.py), and representative coverage in [`test_building_hub.py`](../../tests/test_building_hub.py), [`test_inventory_persistence.py`](../../tests/test_inventory_persistence.py), and [`test_web_inventory.py`](../../tests/test_web_inventory.py).

## Related pages

- [Apartment identity](apartment-identity.md)
- [Apartment profile](apartment-profile.md)
- [Area group](area-group.md)

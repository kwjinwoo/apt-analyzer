---
id: R-030
title: Exact exclusive-area household inventory
status: accepted
priority: P1
created: 2026-09-09
updated: 2026-09-15
origin: User-approved OQ-010 resolution
supersedes: []
superseded_by: null
related_requirements: [R-005, R-019, R-029, R-031]
related_decisions: [ADR-0016, ADR-0017]
---

# R-030: Exact exclusive-area household inventory

## Intent

Show exact exclusive-area household composition when official register scope and unit evidence support it.

## Requirement

Provide an explicit refresh that collects, validates, persists, and displays exact exclusive-area counts independently of transaction analysis.

## Acceptance criteria

- **AC-1:** Verified results display exact Decimal areas, counts, percentages, source, collection time, and whole-complex scope; exports contain aggregates only.
- **AC-2:** Identity, pagination, parent graphs, attached lots, joins, and area semantics fail closed on ambiguity, contradiction, malformed data, or incomplete coverage.
- **AC-3:** K-APT total and available broad bands reconcile independently; mismatch, missing total, empty, partial, mapping-required, and unavailable states remain visible.
- **AC-4:** Failed or partial refreshes preserve the last verified snapshot and expose the latest attempt separately; selection, analysis, and export remain offline.
- **AC-5:** Common-area and non-residential records contribute nothing; raw unit identifiers are never shown.

## Constraints

- Building HUB is primary; K-APT supplies identity, total, and broad-band reconciliation evidence.
- `crtnDay` is a generation date, not an effective date. No historical completeness or ownership guarantee is made.
- Inventory is not transaction-derived; a verified snapshot may supply the matching denominator for a selected single-apartment area turnover under [R-031](R-031-area-group-inventory-denominator.md).
- Exact Decimal precision is preserved without rounding to types.

## Non-goals

- Historical inventory reconstruction, lifecycle inference, all-complex inventory-derived turnover, automatic refresh, permit API mixing, grouping UX redesign, or comparison redesign.

## Verification

### Automated

- [Building HUB contract and normalization tests](../../tests/test_building_hub.py) — AC-2, AC-3.
- [Acquisition metadata tests](../../tests/test_acquisition.py) — AC-2.
- [Inventory persistence tests](../../tests/test_inventory_persistence.py) — AC-1, AC-4.
- [Web inventory tests](../../tests/test_web_inventory.py) — AC-1, AC-4, AC-5.
- [`test_verified_inventory_derives_floor_group_denominator_and_provenance`](../../tests/test_web.py) — verified exact composition is presented with source, collection time, and exact-area shares; K-APT bands remain reference evidence.
- [Web integration tests](../../tests/test_web.py) — AC-4.

### Manual or data validation

On 2026-09-09, complete current captured responses produced: 구의현대2단지 1,606 verified (84.75㎡ 216, 84.86㎡ 216, 84.88㎡ 216, 84.91㎡ 958); 구의현대6단지 421 versus K-APT 423, mismatch; 현대3 127 (59.92㎡ 71, 83.71㎡ 56). These are current-query results, not historical as-of claims.

### Verification gaps

No browser-level refresh assertion exists yet. Repeat live validation after source schema or registration changes.

## Open questions

None. Empirical limitations are follow-up validation under [ADR-0016](../decisions/ADR-0016-exact-area-inventory-source.md).

## Related documentation

- [ADR-0016](../decisions/ADR-0016-exact-area-inventory-source.md)
- [R-029](R-029-apartment-profile.md)

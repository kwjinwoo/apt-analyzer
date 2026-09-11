---
id: ADR-0016
title: Building HUB exact-area inventory
status: accepted
date: 2026-09-09
supersedes: []
superseded_by: null
related_requirements: [R-030, R-029]
---

# ADR-0016: Building HUB exact-area inventory

## Status

Accepted

## Context

K-APT supplies identity, total households, and broad bands, while transactions cannot prove complete inventory. The official [Building HUB building-register API](https://www.data.go.kr/data/15134735/openapi.do) supplies unit-register scope, parent relationships, attached-lot evidence, and area semantics.

## Decision

Use Building HUB for explicitly refreshed exact exclusive-area inventory. Resolve K-APT parcels through official parent and attached-lot evidence, accept only code-validated residential exclusive areas with finite Decimal values, reconcile counts and available bands against persisted K-APT evidence, and retain last verified snapshots separately from latest attempts.

## Rationale

This separates current source-query inventory from broad K-APT bands and transaction observations while keeping identity and pagination uncertainty visible.

## Alternatives considered

### K-APT bands only

Rejected because broad bands cannot provide exact area counts.

### Transaction inference

Rejected because trades are incomplete observations and would distort household counts and denominators.

### Housing-permit API

Rejected because the approved register path provides stronger scope and parent-graph evidence for this feature.

## Consequences

### Positive

- Exact areas retain source precision and independently reconciled counts.
- Ambiguous identity and incomplete coverage remain visible.
- Failed refreshes preserve verified evidence.

### Negative

- Some complexes remain partial, mismatched, or mapping-required.
- A collection is current source evidence and does not establish historical or effective ownership state.

### Follow-up

- Repeat bounded live validation after source changes.
- Add browser-level refresh verification and keep synthetic fixtures distinct from live responses.

## Related documentation

- [R-030](../requirements/R-030-exact-area-inventory.md)
- [ADR-0003](ADR-0003-official-sources-and-apartment-identity.md)

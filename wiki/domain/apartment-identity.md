---
title: Apartment Identity
type: domain
role: topic
status: active
updated: 2026-08-22
aliases:
  - Complex identity
  - Internal apartment ID
tags:
  - identity
  - normalization
---

# Apartment Identity

## Scope

Apartment identity is the relationship between a real apartment complex, source-specific records, and the stable analysis subject used throughout apt-analyzer.

## Knowledge

A display name cannot establish identity because names can be duplicated, normalized differently, or changed. Transaction and apartment-metadata sources may also lack a shared canonical identifier. Identity resolution therefore sits between source acquisition and every downstream population or comparison.

[ADR-0003](../../docs/decisions/ADR-0003-official-sources-and-apartment-identity.md) accepts K-APT source ID plus legal-dong, address, and normalized-name values as initial evidence. Only an explicitly selected single candidate receives a project identity; sparse or ambiguous evidence never becomes an automatic cross-source match.

An identity error has a larger blast radius than an ordinary parsing error: it can merge transactions from different complexes, fragment one complex, attach the wrong household denominator, and invalidate comparisons while still producing plausible metrics.

## Graph connections

- Defines the apartment boundary used by [Transaction population](../data/transaction-population.md).
- Determines which metadata and household evidence reaches [Turnover rate](../metrics/turnover-rate.md).
- Constrains the validity of the [MVP knowledge map](../project/mvp-knowledge-map.md).
- Depends on source traceability described by [Transaction quality](../data/transaction-quality.md).

## Requirements

- [R-001: Apartment search](../../docs/requirements/R-001-apartment-search.md)
- [R-002: Sale transaction retrieval](../../docs/requirements/R-002-transaction-retrieval.md)
- [R-016: Apartment comparison](../../docs/requirements/R-016-apartment-comparison.md)

## Decisions and open questions

- [OQ-001: Stable apartment identity](../../docs/open-questions.md#oq-001-stable-apartment-identity)
- ADR-0003 resolves OQ-001 for the initial version; renamed-complex continuity remains a limitation.

## Evidence and interpretation risks

- Same-name complexes can exist in different locations.
- Address fields may use legal-dong, lot-number, or road-name representations.
- A source-specific identifier may be stable only within that source.
- A renamed complex may need continuity with historical transactions.
- Household metadata attached to the wrong identity corrupts normalized liquidity measures.

## Verify in the repository

[`ApartmentCandidate`, `ApartmentDataService.resolve`, and `ApartmentDataService.retrieve`](../../src/apt_analyzer/apartment_data.py) implement enrichment and evidence matching. [`test_m1.py`](../../tests/test_m1.py) verifies ambiguity, resolution, and mismatch rejection. Opt-in live validation on 2026-08-22 found 262 Seoul candidates for `현대`, then resolved and retrieved 구의현대2단지, 구의현대6단지, and 현대3 using K-APT legal-dong and full-address evidence.

## Related pages

- [Transaction population](../data/transaction-population.md)
- [Transaction quality](../data/transaction-quality.md)
- [Analysis context](analysis-context.md)
- [Open decision map](../project/open-decision-map.md)

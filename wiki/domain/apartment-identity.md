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

Candidate matching evidence includes legal-dong code, lot number, road-name address, and normalized complex name. These inputs are evidence, not an accepted matching algorithm. Ambiguous evidence must remain visible rather than being converted into a confident match.

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
- No identity-strategy ADR has been accepted yet.

## Evidence and interpretation risks

- Same-name complexes can exist in different locations.
- Address fields may use legal-dong, lot-number, or road-name representations.
- A source-specific identifier may be stable only within that source.
- A renamed complex may need continuity with historical transactions.
- Household metadata attached to the wrong identity corrupts normalized liquidity measures.

## Verify in the repository

[`Apartment`](../../src/apt_analyzer/domain.py) provides a source-independent internal ID and display name for the analysis boundary, and [`test_domain.py`](../../tests/test_domain.py) verifies its use in analysis context. Identity resolution, ambiguity results, and real-source validation remain unimplemented.

## Related pages

- [Transaction population](../data/transaction-population.md)
- [Transaction quality](../data/transaction-quality.md)
- [Analysis context](analysis-context.md)
- [Open decision map](../project/open-decision-map.md)

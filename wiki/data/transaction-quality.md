---
title: Transaction Quality
type: data
role: topic
status: active
updated: 2026-08-22
aliases:
  - Transaction data quality
tags:
  - source-traceability
  - corrections
---

# Transaction Quality

## Scope

Transaction quality covers the source and normalization conditions that determine whether records can support a reproducible analysis population.

## Knowledge

Quality begins with explicit source outcomes: valid records, a valid empty response, availability failure, and parsing failure must not collapse into one state. Normalization preserves analytical meaning for contract date, price, exclusive area, transaction type, and cancellation while retaining traceability to relevant source values.

Duplicates and cancellations are temporal data problems, not only import-time problems. Repeated queries must not multiply one transaction, while later source corrections may legitimately change a prior result. Caching reduces repeated calls but cannot make freshness invisible.

Direct transactions and unusual prices require inspection because they can alter both activity and price evidence. Neither category is automatically invalid. If these topics accumulate independent sources, decisions, and tests, this page should remain a hub while they split into concept pages under the decomposition rules.

## Graph connections

- Supports reliable [Apartment identity](../domain/apartment-identity.md).
- Determines confidence in [Transaction population](transaction-population.md).
- Changes the price observations described by [Price-series evidence](price-series-evidence.md).
- Affects all three initial metric pages: [Turnover rate](../metrics/turnover-rate.md), [Transaction retention rate](../metrics/transaction-retention-rate.md), and [Maximum drawdown](../metrics/maximum-drawdown.md).
- Is a cross-cutting risk in the [MVP knowledge map](../project/mvp-knowledge-map.md).

## Requirements

- [R-002: Sale transaction retrieval](../../docs/requirements/R-002-transaction-retrieval.md)
- [R-017: Transaction inclusion policy](../../docs/requirements/R-017-transaction-inclusion-policy.md)
- [R-018: Outlier-impact inspection](../../docs/requirements/R-018-outlier-impact.md)

## Decisions and open questions

- [OQ-006: Default direct-transaction policy](../../docs/open-questions.md#oq-006-default-direct-transaction-policy)
- [OQ-007: Outlier comparison policy](../../docs/open-questions.md#oq-007-outlier-comparison-policy)
- [ADR-0003](../../docs/decisions/ADR-0003-official-sources-and-apartment-identity.md) accepts the official sources and initial duplicate, cache provenance, retry, and identity policies.

## Evidence and interpretation risks

- A record may be corrected after initial acquisition.
- Cancellation indicators may arrive separately or later than the original record.
- A duplicate constraint can be too weak and admit copies or too strong and collapse legitimate trades.
- Retry behavior can create partial coverage if failures are hidden.
- Exact values can be altered by parsing or presentation conversion.

## Verify in the repository

[`NormalizedTransaction`](../../src/apt_analyzer/domain.py) preserves normalized values and source traceability. [`DataGoKrClient`](../../src/apt_analyzer/acquisition.py) exposes outcomes, bounded retries, and cache provenance; [`test_acquisition.py`](../../tests/test_acquisition.py) and [`test_m1.py`](../../tests/test_m1.py) verify encoded-key handling, empty data, normalization, exact-row deduplication, and cache visibility.

## Related pages

- [Transaction population](transaction-population.md)
- [Price-series evidence](price-series-evidence.md)
- [Apartment identity](../domain/apartment-identity.md)
- [Open decision map](../project/open-decision-map.md)

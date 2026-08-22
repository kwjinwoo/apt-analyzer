---
title: Transaction Population
type: data
role: topic
status: active
updated: 2026-08-22
aliases:
  - Eligible transactions
  - Analysis population
tags:
  - filtering
  - reproducibility
---

# Transaction Population

## Scope

Transaction population is the set of normalized sale transactions eligible for one calculation after all subject, time, area, and inclusion conditions are applied.

## Knowledge

Acquired records are not automatically analytical evidence. The population is formed by resolving the apartment identity, enforcing date boundaries, selecting all areas or one area group, and applying explicit cancellation, transaction-type, and optional outlier policies.

Population construction belongs before metric calculation so volume, price, turnover, retention, and MDD cannot silently use different records. Raw and eligible counts remain distinct. A valid empty population must also remain distinguishable from source failure, parsing failure, or incomplete acquisition.

Cancelled transactions are excluded from the default analytical population but remain inspectable. The default treatment of direct transactions and any outlier comparison remain unresolved.

## Graph connections

- Resolves its subject through [Apartment identity](../domain/apartment-identity.md).
- Selects market segments through [Area group](../domain/area-group.md).
- Is fully described by [Analysis context](../domain/analysis-context.md).
- Depends on source reliability from [Transaction quality](transaction-quality.md).
- Supplies counts to [Turnover rate](../metrics/turnover-rate.md) and [Transaction retention rate](../metrics/transaction-retention-rate.md).
- Supplies observations to [Price-series evidence](price-series-evidence.md) and [Maximum drawdown](../metrics/maximum-drawdown.md).

## Requirements

- [R-002: Sale transaction retrieval](../../docs/requirements/R-002-transaction-retrieval.md)
- [R-003: Transaction query period](../../docs/requirements/R-003-query-period.md)
- [R-006: Area-filtered analysis](../../docs/requirements/R-006-area-filter.md)
- [R-017: Transaction inclusion policy](../../docs/requirements/R-017-transaction-inclusion-policy.md)

## Decisions and open questions

- [OQ-006: Default direct-transaction policy](../../docs/open-questions.md#oq-006-default-direct-transaction-policy)
- [OQ-007: Outlier comparison policy](../../docs/open-questions.md#oq-007-outlier-comparison-policy)
- Cancelled transactions are excluded by the accepted requirement and metric policy; no additional ADR exists yet.

## Evidence and interpretation risks

- An empty result can mean no eligible trades or a failed acquisition unless failures are explicit.
- Source corrections can change historical membership.
- Different filters across metrics invalidate combined interpretation.
- Outlier removal can conceal legitimate transactions.
- Transaction-type values may be absent or source-specific.

## Verify in the repository

[`transaction_volume`](../../src/apt_analyzer/analytics.py) composes apartment, period, area, cancellation, and transaction-type conditions over immutable normalized records. [`test_transaction_volume.py`](../../tests/test_transaction_volume.py) verifies raw-versus-eligible counts and a valid empty population without external API access. Acquisition and parsing failures and shared-population behavior across other metrics remain unimplemented.

## Related pages

- [Transaction quality](transaction-quality.md)
- [Analysis context](../domain/analysis-context.md)
- [Requirement map](../project/requirement-map.md)
- [MVP knowledge map](../project/mvp-knowledge-map.md)

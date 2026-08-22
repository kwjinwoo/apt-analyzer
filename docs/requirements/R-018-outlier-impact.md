---
id: R-018
title: Outlier-impact inspection
status: accepted
priority: P2
created: 2026-08-21
updated: 2026-08-21
origin: "Initial requirements R16"
supersedes: []
superseded_by: null
related_requirements: [R-007, R-011, R-017, R-019]
related_decisions: []
---

# R-018: Outlier-impact inspection

## Intent

Unusual transaction prices can materially alter summaries and MDD, but automatic removal can also conceal valid market evidence.

## Requirement

The user can inspect whether an explicit candidate outlier policy materially changes analysis results by comparing inclusive and policy-filtered results.

## Acceptance criteria

- **AC-1:** The inclusive result remains available as a reference.
- **AC-2:** The candidate exclusion rule is explicit and reproducible.
- **AC-3:** Excluded records remain inspectable.
- **AC-4:** Both results use otherwise identical analysis context.
- **AC-5:** The system does not imply that a statistical outlier is an invalid transaction.

## Constraints

- No automatic outlier-removal default is accepted for the initial MVP.

## Non-goals

- Universal fraud detection or automatic correction of public transaction data.

## Verification

### Automated

Not established yet.

### Manual or data validation

- Manually inspect excluded transactions and metric deltas during policy evaluation.

### Verification gaps

- AC-1 through AC-5 have no implementation evidence yet.

## Open questions

- [OQ-007: Outlier comparison policy](../open-questions.md#oq-007-outlier-comparison-policy)

## Related documentation

- [Outlier](../domain/glossary.md#outlier)
- [Maximum drawdown](../domain/metrics.md#maximum-drawdown)

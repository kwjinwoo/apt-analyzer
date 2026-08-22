---
id: R-019
title: Visible analysis context
status: accepted
priority: P0
created: 2026-08-21
updated: 2026-08-21
origin: "Initial requirements R17"
supersedes: []
superseded_by: null
related_requirements: [R-003, R-006, R-008, R-010, R-011, R-016, R-017]
related_decisions: []
---

# R-019: Visible analysis context

## Intent

A metric without its population and calculation conditions is not reproducible and can be misinterpreted.

## Requirement

The user can inspect the analysis conditions used to produce every result.

## Acceptance criteria

- **AC-1:** The selected apartment identity and display information are available.
- **AC-2:** Area selection and overall analysis interval are available.
- **AC-3:** Metric-specific turnover, baseline, comparison, and MDD periods are available when applicable.
- **AC-4:** Price-series aggregation method is available for price-derived metrics.
- **AC-5:** Transaction inclusion and outlier policies are available.
- **AC-6:** Relevant household-count scope and source evidence are available for turnover.
- **AC-7:** Machine-readable output retains equivalent context to human-readable output.

## Constraints

- Context must travel with a result rather than relying on session state or presentation defaults.

## Non-goals

- Exposing internal objects, storage schemas, or source response structures to users.

## Verification

### Automated

Not established yet.

### Manual or data validation

- Confirm that a reported result can be reproduced from its visible context and source data.

### Verification gaps

- AC-1 through AC-7 have no implementation evidence yet.

## Open questions

- [OQ-004: Partial-year annualization](../open-questions.md#oq-004-partial-year-annualization)
- [OQ-006: Default direct-transaction policy](../open-questions.md#oq-006-default-direct-transaction-policy)
- [OQ-008: Area-filtered turnover presentation](../open-questions.md#oq-008-area-filtered-turnover-presentation)

## Related documentation

- [Analysis context](../domain/glossary.md#analysis-context)
- [Shared metric rules](../domain/metrics.md#shared-rules)

---
id: R-009
title: Annual turnover rate
status: accepted
priority: P0
created: 2026-08-21
updated: 2026-08-21
origin: "Initial requirements R8-1"
supersedes: []
superseded_by: null
related_requirements: [R-008, R-019]
related_decisions: []
---

# R-009: Annual turnover rate

## Intent

Users need to inspect how normalized transaction activity changes from year to year, not only as one multi-year average.

## Requirement

The system reports turnover for individual calendar years using the same denominator scope and transaction inclusion semantics as the selected turnover analysis.

## Acceptance criteria

- **AC-1:** Each complete represented calendar year has its own turnover result.
- **AC-2:** Each result uses that year's eligible transaction count.
- **AC-3:** Denominator scope and inclusion policy are consistent and visible.
- **AC-4:** Partial-year data is not presented as full-year turnover without an explicit annualization policy.

## Constraints

- Year-to-year comparison requires consistent household-count scope or visible denominator changes.

## Non-goals

- Automatically interpreting the cause of turnover changes.

## Verification

### Automated

Not established yet.

### Manual or data validation

None.

### Verification gaps

- AC-1 through AC-4 have no implementation evidence yet.

## Open questions

- [OQ-004: Partial-year annualization](../open-questions.md#oq-004-partial-year-annualization)

## Related documentation

- [Annual turnover rate](../domain/metrics.md#annual-turnover-rate)
- [Multi-year turnover requirement](R-008-turnover-rate.md)

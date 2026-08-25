---
id: R-014
title: Price visualization
status: accepted
priority: P0
created: 2026-08-21
updated: 2026-08-24
origin: "Initial requirements R12"
supersedes: []
superseded_by: null
related_requirements: [R-011, R-012, R-019]
related_decisions: [ADR-0005]
---

# R-014: Price visualization

## Intent

Users need to inspect the price observations behind summary statistics and maximum drawdown.

## Requirement

The user can view the representative transaction-price series over time, with monthly median eligible price as the initial default.

## Acceptance criteria

- **AC-1:** Every plotted value identifies its period and aggregation method.
- **AC-2:** The visualization uses the active apartment, area, date interval, and inclusion policy.
- **AC-3:** Months with no observed eligible price are distinguishable from observed values.
- **AC-4:** When MDD is present, its peak and trough can be identified on the same series.

## Constraints

- Visual continuity must not imply observed prices in missing months.

## Non-goals

- Interpolating a continuous apartment valuation curve.

## Verification

### Automated

Observed monthly median and MDD semantics are covered by [tests/test_m2.py](../../tests/test_m2.py); [frontend chart tests](../../frontend/src/main.test.ts) preserve missing-month gaps and MDD markers, while [web contract tests](../../tests/test_web.py) verify underlying deterministic values and context. The [Chromium flow](../../tests/test_web_e2e.py) verifies the rendered price canvas and underlying table after the HTMX update/analysis interaction.

### Manual or data validation

- On 2026-08-26, in-app browser QA confirmed post-HTMX price chart rendering, accessible values, null gaps, and visible analysis/comparison context.

### Verification gaps

The deterministic browser baseline passes with installed Chromium: `uv run --locked pytest -m e2e tests/test_web_e2e.py -q` → `1 passed`. No R-014 acceptance-criterion gap remains; live real-source validation remains opt-in data validation.

## Open questions

- [OQ-003: Missing months in the price series](../open-questions.md#oq-003-missing-months-in-the-price-series)
- [OQ-009: Minimum evidence for monthly price observations](../open-questions.md#oq-009-minimum-evidence-for-monthly-price-observations)

## Related documentation

- [Monthly median price](../domain/metrics.md#monthly-median-price)
- [MDD interval requirement](R-012-mdd-interval.md)
- [ADR-0005: Local-web delivery stack](../decisions/ADR-0005-local-web-delivery-stack.md)

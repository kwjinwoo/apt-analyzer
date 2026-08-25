---
id: R-013
title: Transaction-volume visualization
status: accepted
priority: P0
created: 2026-08-21
updated: 2026-08-24
origin: "Initial requirements R11"
supersedes: []
superseded_by: null
related_requirements: [R-007, R-019]
related_decisions: [ADR-0005]
---

# R-013: Transaction-volume visualization

## Intent

Users need to inspect changes in transaction activity over time more quickly than a summary metric alone allows.

## Requirement

The user can view eligible transaction volume as a yearly or monthly time series.

## Acceptance criteria

- **AC-1:** Each visual observation corresponds to an explicit calendar period and transaction count.
- **AC-2:** The visualization uses the active analysis population and inclusion policy.
- **AC-3:** Missing, zero, and unavailable periods are not visually conflated.
- **AC-4:** Underlying values remain accessible without relying only on visual position.

## Constraints

- Visualization must not redefine aggregation or inclusion semantics.

## Non-goals

- Regional-scale screening and ranking.

## Verification

### Automated

Underlying aggregation is covered by [tests/test_transaction_volume.py](../../tests/test_transaction_volume.py); [frontend chart tests](../../frontend/src/main.test.ts) preserve explicit zero values and null unavailable gaps, while [web contract tests](../../tests/test_web.py) verify deterministic accessible result data and tables. The [Chromium flow](../../tests/test_web_e2e.py) verifies the rendered volume canvas and underlying table.

### Manual or data validation

- On 2026-08-26, in-app browser QA confirmed post-HTMX volume chart rendering, accessible underlying values, update-only rendering, comparison context/status, and no comparison-only empty charts.

### Verification gaps

The deterministic browser baseline passes with installed Chromium: `uv run --locked pytest -m e2e tests/test_web_e2e.py -q` → `1 passed`. No R-013 acceptance-criterion gap remains; live real-source validation remains opt-in data validation.

## Open questions

None.

## Related documentation

- [Transaction volume](../domain/metrics.md#transaction-volume)
- [Periodic aggregation requirement](R-007-periodic-aggregation.md)
- [ADR-0005: Local-web delivery stack](../decisions/ADR-0005-local-web-delivery-stack.md)

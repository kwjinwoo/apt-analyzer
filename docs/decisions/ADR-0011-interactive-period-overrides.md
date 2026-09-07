---
id: ADR-0011
title: Interactive completed-month period overrides
status: superseded
date: 2026-09-01
related_requirements: [R-024, R-025]
supersedes: []
superseded_by: ADR-0012
---

# ADR-0011: Interactive completed-month period overrides

## Status

Superseded by [ADR-0012](ADR-0012-direct-chart-preview.md).

## Context

Users need an explicit, reproducible way to choose completed calendar months from the volume chart.

## Decision

The single-apartment volume chart may prepare explicit whole-calendar-month metric overrides. Applying is explicit and uses the existing analysis editor; ordinary chart interaction has no calculation side effect.

## Rationale

Month snapping provides reproducible boundaries while preserving manual and accessible inputs.

## Consequences

Turnover and retention require completed contiguous 12-month windows and existing coverage rules. MDD may use any selected months. Arbitrary partial-year annualization remains unresolved under OQ-004.

## Alternatives considered

- Silent chart interaction was rejected because it would change calculations without explicit apply.

## Related sources

- [R-025](../requirements/R-025-chart-period-selection.md)
- [ADR-0012](ADR-0012-direct-chart-preview.md)
- [ADR-0010](ADR-0010-completed-month-rolling-analysis.md)

## Related documentation

- [R-025](../requirements/R-025-chart-period-selection.md)

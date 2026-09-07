---
id: ADR-0012
title: Direct non-mutating chart previews
status: superseded
date: 2026-09-03
supersedes: [ADR-0011]
superseded_by: ADR-0013
related_requirements: [R-026, R-019, R-024]
---

# ADR-0012: Direct non-mutating chart previews

## Status

Superseded by [ADR-0013](ADR-0013-duration-aware-chart-preview-turnover.md).

## Context

R-026 replaces button-gated chart period overrides with an exploratory monthly preview. Official analysis and export must remain authoritative.

## Decision

Direct volume-chart drags request a persisted-evidence-only preview after pointer release. The preview is non-mutating and does not update official metrics, editor values, or export state. Manual editor fields remain the only official override path.

## Rationale

This keeps exploration safe while exposing metric-specific evidence and unavailable states without hidden recalculation or source calls.

## Alternatives considered

### Alternative A: Button-gated chart overrides

Superseded by this direct preview because exploratory interaction should not mutate official analysis.

### Alternative B: Client-side metric calculation

Rejected because server-side authoritative evidence and validation must remain consistent.

## Consequences

### Positive

- Safe exploratory interaction and reproducible server-computed evidence.

### Negative

- A separate explicit manual workflow remains necessary to change official periods.

## Related documentation

- [R-026](../requirements/R-026-chart-preview.md)
- [ADR-0010](ADR-0010-completed-month-rolling-analysis.md)

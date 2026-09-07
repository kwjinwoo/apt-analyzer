---
id: ADR-0013
title: Duration-aware chart preview turnover
status: superseded
date: 2026-09-03
supersedes: [ADR-0012]
superseded_by: ADR-0014
related_requirements: [R-027, R-026, R-008]
---

# ADR-0013: Duration-aware chart preview turnover

## Status

Superseded by [ADR-0014](ADR-0014-chart-preview-retention-split.md).

## Context

R-027 extends the direct, accessible, non-mutating preview in R-026 to useful complete whole-month
selections while OQ-004 remains unresolved for arbitrary partial-year
annualization.

## Decision

Retain ADR-0012's direct drag, persisted-evidence-only, dismissal, and
non-mutation decisions. For a selected completed whole-month preview, use selected-period turnover for
12 months, a simple eligible-count-per-year-per-household annual average for
exact 12-month multiples, and cumulative eligible-count-per-household for all
other valid lengths. Label the method and unit explicitly. Retention remains
an adjacent 12-versus-12 comparison, and official analysis/export are unchanged.

## Rationale

This exposes transparent duration semantics without silently annualizing an
arbitrary partial year or mutating the authoritative result.

## Alternatives considered

### Alternative A: Keep all non-12 previews unavailable

Rejected because useful complete multi-year and cumulative evidence would be
hidden despite having deterministic semantics.

### Alternative B: Annualize every selected duration

Rejected because arbitrary partial-year annualization remains unresolved.

## Consequences

### Positive

- Multi-year previews expose an explicit annual-average method.
- Other durations remain visible as cumulative, non-annualized activity.

### Negative

- Preview labels and evidence vary by duration and must remain clear.
- The official analysis contract remains separate from preview behavior.

### Follow-up

- Revisit OQ-004 only through a separate product decision.

## Related documentation

- [R-027](../requirements/R-027-chart-preview-turnover.md)
- [ADR-0012](ADR-0012-direct-chart-preview.md)

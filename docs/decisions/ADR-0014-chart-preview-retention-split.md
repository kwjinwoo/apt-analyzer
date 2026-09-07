---
id: ADR-0014
title: Chart preview 24-month retention split
status: accepted
date: 2026-09-07
supersedes: [ADR-0013]
superseded_by: null
related_requirements: [R-028, R-027, R-010]
---

# ADR-0014: Chart preview 24-month retention split

## Status

Accepted

## Context

An exact 24-month direct chart selection naturally contains two calendar-year
windows. R-028 changes retention interpretation while carrying forward the
direct non-mutating interaction and duration-aware turnover decisions recorded
in superseded ADR-0012 and ADR-0013.

## Decision

For a 24-month completed selection, compare the final 12 months with the first
12 months. For 12 months, retain the selected-comparison plus immediately prior
baseline rule. Other lengths remain retention-unavailable.

## Rationale

The split provides an explicit, adjacent, non-overlapping year-over-year
comparison while preserving existing population, coverage, and zero-baseline
validity rules.

## Alternatives considered

### Alternative A: Keep every non-12 selection unavailable

Rejected because a 24-month selection already supplies two equal complete windows.

### Alternative B: Split every even duration

Rejected because it would invent unsupported retention semantics for other lengths.

## Consequences

### Positive

- 24-month previews expose both comparison and baseline periods clearly.

### Negative

- Preview evidence must distinguish the two windows from the selected range.

### Follow-up

- Preserve OQ-005's explicit zero-baseline policy.

## Related documentation

- [R-028](../requirements/R-028-chart-preview-retention-split.md)
- [ADR-0013](ADR-0013-duration-aware-chart-preview-turnover.md)

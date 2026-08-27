---
title: Regional relative analysis
type: project
role: topic
status: active
updated: 2026-08-27
aliases:
  - regional profile
  - peer-group profile
tags:
  - regional-analysis
  - distributions
  - percentiles
  - correlations
---

# Regional relative analysis

## Scope

M6 adds descriptive regional profiles downstream of existing comparable scalar metrics.

## Knowledge

The peer group is the explicit set of selected regions and resolved candidates under one
common analysis context. Each metric keeps its upstream unit and method. Missing values
are excluded independently, percentiles use empirical midranks, and correlations use
pairwise-complete Spearman midranks with visible sample counts. None of these outputs
assign investment quality or prediction.

## Graph connections

- Extends [Regional ingestion and screening](regional-ingestion-and-screening.md) by
  consuming its bounded evidence and scalar metric boundary.
- Preserves [Analysis context](../domain/analysis-context.md) across the peer group.
- Appears in the cross-cutting [Requirement map](requirement-map.md).

## Requirements

- [R-021 regional relative profile](../../docs/requirements/R-021-regional-relative-profile.md)

## Decisions and open questions

- [ADR-0007](../../docs/decisions/ADR-0007-regional-relative-analysis.md) accepts
  inclusive-linear distributions, empirical midrank percentiles, and pairwise Spearman
  correlation as descriptive methods.
- Existing liquidity open questions still control upstream values; this domain does not
  resolve or redefine them.

## Evidence and interpretation risks

The 2026-08-27 live validation covered 21 explicitly selected complexes across Seoul,
Busan, and Gyeonggi for 2022-2024. Retention was unavailable for three zero baselines;
other metrics were available for all 21. That sample verifies mechanics and surfaced
missingness, not national representativeness or future stability. Peer selection, sparse
transactions, area mix, complex size, and source corrections can materially change
distributions and correlations.

## Verify in the repository

Inspect [`regional_profile.py`](../../src/apt_analyzer/regional_profile.py), the metric
extraction boundary in [`regional_screening.py`](../../src/apt_analyzer/regional_screening.py),
and the `regional-profile` interface in [`cli.py`](../../src/apt_analyzer/cli.py).
Representative deterministic contracts are in [`test_m6.py`](../../tests/test_m6.py);
the bounded opt-in data validation is [`validate_m6_live.py`](../../scripts/validate_m6_live.py).

## Related pages

- [Regional ingestion and screening](regional-ingestion-and-screening.md)
- [MVP knowledge map](mvp-knowledge-map.md)
- [Requirement map](requirement-map.md)
- [Analysis context](../domain/analysis-context.md)

---
id: R-021
title: Regional relative profile
status: accepted
priority: P2
created: 2026-08-27
updated: 2026-08-27
origin: "Roadmap M6 relative regional analysis"
supersedes: []
superseded_by: null
related_requirements: [R-015, R-016, R-019]
related_decisions: [ADR-0007]
---

# R-021: Regional relative profile

## Intent

Users need to understand where one apartment's observed metrics sit within an explicit,
comparable peer group without turning historical evidence into a recommendation or
mixing descriptive statistics into the liquidity metrics themselves.

## Requirement

The user can produce a reproducible descriptive profile of existing scalar metrics for
an explicitly selected regional peer group and common analysis context.

## Acceptance criteria

- **AC-1:** Output identifies the selected regions, candidates, periods, area and
  inclusion policies, metric units, and upstream calculation methods.
- **AC-2:** Each metric exposes available and missing counts, minimum, inclusive-linear
  quartiles, median, maximum, and each available candidate's empirical midrank
  percentile within the selected peer group.
- **AC-3:** Missing values are excluded independently per metric rather than imputed;
  each Spearman midrank correlation exposes its pairwise-complete sample count and is
  unavailable for fewer than two observations or a constant pair.
- **AC-4:** Valid-empty regional coverage, stale or failed coverage, and unavailable
  candidate metrics remain distinguishable.
- **AC-5:** Machine-readable and human-readable exports are equivalent and state that
  the profile is historical descriptive evidence, not an investment recommendation,
  and that a higher percentile does not mean better.

## Constraints

- The peer group and common analysis context must be explicit; results from different
  contexts cannot be pooled silently.
- Relative analysis consumes existing metric values and unavailable states. It does not
  redefine turnover, retention, MDD, price, area, or transaction-count semantics.
- Correlation is descriptive and does not establish causation, stability, or predictive
  value.

## Non-goals

- Composite scores, recommendation ranking, prediction, or fair-value estimation.
- Nationwide transaction-history preload or automatic peer-group selection.
- Rental, nearby-complex, or complex-characteristic domains.

## Verification

### Automated

- [`test_profile_exposes_distribution_midrank_percentiles_and_pairwise_correlation`](../../tests/test_m6.py)
  covers AC-2, AC-3, and AC-5, including tied values and metric-specific missingness.
- [`test_profile_marks_empty_and_constant_pairwise_evidence_unavailable`](../../tests/test_m6.py)
  covers AC-3 and valid descriptive output with no available observations.
- [`test_real_m6_cli_json_and_text_are_equivalent`](../../tests/test_m6.py) covers AC-1,
  AC-4, and AC-5 through persisted regional evidence and the installed CLI.
- M5 coverage-state, common-context, and unavailable-metric contracts remain covered by
  [`test_m5.py`](../../tests/test_m5.py).

### Manual or data validation

`scripts/validate_m6_live.py --live` completed on 2026-08-27 for seven explicitly
selected complexes in each of Seoul, Busan, and Gyeonggi over 2022 through 2024. All 21
had price, area, transaction-count, turnover, and MDD observations; retention was
available for 18 and explicitly unavailable for three zero-transaction baselines. The
output reproduced per-region distributions, all pairwise sample counts, and combined
correlations without exposing credentials.

### Verification gaps

- The 21-complex sample validates mechanics and interpretation boundaries, not national
  representativeness or future-period stability.
- Source corrections can change historical observations on a later run.

## Open questions

None.

## Related documentation

- [Metric definitions](../domain/metrics.md#regional-relative-profile)
- [ADR-0007](../decisions/ADR-0007-regional-relative-analysis.md)
- [Roadmap M6](../roadmap.md#m6-broader-apartment-analysis)

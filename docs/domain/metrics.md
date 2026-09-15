# Metric Definitions

This document defines the user-facing meaning, required context, and interpretation limits of the initial analytics. Implementations and tests must be inspected to determine current behavior.

## Shared rules

Every metric result must retain or expose enough [analysis context](glossary.md#analysis-context) to make the result interpretable and reproducible.

The same selected apartment, area filter, date boundaries, and transaction inclusion policy must be applied consistently to all inputs of a calculation and to every apartment in a comparison.

Cancelled transactions are excluded from the default analytical population but remain inspectable. The default treatment of direct transactions and outliers is still unresolved; a result must not conceal the policy that was applied.

## Transaction volume

### Purpose

Describe how many eligible sale transactions occurred during a period.

### Definition

Transaction volume is the count of eligible normalized transactions in the requested calendar period and grouping.

### Initial aggregations

- Yearly count is required for the MVP.
- Monthly count is required to support price-series inspection and later visualization.
- Quarterly aggregation is a planned extension, not an initial contract.

### Interpretation constraints

Human displays use `%` for turnover, retention, and MDD; machine-readable
results retain the exact signed or unsigned ratio and its interpretation.

Raw counts are affected by complex size and must not be treated as normalized liquidity. A count is meaningful only with its area selection, date interval, and inclusion policy.

## Price summary

### Purpose

Summarize the distribution of eligible transaction prices within a period.

### Required statistics

- Arithmetic mean
- Median
- Maximum
- Minimum

### Interpretation constraints

Sparse periods, heterogeneous area types, direct transactions, cancellations, and unusual records can materially change these values. The analysis context must identify the population used.

## Turnover rate

### Purpose

Normalize transaction activity by apartment-complex size.

### Definition

```text
annualized eligible transaction count
--------------------------------------
applicable household count
```

For a multi-year interval, the initial candidate annualization is total eligible transactions divided by the duration expressed in years. The exact treatment of arbitrary partial years remains unresolved; [ADR-0010](../decisions/ADR-0010-completed-month-rolling-analysis.md) defines completed-month defaults without resolving that general question.

### Required context

- Turnover period and boundary semantics
- Eligible transaction count
- Annualization method
- Household count and its scope
- Area selection
- Transaction inclusion policy

### Interpretation constraints

Filtering transactions to an area group does not create an exact area-level turnover rate unless the denominator is the household count for that same area group. Until that denominator is available, distinguish whole-complex turnover from area-filtered transaction activity. For a single-apartment analysis, a verified Building HUB snapshot may provide that denominator by applying the active grouping policy to every exact inventory area; this is latest-query evidence, not a historical as-of inventory claim.

An exact 12-consecutive-completed-month window uses rolling-turnover semantics;
an adjacent completed 12-month baseline and comparison uses rolling-retention
semantics. The non-mutating chart preview extends this with [R-027](../requirements/R-027-chart-preview-turnover.md)
and [ADR-0013](../decisions/ADR-0013-duration-aware-chart-preview-turnover.md),
with retention interpretation updated by [R-028](../requirements/R-028-chart-preview-retention-split.md)
and [ADR-0014](../decisions/ADR-0014-chart-preview-retention-split.md):
12-month selections use rolling turnover, exact 12-month multiples use an
explicit annual average, and other whole-month selections are cumulative and
not annualized. Other arbitrary partial-year annualization remains unresolved.

## Annual turnover rate

Annual turnover uses one calendar year's eligible transaction count divided by the applicable household count. Partial-year values must not be presented as full-year turnover without an explicit and accepted annualization policy.

## Transaction retention rate

### Purpose

Measure how much transaction activity remains during a selected comparison period relative to a selected baseline period.

### Definition

```text
comparison-period annualized transaction count
----------------------------------------------
baseline-period annualized transaction count
```

### Required context

- Baseline period and annualized count
- Comparison period and annualized count
- Area selection
- Transaction inclusion policy

### Interpretation constraints

The result is relative to user-selected periods and is not an intrinsic property of the complex. A zero baseline cannot produce an ordinary percentage and requires an explicit result policy. The default completed-month windows and 12/24-month support thresholds are defined by [ADR-0010](../decisions/ADR-0010-completed-month-rolling-analysis.md).
For chart preview, [R-028](../requirements/R-028-chart-preview-retention-split.md) and [ADR-0014](../decisions/ADR-0014-chart-preview-retention-split.md) retain the 12-month selected-comparison plus preceding 12-month baseline, and split a 24-month selection into first-12 baseline and last-12 comparison; other lengths are unavailable. OQ-005 remains the governing zero-baseline question.

## Completed-month rolling analysis

The period-driven analysis contract uses the latest calendar month whose
boundaries are wholly contained in the selected overall interval as the anchor,
without searching backward for usable coverage. Default turnover uses the 12
consecutive calendar months ending at that anchor, with the entire span wholly
contained in the overall interval; default retention compares those months with
the immediately preceding 12 consecutive, non-overlapping months under
identical population and inclusion semantics, with the full 24-month span
wholly contained in the interval. Every required month
must have successful or valid-empty coverage; any missing, failed, or incomplete
month makes the default unavailable. For each completed chart month, a trailing
three-month arithmetic mean uses that month and the two immediately preceding
consecutive completed months, all wholly contained in the interval, as
supporting time-series evidence only. Partial
boundary months may be displayed explicitly but are excluded from rolling
windows; this does not define arbitrary partial-year annualization. Advanced
overrides remain subject to metric validity rules and may be explicitly
unavailable.

## Monthly median price

### Purpose

Reduce the effect of individual transaction noise when constructing a price series from irregular apartment transactions.

### Definition

For each calendar month, take the median price of eligible transactions in the selected apartment and area population.

### Interpretation constraints

A month with one transaction has that transaction as its median but carries little evidence about a market-clearing level. A month with no transactions has no observed price; an interpolation policy has not been accepted.

## Maximum drawdown

### Purpose

Describe the largest observed peak-to-trough decline in the selected representative price series.

### Initial default definition

1. Build the monthly median price series from eligible transactions.
2. For each observation, determine the highest preceding observed price.
3. Calculate the decline from that running peak.
4. Select the most negative decline and return its peak and trough observations.

```text
drawdown = trough price / peak price - 1
```

### Required result context

- MDD value
- Peak month and price
- Trough month and price
- Price aggregation method
- Area selection
- Analysis period
- Transaction inclusion policy

### Interpretation constraints

Apartment transactions are irregular and sparse. Long no-trade intervals, single-transaction months, heterogeneous units, direct transactions, cancellations, and unusual prices can produce a misleading drawdown. The treatment of missing months and minimum evidence thresholds requires further validation.

## Regional relative profile

### Purpose

Describe the observed distribution and relative position of existing scalar metrics
within an explicit regional peer group and common analysis context.

### Definition

For each metric, exclude unavailable values independently and report available and
missing counts, minimum, inclusive-linear quartiles, median, and maximum. A candidate's
empirical midrank percentile is:

```text
values below + 0.5 × tied values
--------------------------------
        available values
```

Pairwise relationships use Spearman correlation over midranks and expose the number of
candidates for which both metrics are available. Fewer than two paired observations or
a constant paired series produces an unavailable correlation rather than a numeric
substitute.

### Interpretation constraints

Percentiles apply only to the displayed peer group and context. Higher does not mean
better, and correlation does not imply causation, stability, prediction, or investment
quality. Missing values, small samples, peer selection, transaction sparsity, area mix,
complex size, and source corrections can materially change the result.

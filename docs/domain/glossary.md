# Domain Glossary

This glossary defines how apt-analyzer uses domain terms. It does not prescribe code-level names or data structures.

## Analysis context

The complete set of conditions required to interpret and reproduce an analysis result. It includes the apartment, area selection, analysis period, metric-specific periods, price aggregation method, and transaction inclusion policy.

## Analysis period

The date interval whose transactions are eligible for an analysis. A metric may additionally define a baseline period, comparison period, or turnover period within the available data range.

## Apartment complex

A residential apartment development treated as one analysis subject. A complex must not be identified by display name alone because names can be duplicated, changed, or represented differently across data sources.

## Apartment identity

The project's stable representation of an apartment complex and the evidence used to match records from different sources to it. Candidate matching evidence includes legal-dong code, lot number, road-name address, and normalized complex name. The final identity policy is unresolved.

## Area-filtered transaction activity

Transaction activity calculated after filtering to an area group. Unless the household count for that area group is known, it must not be described as an exact area-level turnover rate.

## Area group

A market-facing grouping of similar exclusive-area values used to define an analysis population. Grouping never replaces the raw exclusive-area value. The initial grouping rule remains subject to validation against real complexes.

## Baseline period

The reference period used as the denominator of the transaction retention rate.

## Brokered transaction

A transaction reported as involving a real-estate broker rather than a direct transaction. Source-specific values require normalization before analysis.

## Cancelled transaction

A reported transaction that was subsequently cancelled or released. Cancellation data must remain identifiable so the inclusion policy can exclude or inspect it reproducibly.

## Comparison period

The period whose annualized transaction activity is compared with the baseline period for transaction retention.

## Contract date

The date on which a reported sale contract was made. It is the default event date for time-based transaction analysis.

## Direct transaction

A transaction reported as occurring without a broker. Direct transactions may have different data-quality characteristics and must be distinguishable by the inclusion policy.

## Empirical midrank percentile

The relative position of an observed metric within an explicit peer group, calculated as the number of available values below it plus half the number tied with it, divided by the number of available values. It has no inherent favorable direction.

## Exclusive area

The private floor area associated with a transaction, measured in square metres. The source value is preserved even when a derived area group is assigned.

## Household count

The number of residential households in an apartment complex. Whole-complex turnover uses the total household count as its denominator. Exact area-level turnover requires an area-specific household count.

## Internal apartment ID

A stable identifier assigned by apt-analyzer after resolving an apartment complex across source-specific identities. It is not assumed to be provided by any one external source.

## Monthly median price

The median transaction price for eligible transactions contracted within a calendar month. It is the initial default price observation for maximum-drawdown analysis.

## Normalized transaction

A transaction represented in the project's domain vocabulary after parsing and normalizing source fields. Normalization does not erase the ability to trace relevant values back to source data.

## Outlier

A transaction whose value may materially distort an aggregate or price series. The project does not assume that a statistical anomaly is invalid. Automatic exclusion is outside the initial MVP until an explicit policy is validated.

## Price series

An ordered sequence of representative price observations. For the initial MDD metric, the candidate default is a monthly median series. The treatment of months with no eligible transactions remains unresolved.

## Raw exclusive area

The exclusive-area value as normalized from the source record before market-facing grouping.

## Regional peer group

The explicitly selected regions and resolved apartment candidates whose existing metrics are compared under one common analysis context. It is an analysis population, not an automatically inferred market or recommendation set.

## Spearman correlation

A descriptive correlation of paired midranks. In this project it uses only candidates for which both metrics are available and always carries that pairwise-complete sample count.

## Transaction inclusion policy

The explicit rules that determine which normalized transactions are eligible for a calculation, including cancellation status, transaction type, and any outlier treatment.

## Transaction retention rate

The comparison period's annualized transaction count divided by the baseline period's annualized transaction count. It describes how much transaction activity remained relative to the selected baseline.

## Turnover rate

Annualized eligible transaction count divided by the applicable household count. Until area-level household counts are available, the supported denominator is the whole-complex household count.

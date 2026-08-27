# Requirements

Requirements define externally meaningful outcomes and constraints. They do not describe the current implementation. Code and tests remain authoritative for current behavior.

Use [TEMPLATE.md](TEMPLATE.md) when adding a requirement.

## Status definitions

- `proposed`: under review and not yet part of the accepted product contract.
- `accepted`: an active product requirement.
- `deprecated`: retained for context but no longer targeted for new behavior.
- `superseded`: replaced by another requirement.
- `rejected`: considered and explicitly not adopted.

## Requirement catalog

| ID | Requirement | Status | Priority | Initial source |
|---|---|---|---|---|
| [R-001](R-001-apartment-search.md) | Apartment search | accepted | P0 | R1 |
| [R-002](R-002-transaction-retrieval.md) | Sale transaction retrieval | accepted | P0 | R2 |
| [R-003](R-003-query-period.md) | Transaction query period | accepted | P0 | R3 |
| [R-004](R-004-area-detection.md) | Available-area detection | accepted | P0 | R4 |
| [R-005](R-005-area-grouping.md) | Exclusive-area grouping | accepted | P0 | R5 |
| [R-006](R-006-area-filter.md) | Area-filtered analysis | accepted | P0 | R6 |
| [R-007](R-007-periodic-aggregation.md) | Periodic transaction aggregation | accepted | P0 | R7 |
| [R-008](R-008-turnover-rate.md) | Multi-year turnover rate | accepted | P0 | R8 |
| [R-009](R-009-annual-turnover-rate.md) | Annual turnover rate | accepted | P0 | R8-1 |
| [R-010](R-010-transaction-retention-rate.md) | Transaction retention rate | accepted | P0 | R9 |
| [R-011](R-011-maximum-drawdown.md) | Maximum drawdown | accepted | P0 | R10 |
| [R-012](R-012-mdd-interval.md) | Maximum-drawdown interval | accepted | P0 | R10-1 |
| [R-013](R-013-transaction-volume-visualization.md) | Transaction-volume visualization | accepted | P0 | R11 |
| [R-014](R-014-price-visualization.md) | Price visualization | accepted | P0 | R12 |
| [R-015](R-015-apartment-screening.md) | Metric-based apartment screening | accepted | P1 | R13 |
| [R-016](R-016-apartment-comparison.md) | Apartment comparison | accepted | P0 | R14 |
| [R-017](R-017-transaction-inclusion-policy.md) | Transaction inclusion policy | accepted | P1 | R15 |
| [R-018](R-018-outlier-impact.md) | Outlier-impact inspection | accepted | P2 | R16 |
| [R-019](R-019-analysis-context.md) | Visible analysis context | accepted | P0 | R17 |
| [R-020](R-020-local-browser-analysis-workspace.md) | Local browser analysis workspace | accepted | P0 | Local-web direction |
| [R-021](R-021-regional-relative-profile.md) | Regional relative profile | accepted | P2 | Roadmap M6 |

## Change policy

- Clarifications that do not change the observable outcome may update an existing requirement.
- A material change to an accepted outcome should cite the decision that authorized the change.
- When another requirement fully replaces a requirement, retain the old document, mark it `superseded`, and link both directions.
- Do not add implementation-completion fields. Use linked verification evidence to establish what is covered.

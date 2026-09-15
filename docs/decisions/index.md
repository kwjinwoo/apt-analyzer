# Architecture Decision Records

ADRs preserve consequential decisions whose rationale would be difficult to reconstruct from code. Use [TEMPLATE.md](TEMPLATE.md) for new decisions.

## Status definitions

- `proposed`: under review.
- `accepted`: currently authoritative.
- `superseded`: replaced by a later ADR.
- `rejected`: evaluated and not adopted.

Once accepted, an ADR preserves the decision made at that time. Correcting wording or links is allowed, but changing the decision requires a new ADR that supersedes the old one.

## Decision catalog

| ID | Decision | Status | Date |
|---|---|---|---|
| [ADR-0001](ADR-0001-documentation-policy.md) | Documentation as context and navigation | accepted | 2026-08-21 |
| [ADR-0002](ADR-0002-python-development-toolchain.md) | Python development toolchain | accepted | 2026-08-22 |
| [ADR-0003](ADR-0003-official-sources-and-apartment-identity.md) | Official sources and apartment identity | accepted | 2026-08-22 |
| [ADR-0004](ADR-0004-sqlite-persistence-and-freshness.md) | SQLite persistence, migrations, and monthly freshness | accepted | 2026-08-23 |
| [ADR-0005](ADR-0005-local-web-delivery-stack.md) | Local-web delivery stack | accepted | 2026-08-24 |
| [ADR-0006](ADR-0006-regional-cache-and-screening.md) | Regional cache and bounded screening | accepted | 2026-08-26 |
| [ADR-0007](ADR-0007-regional-relative-analysis.md) | Independent regional relative analysis | accepted | 2026-08-27 |
| [ADR-0008](ADR-0008-interactive-province-list-freshness.md) | Interactive province-list freshness and stale fallback | accepted | 2026-08-28 |
| [ADR-0009](ADR-0009-explicit-transaction-name-aliases.md) | Explicit source-scoped transaction-name aliases | accepted | 2026-08-30 |
| [ADR-0010](ADR-0010-completed-month-rolling-analysis.md) | Completed-month rolling analysis | accepted | 2026-08-30 |
| [ADR-0011](ADR-0011-interactive-period-overrides.md) | Interactive completed-month period overrides | superseded | 2026-09-01 |
| [ADR-0012](ADR-0012-direct-chart-preview.md) | Direct non-mutating chart previews | superseded | 2026-09-03 |
| [ADR-0013](ADR-0013-duration-aware-chart-preview-turnover.md) | Duration-aware chart preview turnover | superseded | 2026-09-03 |
| [ADR-0014](ADR-0014-chart-preview-retention-split.md) | Chart preview 24-month retention split | accepted | 2026-09-07 |
| [ADR-0015](ADR-0015-source-labeled-apartment-profile.md) | Source-labeled persisted apartment profile | accepted | 2026-09-08 |
| [ADR-0016](ADR-0016-exact-area-inventory-source.md) | Building HUB exact-area inventory | accepted | 2026-09-09 |
| [ADR-0017](ADR-0017-area-inventory-turnover-denominator.md) | Verified exact inventory denominator for area turnover | accepted | 2026-09-12 |

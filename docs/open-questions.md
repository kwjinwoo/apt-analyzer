# Open Questions

This document records unresolved questions that require evidence or an explicit decision. Candidate approaches are not project commitments. Once resolved, link the accepted ADR and retain a short resolution record.

## OQ-001: Stable apartment identity

### Question

How should the project assign a stable internal identity when transaction and apartment-metadata sources do not share a canonical complex ID?

### Why it matters

Incorrect matching can combine different complexes or fragment one complex, invalidating every downstream metric.

### Evidence needed

- Candidate metadata sources and their identifiers
- Real matches across at least three complexes, including ambiguous names
- Behavior under renamed complexes and address variations

### Status

Resolved for the initial version by [ADR-0003](decisions/ADR-0003-official-sources-and-apartment-identity.md). K-APT candidates are enriched with legal-dong and full-address evidence before MOLIT retrieval. Renamed-complex continuity and a universal permanent cross-source identifier remain outside this resolution.

## OQ-002: Area-group boundary

### Question

What grouping rule should classify values such as `84.1`, `84.9`, and `85.0` square metres?

### Why it matters

The area group defines the transaction population for volume, price, retention, and MDD analysis.

### Current candidate

Integer-level grouping is suitable for an initial experiment but is not yet an accepted permanent rule.

### Evidence needed

- Exclusive-area distributions from at least three real complexes
- Cases where nearby raw areas represent different unit products
- Market-facing conventions used to describe those units

### Status

Unresolved.

## OQ-003: Missing months in the price series

### Question

How should months with no eligible transactions be represented for MDD analysis?

### Why it matters

Dropping, carrying forward, or interpolating missing observations gives different temporal meaning to a peak-to-trough decline.

### Status

Unresolved. Do not interpolate without an accepted decision.

## OQ-004: Partial-year annualization

### Question

How should turnover and transaction counts be annualized when an analysis interval contains partial calendar years or arbitrary dates?

### Why it matters

Different duration conventions can produce materially different normalized rates.

### Status

Unresolved.

## OQ-005: Zero transaction-retention baseline

### Question

What result should be returned when the baseline period contains zero eligible transactions?

### Why it matters

The ordinary retention ratio is undefined, and returning zero or infinity would imply misleading semantics.

### Status

Unresolved.

## OQ-006: Default direct-transaction policy

### Question

Should direct transactions be included in the default analysis population?

### Why it matters

Direct transactions may be legitimate but may also have different price characteristics from brokered market transactions.

### Evidence needed

- Frequency and distribution of direct transactions in validation complexes
- Impact on volume, price summaries, and MDD

### Status

Unresolved. The applied policy must always be visible.

## OQ-007: Outlier comparison policy

### Question

What method should define the optional “outlier excluded” comparison without silently removing valid trades?

### Why it matters

An automated rule can improve robustness or conceal meaningful transactions. The MVP prioritizes visibility over automatic removal.

### Status

Unresolved and deferred beyond the essential MVP.

## OQ-008: Area-filtered turnover presentation

### Question

What metric and label should be shown when transactions are filtered to an area group but only the whole-complex household count is available?

### Why it matters

Calling the result an area-level turnover rate would imply a denominator the project does not possess.

### Current constraint

The project must distinguish whole-complex turnover from area-filtered transaction activity.

### Status

Unresolved presentation and metric design.

## OQ-009: Minimum evidence for monthly price observations

### Question

Should a monthly median based on one transaction be used without qualification, excluded, or reported with an evidence indicator?

### Why it matters

Sparse monthly observations can dominate the MDD result while representing a single unit-specific trade.

### Status

Unresolved.

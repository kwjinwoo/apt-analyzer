# Roadmap

The roadmap describes outcome-oriented milestones and completion evidence. It does not track implementation tasks; those belong in issues, pull requests, or active agent plans.

Development follows this dependency direction:

```text
Foundation
    ↓
Reliable data and identity
    ↓
Single-complex analytics
    ↓
Persistence and comparison
    ↓
Screening and visualization
    ↓
Broader analysis and productization
```

## M0: Project foundation

### Outcome

The project has a testable Python foundation and accepted boundaries for its first domain model and metrics.

### Done when

- Formatting, linting, type-checking policy, and tests can run locally and in CI.
- Core analytics can be tested without external API access.
- Initial domain values can represent apartments, transactions, analysis periods, and area-group selections without relying on source-specific response objects.
- Metric semantics and unresolved edge cases are linked from the relevant requirements.
- The documentation and ADR conventions are enforced mechanically where practical.

## M1: Reliable transaction data and apartment identity

### Outcome

A real apartment complex can be resolved and its sale transaction history can be retrieved and normalized reproducibly.

### Done when

- At least three real complexes, including an ambiguous-name case, have been validated.
- Source records can be traced through normalization.
- Prices, dates, exclusive areas, transaction types, and cancellation states are normalized.
- Duplicate and cancelled records are handled according to explicit policies.
- Source failures, retries, and cached responses do not silently change analysis meaning.
- Apartment identity mismatches are detectable rather than silently accepted.

Completion evidence: deterministic contract tests cover acquisition, detail enrichment, mismatch detection, normalization, duplicate, failure, retry, and cache boundaries. Opt-in live validation on 2026-08-22 reproduced a 262-candidate ambiguous `현대` search and resolved three K-APT candidates through legal-dong and full-address evidence before retrieving their MOLIT transactions for 2025-01 through 2025-02. The initial policy is accepted in [ADR-0003](decisions/ADR-0003-official-sources-and-apartment-identity.md).

## M2: Single-complex analyzer

### Outcome

A user can analyze one selected complex and area population through a reproducible non-web interface.

### Done when

- Available area groups can be discovered and selected while raw exclusive areas remain available.
- Yearly transaction counts and required price summaries are available.
- Turnover, transaction retention, and MDD return their required context.
- Peak and trough observations are available for MDD.
- Transaction inclusion choices and filtered counts are visible.
- Representative acceptance tests link back to the relevant requirements.
- Human-readable and machine-readable result forms are available through the initial interface.

Completion evidence: `tests/test_m2.py` covers deterministic area grouping and selection, exact yearly summaries and valid-empty coverage, successful annual/multi-year turnover and retention with explicit methods, shared-policy propagation, explicit unavailable states, monthly evidence, MDD peak/trough/subperiod and non-declining behavior, integrated context, and deterministic text/JSON serialization. `test_real_console_entrypoint_outputs_configured_json_and_text` exercises the actual `apt-analyzer analyze INPUT --format text|json` entry point with `tests/fixtures/m2_input.json`; repository validation and pre-commit checks pass.

This is the first usable MVP for a single apartment complex.

## M3: Persistence and apartment comparison

### Outcome

Previously acquired data can be updated locally, and multiple apartment complexes can be compared under identical analysis conditions.

### Done when

- Incremental updates avoid unnecessary repeated acquisition without hiding source freshness.
- Duplicate records remain constrained across updates.
- Schema changes have a reproducible migration path.
- Every compared apartment uses the same area interpretation, periods, price method, and inclusion policy.
- Comparison results expose metric context and can be exported.

This milestone completes the initial multi-complex MVP described by the accepted requirements.

Completion evidence: `tests/test_m3.py` covers atomic deterministic v1→v2 migration with exact-duplicate collapse, source-specific valid-empty monthly caching/freshness and provenance or apartment/month mismatch failures, persisted evidence loaded into a two-subject common-context comparison, subject-integrity validation, explicit absent-group unavailability, co-present metrics, and the real `compare INPUT --format text|json` CLI with equivalent exports. Persistence direction is recorded in ADR-0004.

## M4: Screening and visualization

### Outcome

Users can inspect metric behavior over time and discover candidate complexes from precomputed, comparable results.

### Done when

- Transaction-volume and monthly-median price series can be inspected visually.
- MDD peak and trough and retention periods are visually identifiable.
- Regional-scale ingestion and metric computation are reproducible.
- Screening filters have explicit semantics and use comparable analysis contexts.
- Results can be sorted or filtered without implying an investment recommendation.

## M5: Broader apartment analysis

### Outcome

Validated analysis domains can be added without mixing their meaning into the liquidity core.

Candidate domains include long-term price behavior, complex characteristics, nearby-complex benchmarks, rental-market metrics, and relative regional analysis.

### Entry conditions

- The initial liquidity metrics have been manually validated across multiple regions and market periods.
- Important distributions, correlations, and data-quality limitations are understood.
- New domains can remain independently testable and interpretable.

## M6: Productization

### Outcome

The validated analytics workflow is available through a maintainable product interface with repeatable data updates.

### Done when

- Core analytics remain independent of the selected web stack.
- Data updates and analysis reproduction are operationally defined.
- Search, single-complex analysis, comparison, visualization, and screening are available through the product interface.
- User-visible metric limitations and analysis context remain explicit.

## Deferred product directions

- Composite liquidity scores, until metric distributions and correlations are validated
- Price prediction or investment recommendations
- Listing-price and fair-value estimation
- School, transportation, development-potential, subscription, and recommendation scores
- Jeonse and monthly-rent analysis until introduced as independent data domains

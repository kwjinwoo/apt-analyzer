# Architecture Overview

This document records architectural intent and boundaries. It deliberately avoids predicted class names, package trees, and control flow that should be recovered from code once implementation exists.

## Architectural objective

Build a reusable apartment-complex analysis toolkit whose core analytics can be tested without external API access. Validate data identity, normalization, and metric meaning before investing in a product-level UI.

## Intended flow

```text
External data sources
        ↓
Acquisition and source preservation
        ↓
Normalization and identity resolution
        ↓
Explicit analysis context and filtering
        ↓
Domain analytics
        ↓
CLI, comparison, screening, and local web UI
```

## Boundaries

### External data acquisition

Source adapters are responsible for source-specific requests, responses, availability failures, and parsing concerns. External schemas must not become the analytics domain model by accident.

### Normalization

Normalization translates source values into explicit domain meaning while preserving traceability to relevant source values. Cancellation status, transaction type, exclusive area, price, and contract date require unambiguous normalized representations.

### Apartment identity resolution

Apartment identity is an explicit boundary because transaction and metadata sources may not share a canonical complex identifier. Matching must not be hidden inside unrelated API or repository logic.

### Analysis population

Area selection, date boundaries, and transaction inclusion rules define the population before metrics are calculated. A shared analysis context prevents different metrics or comparison subjects from silently using different populations.

### Domain analytics

Metric calculations operate on normalized domain inputs and explicit context. They must not require network access or an external service in order to be unit tested.

### Interfaces

CLI, comparison, screening, visualization, and the local web interface consume
domain capabilities. The local web boundary is loopback-bound by default, keeps
credentials server-side, and uses server-rendered HTML/HTMX plus bundled TypeScript
assets. Presentation choices must not redefine metric semantics.

### Persistence

Persistence is an adapter concern introduced to reduce repeated acquisition and support multi-complex analysis. Storage technology must not become the definition of domain identity or metrics.

## Dependency direction

- Domain analytics may depend on domain values and policies, not external API clients or UI frameworks.
- Source adapters translate into normalized domain inputs.
- Interfaces depend on application and domain capabilities.
- Persistence implementations satisfy domain-facing access contracts rather than exposing storage-specific records throughout the system.

## Replaceable policies

The following behaviors require explicit, independently testable policies because evidence may change them:

- Apartment identity matching
- Exclusive-area grouping
- Transaction inclusion
- Outlier handling
- Price-series aggregation
- Missing-month treatment

## Architectural risks

- Different sources may identify the same complex differently.
- Similar exclusive areas do not always represent the same market product.
- Sparse transaction data can make price series and MDD unstable.
- Exact area-level turnover is unavailable without area-level household counts.
- Public API corrections and cancellations can change historical records.

See [open questions](../open-questions.md) for unresolved policies and [ADRs](../decisions/index.md) for accepted directions.

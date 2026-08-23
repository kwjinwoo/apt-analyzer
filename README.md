# apt-analyzer

A data-driven toolkit for analyzing apartment complexes using public real-estate transaction data.

The project starts with **transaction liquidity** and **price resilience** as its first analysis domain, but is designed to expand into broader apartment-complex analysis over time.

## Documentation

Start with the [documentation index](docs/index.md) for product requirements, domain definitions, architectural intent, decisions, open questions, and the outcome-oriented roadmap. Use the [LLM-maintained wiki](wiki/index.md) to navigate relationships among those sources. Current behavior must be verified in code and tests.

## Official Data Key

Set the data.go.kr Encoding key in the repository-root `.env`:

```dotenv
DATA_GO_KR_SERVICE_KEY=your_percent_encoded_key
```

The environment variable takes precedence. The key is already percent-encoded and the client preserves it exactly once. Never commit `.env` or print credential-bearing request URLs.

## Offline M2 analyzer

The first MVP analyzes a deterministic JSON fixture without a network call:

```bash
apt-analyzer analyze input.json --format text
apt-analyzer analyze input.json --format json
```

The input declares `data_status` as `complete` (or `valid_empty` for a known
successful empty result), the selected apartment, an inclusive overall period,
normalized transactions, and an explicit inclusion policy. Area groups are
discovered from the selected apartment's known transactions for that period;
use `{"kind": "all"}` or select a discovered group by its `key`. Turnover and
retention accept complete calendar-year periods only and expose household
count, scope, and source evidence. MDD uses observed monthly medians; missing
months are not interpolated. JSON preserves monetary precision as strings, and
text output contains the same context and metric fields.

Minimal input shape:

```json
{
  "data_status": "complete",
  "apartment": {"internal_id": "apt-1", "display_name": "Example"},
  "period": {"start": "2024-01-01", "end": "2025-12-31"},
  "area_selection": {"kind": "all"},
  "inclusion_policy": {"include_cancelled": false, "transaction_types": ["brokered"]},
  "transactions": []
}
```

For a group selection, first inspect the JSON result's `available_area_groups`
and pass its key as `{"kind": "group", "key": "floor-84"}`.

## Offline M3 comparison

Compare offline subjects with one shared configuration:

```bash
apt-analyzer compare comparison.json --format text
apt-analyzer compare comparison.json --format json
```

The input declares apartments, transactions keyed by apartment ID, and common periods, area-group key, price method, and inclusion policy. Missing subject evidence is exported as unavailable.

For local persistence, use the stdlib `SQLiteStore` API with an injected
`fetch_month` callable. `update_incremental` records source-specific monthly
coverage and fetched-at freshness, skips fresh months, counts inserts and
duplicates, and keeps failed or mismatched months out of successful coverage.
`load_transactions` supplies reproducible evidence to `compare` without a
network call.

## Current Focus

The initial goal is to answer a simple question:

> **How well did this apartment complex continue to trade during a market downturn, and how well did its price hold up?**

Rather than relying only on recent transaction prices, complex size, or subjective popularity, `apt-analyzer` focuses on measurable historical behavior.

Core metrics include:

- Transaction volume
- Turnover rate
- Transaction retention rate
- Maximum drawdown (MDD)
- Area-specific transaction behavior
- Cross-complex comparison

---

## Why This Project?

Apartment liquidity is difficult to judge from a single metric.

A large complex may have many transactions simply because it contains many households. A popular complex may trade actively in a bull market but become illiquid during a downturn.

This project attempts to normalize and compare transaction activity using metrics such as:

```text
Transaction Volume
        ↓
Turnover Rate
        ↓
Downturn Retention
        ↓
Price Drawdown
        ↓
Cross-Complex Comparison
```

The initial focus is not to predict future prices, but to make historical liquidity and price resilience easier to measure and compare.

---

# Core Features

## 1. Apartment Search

Users can search for an apartment complex by name.

If multiple complexes share the same or similar names, they should be distinguishable by location or address.

Example:

```text
Search: "Lotte Castle"

- Lotte Castle Eco 1
  Giheung-gu, Yongin-si, Gyeonggi-do

- Lotte Castle Eco 2
  Giheung-gu, Yongin-si, Gyeonggi-do
```

Each selected apartment complex is mapped to an internal unique identifier.

---

## 2. Transaction Data

The system retrieves apartment sale transaction records for a selected complex and time range.

Each transaction should contain at least:

- Contract date
- Transaction price
- Exclusive area
- Floor
- Transaction type
- Cancellation status

Additional fields should be preserved when available:

- Building / unit information
- Construction year
- Broker location

---

## 3. Area-Based Analysis

Once a complex is selected, the system automatically detects the exclusive-area values available for that complex.

Example:

```text
All
59㎡
74㎡
84㎡
101㎡
```

Similar raw exclusive-area values may be grouped into a common market-facing area group.

Example:

```text
84.81㎡
84.92㎡
84.97㎡
   ↓
84㎡ group
```

The raw value is still preserved internally:

```text
exclusive_area = 84.97
area_group     = 84
```

The selected area group acts as a filter for all downstream analytics.

---

# Analytics

## 4. Transaction Volume

Transaction data can be aggregated by year.

Minimum output:

| Year | Transactions | Avg Price | Median Price | Max Price | Min Price |
|---|---:|---:|---:|---:|---:|
| 2021 | 81 | 610M KRW | 600M KRW | 680M KRW | 530M KRW |
| 2022 | 31 | 560M KRW | 550M KRW | 620M KRW | 500M KRW |
| 2023 | 22 | 490M KRW | 480M KRW | 540M KRW | 450M KRW |

The internal aggregation layer should remain flexible enough to support monthly and quarterly analysis later.

---

## 5. Turnover Rate

Turnover rate measures how actively a complex trades relative to its size.

Definition:

```text
Turnover Rate =
    Annualized Transaction Count
    ----------------------------
        Total Households
```

Example:

```text
Transactions in 2022-2023 = 60
Period length              = 2 years
Total households           = 1,000

Annualized transactions = 30

Turnover Rate = 3.0%
```

The system should support both:

- Annual turnover rate
- Multi-year annualized turnover rate

### Area-Level Limitation

An exact area-level turnover rate requires the number of households for that specific area type.

Until area-level household counts are available, the system must clearly distinguish between:

- Complex-level turnover rate
- Area-filtered transaction activity

---

## 6. Transaction Retention Rate

Transaction retention rate measures how much transaction activity remains during a comparison period relative to a baseline period.

Definition:

```text
Transaction Retention Rate =
    Comparison Period Annual Avg Transactions
    -----------------------------------------
      Baseline Period Annual Avg Transactions
```

Example:

```text
Baseline
2019-2021: 60 transactions/year

Comparison
2022-2023: 30 transactions/year

Retention Rate = 50%
```

Users should be able to configure both periods.

Example:

```text
Baseline Period
2019-2021

Comparison Period
2022-2023
```

---

## 7. Maximum Drawdown

Maximum Drawdown measures the largest peak-to-trough decline in transaction prices over a selected period.

Because apartment transaction data is sparse and noisy, the default price series should use:

```text
Monthly Median Transaction Price
```

Pipeline:

```text
Transactions
    ↓
Monthly Median Price
    ↓
Price Time Series
    ↓
Running Peak
    ↓
Peak-to-Trough Drawdown
    ↓
Maximum Drawdown
```

Example:

```text
2021-10  650M KRW  ← Peak
2022-06  600M KRW
2023-01  530M KRW
2023-04  480M KRW  ← Trough

MDD = -26.2%
```

The result should include:

- MDD value
- Peak date
- Peak price
- Trough date
- Trough price

---

# Apartment Comparison

Multiple apartment complexes can be compared using the same analysis configuration.

Example:

| Metric | Complex A | Complex B | Complex C |
|---|---:|---:|---:|
| Households | 1,200 | 850 | 1,500 |
| 2022-23 Transactions | 72 | 31 | 81 |
| Turnover Rate | 3.0% | 1.8% | 2.7% |
| Retention Rate | 58% | 31% | 63% |
| MDD | -22% | -34% | -25% |

All compared complexes should use the same:

- Area filter
- Analysis period
- Baseline period
- Comparison period
- Price aggregation method
- Transaction filters

---

# Screening

Once enough apartment data has been collected, the project should support filtering complexes by quantitative criteria.

Example:

```text
Transaction Price     400M-600M KRW
Exclusive Area        59-84㎡
Turnover Rate         >= 2%
Retention Rate        >= 40%
MDD                   >= -30%
2023 Transactions     >= 10
```

The long-term goal is to support queries such as:

> Find apartment complexes that remained liquid during a market downturn and experienced relatively limited price drawdowns.

---

# Data Quality

The system should identify transaction records that may distort the analysis.

At minimum:

- Cancelled transactions
- Direct transactions
- Brokered transactions

Users should be able to include or exclude these records.

Example:

```text
[x] Brokered Transactions
[x] Direct Transactions
[ ] Cancelled Transactions
```

Automatic outlier removal is not required for the initial MVP.

Instead, the project should preserve raw data and make filtering behavior explicit and reproducible.

---

# Analysis Context

Every analysis result should expose the configuration used to generate it.

Example:

```text
Apartment
Complex A

Area
84㎡

Analysis Period
2019-2026

Turnover Period
2022-2023

Retention
Baseline:   2019-2021
Comparison: 2022-2023

MDD Price Aggregation
Monthly Median

Direct Transactions
Excluded
```

A metric without its analysis context is not considered reproducible.

---

# MVP User Flow

```text
Search Apartment
      ↓
Select Complex
      ↓
Select Area
[All / 59 / 74 / 84 / 101]
      ↓
Configure Analysis Period
      ↓
Load and Normalize Transactions
      ↓
┌──────────────────────────┐
│ Transaction Volume       │
│ Price Trend              │
│ Turnover Rate            │
│ Retention Rate           │
│ Maximum Drawdown         │
└──────────────────────────┘
      ↓
Compare with Other Complexes
```

Future direction:

```text
Collect Multiple Complexes
        ↓
Precompute Metrics
        ↓
Screen by Conditions
        ↓
Discover Strong Candidates
```

---

# Suggested Architecture

The initial version should begin as a local analytics tool.

```text
Public Real-Estate APIs
        ↓
Data Ingestion
        ↓
Normalization / Apartment Matching
        ↓
DuckDB or SQLite
        ↓
Analytics Layer
        ↓
CLI / Notebook
```

Once the analytics logic and data model are validated, the project can expand into a web application.

```text
FastAPI
   ↓
PostgreSQL
   ↓
React / Next.js
```

---

# Suggested Project Structure

```text
apt-analyzer/
├── README.md
├── ROADMAP.md
├── pyproject.toml
├── src/
│   └── apt_analyzer/
│       ├── api/
│       │   ├── transactions.py
│       │   └── apartments.py
│       ├── ingestion/
│       │   ├── transaction_loader.py
│       │   └── apartment_loader.py
│       ├── models/
│       │   ├── apartment.py
│       │   └── transaction.py
│       ├── normalization/
│       │   ├── apartment_matcher.py
│       │   └── area_group.py
│       ├── analytics/
│       │   ├── liquidity/
│       │   │   ├── turnover.py
│       │   │   ├── retention.py
│       │   │   └── drawdown.py
│       │   ├── price/
│       │   └── comparison/
│       ├── storage/
│       │   └── repository.py
│       └── cli/
│           └── main.py
├── tests/
│   ├── analytics/
│   ├── normalization/
│   └── ingestion/
└── data/
    └── .gitkeep
```

---

# MVP Scope

## P0 — Required

- Apartment search
- Transaction data retrieval
- Automatic area grouping and selection
- Yearly transaction aggregation
- Turnover rate
- Baseline/comparison transaction retention rate
- Maximum drawdown
- Multi-complex comparison

## P1 — High Value

- Transaction-volume visualization
- Price-trend visualization
- Direct/cancelled transaction filters
- Monthly and quarterly aggregation
- Metric-based filtering

## P2 — Later

- Accurate household count by area type
- Automatic outlier detection
- Nearby-complex benchmarking
- Regional percentile analysis
- Composite liquidity score

---

# Out of Scope — v1

- Jeonse / monthly rent
- Subscription / presale analysis
- School-district scoring
- Transportation scoring
- Development-potential analysis
- AI price prediction
- Listing-price analysis
- Fair-value estimation
- Investment recommendation score

---

# Project Principle

The initial version should avoid a composite score.

The project should first expose raw, interpretable metrics such as:

```text
Turnover Rate      3.0%
Retention Rate    55.0%
MDD              -24.0%
```

A weighted score should only be considered after validating these metrics across enough complexes, regions, and market cycles.

---

# Long-Term Direction

`apt-analyzer` is intentionally broader than a liquidity-only tool.

Liquidity and price resilience are the first analysis modules, but the project can later expand into areas such as:

- Long-term price trends
- Area-type popularity
- Relative valuation
- Jeonse ratio
- Complex age and scale
- Nearby-complex benchmarking
- Regional percentile analysis
- Transportation and amenity data
- Broader apartment-complex comparison

The repository name therefore reflects the broader long-term goal:

> **Analyze an apartment complex as a data product, not just as a transaction history.**

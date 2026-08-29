---
id: R-022
title: Local productized analysis and screening workspace
status: accepted
priority: P0
created: 2026-08-27
updated: 2026-08-28
origin: "Roadmap M7 productization"
supersedes: []
superseded_by: null
related_requirements: [R-015, R-019, R-020]
related_decisions: [ADR-0005, ADR-0006, ADR-0008]
---

# R-022: Local productized analysis and screening workspace

## Intent

Users need a repeatable local interface for the validated apartment analytics,
including bounded regional screening, without losing analysis context or evidence
availability.

## Requirement

The local browser workspace supports search, analysis, comparison, visualization,
and persisted regional screening with equivalent machine-readable exports and
operationally documented local data reproduction.

## Acceptance criteria

- **AC-1:** Search, single-complex analysis, comparison, visualization, and screening are available through localhost.
- **AC-2:** Screening accepts explicit regions, candidates, common context, and metric/operator/value/unit rules; unavailable evidence cannot pass.
- **AC-3:** Screening displays inclusion-driving values, context, coverage state, and historical non-recommendation limitations, with equivalent export.
- **AC-4:** Install/start, persistent SQLite selection, bounded updates, reproduction, verification, and backup/recovery are documented.
- **AC-5:** The default local workspace is understandable in Korean, while equivalent exports retain stable machine-readable keys, identifiers, status codes, and metric context.
- **AC-6:** Search and SQLite evidence refresh show an accessible in-flight progress indicator and prevent duplicate submission; the main screen shows today’s per-service public-API attempts, configured daily limits, and non-negative remaining counts from the configured SQLite database, explicitly distinguishing local accounting from portal-global usage.
- **AC-7:** Interactive K-APT province-list search reuses a persisted full-province snapshot for 24 hours across local server restarts and name queries; at expiry it synchronously revalidates, atomically replaces only after a complete success, and falls back to the prior snapshot with a visible Korean stale/failure notice when refresh fails.

## Constraints

The local workspace remains single-user, loopback-bound, SQLite-backed, and network-free in deterministic tests. Existing metric semantics and unavailable-versus-zero distinctions remain authoritative.

## Non-goals

Cloud hosting, authentication, multi-user operation, automatic nationwide ingestion, prediction, composite scoring, and investment recommendations.

## Verification

### Automated

- [`test_screening_flow_uses_persisted_regional_coverage_and_exports_equivalent_context`](../../tests/test_web.py) — AC-2 and AC-3.
- [`test_comparison_flow_renders_shared_context_and_export`](../../tests/test_web.py) — AC-1 and shared-context export.
- [`test_web_e2e.py`](../../tests/test_web_e2e.py) — AC-1 and AC-5 browser workflow, including Korean labels and chart accessibility.
- [`test_web.py`](../../tests/test_web.py) and [`test_m3.py`](../../tests/test_m3.py) — AC-6 local usage dashboard, limit validation, and SQLite daily accounting.
- [`test_web.py`](../../tests/test_web.py) and [`test_m5.py`](../../tests/test_m5.py) — AC-7 persistent province-list freshness, stale fallback, and boundary behavior.

### Manual or data validation

Run the documented local commands against an explicitly selected persistent SQLite database.

### Verification gaps

Real-source ingestion remains opt-in because deterministic tests do not call external APIs.

## Open questions

- [OQ-008: Area-filtered turnover presentation](../open-questions.md#oq-008-area-filtered-turnover-presentation)

## Related documentation

- [Roadmap M7](../roadmap.md#m7-productization)
- [R-015](R-015-apartment-screening.md)
- [R-020](R-020-local-browser-analysis-workspace.md)

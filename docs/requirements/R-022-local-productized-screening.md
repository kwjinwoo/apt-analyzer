---
id: R-022
title: Local productized analysis and screening workspace
status: accepted
priority: P0
created: 2026-08-27
updated: 2026-08-27
origin: "Roadmap M7 productization"
supersedes: []
superseded_by: null
related_requirements: [R-015, R-019, R-020]
related_decisions: [ADR-0005, ADR-0006]
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

## Constraints

The local workspace remains single-user, loopback-bound, SQLite-backed, and network-free in deterministic tests. Existing metric semantics and unavailable-versus-zero distinctions remain authoritative.

## Non-goals

Cloud hosting, authentication, multi-user operation, automatic nationwide ingestion, prediction, composite scoring, and investment recommendations.

## Verification

### Automated

- [`test_screening_flow_uses_persisted_regional_coverage_and_exports_equivalent_context`](../../tests/test_web.py) — AC-2 and AC-3.
- [`test_comparison_flow_renders_shared_context_and_export`](../../tests/test_web.py) — AC-1 and shared-context export.
- [`test_web_e2e.py`](../../tests/test_web_e2e.py) — AC-1 browser workflow.

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

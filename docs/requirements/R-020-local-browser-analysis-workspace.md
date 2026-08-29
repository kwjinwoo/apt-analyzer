---
id: R-020
title: Local browser analysis workspace
status: accepted
priority: P0
created: 2026-08-24
updated: 2026-08-24
origin: "Local-web product direction"
supersedes: []
superseded_by: null
related_requirements: [R-001, R-002, R-013, R-014, R-016, R-017, R-019]
related_decisions: [ADR-0005, ADR-0008]
---

# R-020: Local browser analysis workspace

## Intent

Users need to inspect and compare apartment analysis with a visible, mouse- and
keyboard-interactive local workspace rather than assembling a CLI workflow.

## Requirement

The user can launch a local browser workspace that supports apartment search and
explicit selection, evidence update, analysis, comparison, and export while showing
the active analysis context and data availability states.

## Acceptance criteria

- **AC-1:** Launching the documented local command opens a loopback-bound workspace
  without requiring a cloud service.
- **AC-2:** A user can search, distinguish, and explicitly select an apartment before
  requesting data or analysis.
- **AC-3:** A user can request an update for a selected period and distinguish fresh,
  stale, valid-empty, and failed evidence.
- **AC-4:** A user can choose analysis period, area population, and transaction
  inclusion policy before viewing metrics.
- **AC-5:** A user can inspect transaction volume and price observations, compare
  selected apartments under a shared context, and export the same context.
- **AC-6:** Credentials are kept on the server process and the default workspace is
  bound to loopback; the browser does not receive secrets.

## Constraints

- The initial workspace is single-user and local to one process and SQLite database.
- CLI commands remain available as a deterministic export and regression interface.
- Missing, empty, and failed source evidence must remain distinct in user-visible
  results.

## Non-goals

- Regional screening, outlier policy, authentication, cloud deployment, or network
  hosting.
- React/Next.js, PostgreSQL, or a separate CSS framework.

## Verification

### Automated

- [Web foundation contract tests](../../tests/test_web.py) — verifies explicit
  selection, persisted multi-subject shared-context comparison, equivalent export,
  update-only rendering, and coverage/status semantics;
  M1-M3 representative suites cover delegated workflow semantics.
- [Deterministic browser acceptance](../../tests/test_web_e2e.py) — drives Chromium
  through search, selection, update of both subjects, analysis, chart/table visibility,
  comparison, and export without a network source.
- [Credential composition regressions](../../tests/test_acquisition.py) and
  [default web composition regressions](../../tests/test_web.py) — verify process
  environment precedence, repository `.env` fallback, missing-key behavior, and that
  the default workspace uses the canonical acquisition loader.

### Manual or data validation

Default automated tests are deterministic and network-free. Run the browser baseline
with `uv run --locked pytest -m e2e tests/test_web_e2e.py -q`; installed Chromium result:
`1 passed`. In-app browser QA on 2026-08-26 confirmed update-only rendering, accessible
values, comparison counts/status/context/export, deduplicated area options, and absence
of comparison-only empty charts.

### Verification gaps

No R-020 acceptance-criterion gap remains. Live real-source validation remains a manual
or opt-in data-validation item because deterministic tests never call public APIs.

## Open questions

- [OQ-003: Missing months in the price series](../open-questions.md#oq-003-missing-months-in-the-price-series)
- [OQ-008: Area-filtered turnover presentation](../open-questions.md#oq-008-area-filtered-turnover-presentation)

## Related documentation

- [Roadmap M4](../roadmap.md#m4-local-web-analyzer-and-visualization)
- [ADR-0005: Local-web delivery stack](../decisions/ADR-0005-local-web-delivery-stack.md)

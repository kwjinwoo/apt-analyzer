---
id: ADR-0005
title: Local-web delivery stack
status: accepted
date: 2026-08-24
supersedes: []
superseded_by: null
related_requirements: [R-013, R-014, R-016, R-019, R-020]
---

# ADR-0005: Local-web delivery stack

## Status

Accepted

## Context

The completed M2 and M3 milestones provide deterministic analytics, persistence,
comparison, and CLI export. Repeated use shows that a visible local workspace is a
better next interface than a CLI-only workflow. The first web product must preserve
the existing domain boundaries, SQLite persistence, credential privacy, and small
single-user operating model.

## Decision

Deliver the next interface as a localhost application using FastAPI and Uvicorn,
server-rendered Jinja2 HTML with HTMX interactions, Chart.js for metric visuals, and
vanilla TypeScript bundled by Vite. Retain SQLite and the CLI. Bind to `127.0.0.1` by
default and keep source credentials in the server process.

## Rationale

This stack adds a browser interaction boundary without turning the validated Python
analytics core into a client-side application. Server-rendered fragments keep local
state and credential handling simple, while TypeScript/Vite provide a deterministic
home for authored assets and Chart.js covers the initial time-series needs.

## Alternatives considered

### Alternative A: React or Next.js with a separate API

Rejected for this milestone because a full SPA would add client-side routing, state,
DTO, and deployment concerns before the local workflow is validated.

### Alternative B: PostgreSQL and cloud-oriented hosting

Rejected because the first workspace is single-user and local; SQLite already covers
the accepted persistence boundary and avoids a required service dependency.

### Alternative C: CLI-only continuation

Rejected as the primary interface because it does not meet the accepted browser
workspace outcome, but retained for export and regression automation.

## Consequences

### Positive

- Existing domain and persistence boundaries remain reusable.
- The browser can show context, freshness, unavailable states, and charts together.
- Local operation avoids cloud hosting and keeps credentials server-side.

### Negative

- The first UI is intentionally limited to one local process and SQLite database.
- HTMX and Vite assets introduce both Python and Node quality gates.

### Follow-up

- Add browser acceptance coverage as M4 features become implemented.
- Revisit hosting and storage only after regional use and productization evidence.

## Related documentation

- [R-020: Local browser analysis workspace](../requirements/R-020-local-browser-analysis-workspace.md)
- [R-013: Transaction-volume visualization](../requirements/R-013-transaction-volume-visualization.md)
- [R-014: Price visualization](../requirements/R-014-price-visualization.md)
- [Architecture overview](../architecture/overview.md)

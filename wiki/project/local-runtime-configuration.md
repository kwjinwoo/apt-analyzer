---
title: Local Runtime Configuration
type: project
role: topic
status: active
updated: 2026-08-26
aliases:
  - Local credential configuration
  - Runtime service key loading
tags:
  - configuration
  - credentials
  - local-web
---

# Local Runtime Configuration

## Scope

This topic records how the local browser workspace obtains official-source credentials without exposing them to browser output.

## Knowledge

All live interfaces reuse `apt_analyzer.acquisition.load_service_key()`. The process environment takes precedence over the repository-root/current-working-directory `.env` fallback. A missing credential remains a user-visible live-operation failure, while the credential stays server-side.

The M4 default web composition previously duplicated lookup with a process-environment-only read. That caused a configured local `.env` to be ignored and selected `MissingKeyService`; the prevention rule is to delegate credential lookup to the canonical acquisition loader.

The current official K-APT apartment-list contract is `AptListService4/getSidoAptList4`, as published in the [data.go.kr API page](https://www.data.go.kr/data/15057332/openapi.do). The M1 search boundary must keep its endpoint aligned with that published operation; an older v3 operation can return `NO_OPENAPI_SERVICE_ERROR` even when credentials are valid.

## Graph connections

- The local workspace outcome is defined by [R-020](../../docs/requirements/R-020-local-browser-analysis-workspace.md).
- The workspace boundary and server-side delivery are constrained by [ADR-0005](../../docs/decisions/ADR-0005-local-web-delivery-stack.md).
- This configuration supports the end-to-end [MVP knowledge map](mvp-knowledge-map.md).

## Requirements

- [R-020 AC-6](../../docs/requirements/R-020-local-browser-analysis-workspace.md) requires credentials to remain on the server process and absent from browser output.

## Decisions and open questions

The accepted invariant is environment-over-`.env` precedence with one canonical loader. No product or architecture question is opened by this bug fix.

## Evidence and interpretation risks

- Never record, log, export, or render the service-key value.
- Tests use sentinel values only and do not call the public API.
- A live source validation still depends on the user's local credential being configured and valid.

## Verify in the repository

- Canonical loading: [`load_service_key`](../../src/apt_analyzer/acquisition.py).
- Default web composition: [`_default_service`](../../src/apt_analyzer/web/__init__.py).
- Loader precedence/fallback/missing-source regressions: [`test_acquisition.py`](../../tests/test_acquisition.py).
- Default composition and missing-key regressions: [`test_web.py`](../../tests/test_web.py).
- Official K-APT list operation regression: [`test_m1.py`](../../tests/test_m1.py).

## Related pages

- [MVP knowledge map](mvp-knowledge-map.md)
- [Requirement map](requirement-map.md)

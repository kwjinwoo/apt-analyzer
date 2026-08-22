---
id: ADR-0001
title: Documentation as context and navigation
status: accepted
date: 2026-08-21
supersedes: []
superseded_by: null
related_requirements: []
---

# ADR-0001: Documentation as context and navigation

## Status

Accepted

## Context

Agent-led development benefits from durable product and design context, but implementation-oriented documentation quickly becomes a competing and stale description of the system. Functions, control flow, data structures, and current implementation choices can be recovered more reliably from code and tests.

The project needs documentation that helps humans and agents understand requirements, domain meaning, architectural intent, constraints, and where to investigate, without treating prose as proof of current behavior.

## Decision

Project documentation will be a context and navigation layer rather than a duplicate implementation reference.

- Code and tests are authoritative for current behavior.
- Requirements are authoritative for accepted product outcomes.
- Domain documents and accepted ADRs are authoritative for agreed terminology, metric meaning, constraints, and decision rationale.
- Documentation may point to code and representative tests, but must not duplicate implementation mechanics.
- Any implementation-related statement found in documentation must be verified against current code and tests before it is relied upon.
- The LLM-maintained wiki may synthesize and connect project knowledge, but it does not replace docs, code, or tests as an authoritative source.

## Rationale

This separation gives agents durable intent while limiting documentation drift. Navigation links and verification references accelerate exploration without requiring prose to track every refactor. Git history preserves earlier versions of evolving documents.

## Alternatives considered

### Alternative A: Comprehensive implementation documentation

Document every module, data structure, and control flow in prose. This was rejected because it would duplicate code, become stale, and create ambiguity about the actual behavior.

### Alternative B: Code and tests only

Keep no durable product or design documentation. This was rejected because requirements, metric interpretation, external constraints, rejected alternatives, and decision rationale cannot be reliably reconstructed from implementation alone.

### Alternative C: Treat the LLM wiki as the project source of truth

Allow the generated wiki to define requirements and behavior. This was rejected because the wiki is a synthesis layer maintained by a probabilistic system and must remain grounded in human-approved docs and verified implementation evidence.

## Consequences

### Positive

- Documentation focuses on durable information with high context value.
- Agents receive clear instructions about where to verify different kinds of claims.
- Refactoring does not require rewriting narrative implementation documentation.
- Requirements can link directly to representative verification evidence.

### Negative

- Understanding current behavior always requires inspecting code and tests.
- Contributors must exercise judgment about whether a change affects durable documentation.
- Documentation and wiki linting are needed to detect broken links and stale claims.

### Follow-up

- The LLM wiki schema and its ingest, query, decomposition, and lint workflows are defined in [wiki maintenance instructions](../../wiki/AGENTS.md); evolve them through reviewed changes as the graph grows.
- Mechanical wiki checks are implemented in [`scripts/wiki_lint.py`](../../scripts/wiki_lint.py). Extend repository-wide document ID and Requirement verification checks as the project foundation grows.

## Related documentation

- [Documentation index](../index.md)
- [Requirement template](../requirements/TEMPLATE.md)
- [ADR template](TEMPLATE.md)

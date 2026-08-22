---
id: ADR-0002
title: Python development toolchain
status: accepted
date: 2026-08-22
supersedes: []
superseded_by: null
related_requirements: []
---

# ADR-0002: Python development toolchain

## Status

Accepted

## Context

The project needs a reproducible Python environment and a small, deterministic quality gate that
works for both a human developer and coding agents. Dependency resolution, formatting, linting,
type checking, testing, and commit-message validation must be invocable without relying on
machine-global Python packages. The rationale for choosing these tools would be difficult to infer
from their configuration alone.

## Decision

Use the Python 3.14 minor release line and manage the project environment, dependency groups, and
lockfile with uv. Use a `src` package layout with uv's build backend. Use Ruff for formatting,
linting, import ordering, and Google-style docstring enforcement; Pyright in strict mode for static
type checking; and pytest for automated tests. Run repository hygiene checks and these quality
checks through pre-commit, and validate commit messages with Commitizen's Conventional Commits
rules in the `commit-msg` stage.

Configuration files and the lockfile remain authoritative for current commands and exact tool
versions. This ADR records only the durable choice and its rationale.

## Rationale

One environment manager and one lockfile reduce differences between interactive development,
agent execution, and future automation. Ruff consolidates several fast source checks into one tool,
while Pyright and pytest cover different classes of defects. Local Git hooks provide immediate
feedback at the point where the repository's conventions matter. Pinning the Python minor line
allows compatible patch releases without making a particular developer machine's installed patch
version a project-wide constraint.

## Alternatives considered

### Alternative A: pip and hand-maintained requirements files

This is widely supported, but it would require additional conventions or tools for environment
creation, dependency grouping, and deterministic locking.

### Alternative B: Separate formatting, linting, and import-sorting tools

This offers more independent choices, but increases configuration surface and the chance of tools
disagreeing over the same source file.

### Alternative C: Rely on manual checks before commits

This has less initial setup, but makes quality gates easier for both humans and agents to omit and
provides no enforcement for commit-message structure.

## Consequences

### Positive

- Contributors and agents can reproduce the development environment from one lockfile.
- Formatting, lint, typing, tests, repository hygiene, and commit messages have executable gates.
- Tool responsibilities are explicit and have little overlap.

### Negative

- Python 3.14 may initially have a smaller third-party compatibility surface than older releases.
- Local commits depend on uv and the selected Python minor line being available.
- Strict typing and docstring rules add work when new production modules are introduced.

### Follow-up

- Reconsider the Python minor line if a required runtime dependency does not support it.
- Treat changes to the toolchain's scope or enforcement model as a review of this decision.

## Related documentation

- [Documentation and knowledge policy](ADR-0001-documentation-policy.md)
- [Repository agent instructions](../../AGENTS.md)

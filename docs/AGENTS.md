# Documentation instructions

These instructions apply to every file under `docs/`. Project documentation is intentionally thin: it preserves durable information that cannot be reliably reconstructed from code, while code and tests describe the current implementation.

## Authority

- Code and tests are authoritative for current system behavior.
- `requirements/` is authoritative for accepted product outcomes, acceptance criteria, constraints, and non-goals.
- `domain/` and accepted ADRs are authoritative for agreed terminology, metric meaning, durable constraints, and decision rationale.
- `open-questions.md` is authoritative for explicitly unresolved product and design questions.
- `roadmap.md` describes outcome-oriented sequencing, not an implementation task list.
- `wiki/` is a non-authoritative synthesis and navigation graph.

Thin documentation does not mean that code is authoritative for product intent. It means documentation must not duplicate facts that are more reliably verified in code and tests.

## Reading documentation

1. Start at `index.md` and locate the requirement closest to the task.
2. Follow only the relevant domain, ADR, open-question, and related-requirement links.
3. Treat implementation and test links as navigation hints, not proof that the linked behavior is still current.
4. Verify current behavior in code and representative tests.
5. Use the repository `$query-project-wiki` skill when the task needs cross-document relationships, concept neighbors, or code and test entry points from the Wiki.

Do not load the entire documentation tree for a local task. Expand the reading set only when the current sources expose a dependency, ambiguity, or conflict.

## Writing documentation

Update documentation when a change affects an accepted requirement, acceptance criterion, non-goal, domain definition, metric meaning, durable constraint, architectural boundary, roadmap outcome, open question, or consequential decision rationale.

Do not document:

- function or class behavior that can be read from code;
- control flow, data structures, module layout, or the current implementation technique;
- temporary plans or ordinary refactoring choices;
- exhaustive test inventories;
- speculative decisions presented as accepted policy.

Prefer links and concise rationale over copied definitions. When implementation is mentioned, state what should be verified and point to representative evidence instead of narrating mechanics.

## Requirements

- Use `requirements/TEMPLATE.md` for a new requirement.
- Keep one externally meaningful outcome per requirement.
- Change an accepted outcome only with explicit authorization and related decision context.
- Retain superseded requirements and link both directions.
- Link only representative acceptance, contract, integration, or domain tests in `Verification`.
- Map linked tests to the acceptance criteria they cover and keep verification gaps visible.

## Architecture decisions

- Use `decisions/TEMPLATE.md` for a new ADR.
- Create an ADR when the selected direction and its rationale would be difficult to reconstruct from code.
- Do not materially rewrite an accepted decision. Create a new ADR that supersedes it.
- Keep candidate approaches in `open-questions.md` until a decision is accepted.

## Validation

After changing documentation:

```bash
python3 scripts/docs_lint.py
```

Review the diff for duplicated implementation detail, unintended requirement changes, unsupported claims, missing verification gaps, and Wiki cascade impact.

# Repository agent instructions

These instructions apply to the entire repository. More specific `AGENTS.md` files add rules for their directory. Read `docs/AGENTS.md` before working with project documentation, and read `wiki/AGENTS.md` before modifying the knowledge graph.

## Sources of truth

- Code and tests are authoritative for current system behavior.
- `docs/requirements/` is authoritative for accepted product outcomes.
- `docs/domain/` and accepted ADRs are authoritative for agreed terminology, metric meaning, constraints, and decision rationale.
- `wiki/` is an LLM-maintained synthesis and navigation graph. It is not authoritative for behavior or policy.
- Treat documentation as context for what to inspect. Verify implementation claims in code and tests.

## Context acquisition

Before changing code:

1. Read `docs/AGENTS.md` and identify the relevant requirements, domain definitions, decisions, constraints, and open questions.
2. Read only the documentation needed to establish normative intent for the active task.
3. Whenever obtaining project knowledge or repository navigation from `wiki/`, use the repository `$query-project-wiki` skill.
4. Verify current behavior in code and representative tests before making implementation decisions.

Do not read all Docs or Wiki pages by default. Build scoped context and expand only when a relevant link, conflict, or uncertainty requires it.

## Sol-Luna delegation

- The primary agent, Sol, owns user discussion, requirements clarification, consequential decisions, and final acceptance.
- When the user has explicitly approved a concrete direction and only bounded implementation, tests, documentation, and verification remain, invoke the repository `$handoff-to-luna` skill and delegate the work to the `luna_worker` custom agent.
- Do not delegate while material requirements, architecture, data policy, scope, or authorization remain unresolved.
- Use only one write-capable Luna agent at a time. Sol must not edit overlapping files while Luna is working.
- Luna must return ambiguity or source conflicts to Sol instead of deciding them. Sol reviews Luna's diff and validation evidence before reporting completion to the user.

## Development workflow

- Develop behavior changes using test-driven development.
- Follow the red-green-refactor loop:
  1. Write the smallest test that expresses the next observable behavior or contract.
  2. Run it and confirm that it fails for the intended reason before changing production code.
  3. Implement only enough production code to make the test pass.
  4. Refactor only while the relevant tests remain green.
  5. Run the broader affected test suite.
- Prefer tests of public behavior, domain invariants, and boundary contracts over private implementation details.
- Choose the narrowest test level that provides credible evidence, and add higher-level acceptance or integration coverage when a Requirement crosses boundaries.
- Do not skip the red step by writing tests only after the implementation.
- If an executable test is not appropriate for a documentation-only, generated-file, or development-configuration change, state that explicitly and run the relevant structural or tool validation instead.

## Python development conventions

### Environment and dependencies

- Use `uv` to manage the Python version, project environment, dependencies, lockfile, and Python commands.
- Pin the supported Python minor version in both `.python-version` and `project.requires-python`.
- Declare runtime dependencies in `project.dependencies` and development tools in `dependency-groups.dev`.
- Commit `uv.lock`. Dependency metadata and the lockfile must change together.
- Add, update, and remove dependencies with `uv add`, `uv lock`, and `uv remove`; do not install project dependencies directly with `pip`.
- Run project tools through `uv run --locked` so an outdated lockfile fails instead of being silently rewritten.
- Do not add a production dependency without checking its necessity, maintenance status, license, and effect on the lockfile.

### Python quality

- Use Ruff as the Python formatter and linter. Format during development; commit-time checks must be check-only and must not leave unreviewed changes.
- Add type annotations to production function and method parameters and return values.
- Use the configured static type checker for production code. Avoid `Any` outside external-library boundaries, and explain every targeted type suppression.
- Write Google-style docstrings for public modules, classes, functions, and methods, and for private code that is non-trivial or non-obvious.
- Docstrings must describe the caller-facing contract, semantics, units, precision, side effects, exceptions, and interpretation constraints when relevant. Do not restate the signature or narrate implementation mechanics.
- Test functions and trivial private helpers do not require docstrings when their names and types already communicate the relevant behavior.

### Tests

- Use pytest for Python tests.
- Add or update tests with every behavior change. Every bug fix requires a regression test that fails without the fix.
- Use representative acceptance, contract, integration, or domain tests to verify Requirement acceptance criteria where appropriate.
- Keep unit tests deterministic and isolated from real networks, clocks, random sources, and external services. Control those dependencies explicitly.
- Preserve the distinction among an empty valid result, missing data, invalid data, and an external-source failure.

## Commit conventions

- All configured pre-commit hooks must pass before a commit is created.
- Never bypass hooks with `--no-verify` unless the user explicitly authorizes that specific commit.
- Use Commitizen with the `cz_conventional_commits` convention: `<type>(<optional-scope>): <description>`.
- Use one of these commit types unless the Commitizen configuration explicitly changes them: `feat`, `fix`, `docs`, `style`, `refactor`, `perf`, `test`, `build`, `ci`, `chore`, or `revert`.
- Write commit messages in English. Use a concise imperative description that begins with a lowercase letter and has no trailing period.
- Keep each commit focused on one logical change. Mark breaking changes with `!` or a `BREAKING CHANGE:` footer.
- Install both the `pre-commit` and `commit-msg` hook stages when the toolchain is bootstrapped.

## Architecture conventions

- Read `docs/architecture/overview.md` before introducing or changing a package boundary or dependency direction.
- Architecture documentation defines intended boundaries, responsibilities, and allowed dependency directions. Code and tests define the current module and import graph.
- Do not duplicate the current package tree or individual imports in architecture documentation.
- When an architecture boundary is accepted, enforce prohibited dependencies mechanically where practical.
- Record a consequential architecture choice and its rationale in an ADR; keep unresolved candidates in `docs/open-questions.md`.

## Python verification

Once the Python toolchain is configured, the standard local verification sequence is:

```bash
uv lock --check
uv run --locked ruff format --check .
uv run --locked ruff check .
uv run --locked pyright
uv run --locked pytest
uv run --locked pre-commit run --all-files
```

Do not claim these checks passed before `pyproject.toml`, `uv.lock`, and `.pre-commit-config.yaml` exist. During toolchain bootstrap, either create the missing configuration as part of the authorized task or report the checks as not yet available.

## Knowledge impact review

Every task that changes the worktree must review documentation and wiki impact before completion. A review is required even when the correct result is `No material`.

Update `docs/` when a change affects an accepted requirement, acceptance criterion, non-goal, domain definition, metric meaning, durable constraint, architectural boundary, roadmap outcome, open question, or consequential decision rationale. Link representative acceptance, contract, integration, or domain tests when they become useful verification evidence. Do not document ordinary implementation mechanics.

Update `wiki/` when a source change creates durable knowledge, changes a conceptual relationship, introduces a dispute, resolves an open question, or adds, moves, or invalidates important implementation evidence. Ordinary bug fixes and internal refactors normally have no material wiki impact unless they expose a missing policy or invalidate graph evidence.

Before finishing a change:

1. Inspect the complete Git diff and run `python3 scripts/knowledge_review.py inspect`.
2. Classify Docs impact as `updated` or `no-material`.
3. Classify Wiki impact as `new`, `updated`, `disputed`, or `no-material`.
4. Update affected files, or record a specific reason why there is no material impact.
5. Run `python3 scripts/docs_lint.py` and `python3 scripts/wiki_lint.py`.
6. Record the review against the final diff:

   ```bash
   python3 scripts/knowledge_review.py record \
     --docs <updated|no-material> \
     --wiki <new|updated|disputed|no-material> \
     --docs-reason "<specific Docs reason>" \
     --wiki-reason "<specific Wiki reason>"
   ```

7. Run `python3 scripts/knowledge_review.py check`. Any later worktree change makes the prior review stale, so repeat the review after further edits.

The final response for a change must include:

```text
Docs impact: Updated | No material — <reason>
Wiki impact: New | Updated | Disputed | No material — <reason>
```

## Required checks

Run the checks relevant to the change, including project tests once they exist. Documentation changes always require:

```bash
python3 scripts/docs_lint.py
python3 scripts/wiki_lint.py
python3 scripts/knowledge_review.py check
```

Do not bypass a failing knowledge gate by creating unrelated documentation changes. Fix structural failures, update materially affected knowledge, or record an honest `No material` decision.

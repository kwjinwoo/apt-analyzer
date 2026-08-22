---
name: handoff-to-luna
description: Create a decision-complete handoff and delegate bounded implementation, tests, and documentation to the project Luna worker. Use when the user and primary agent have explicitly agreed on direction and scope, no product decision remains open for the delegated work, and only execution and verification remain. Do not use during discovery, requirements negotiation, unresolved architecture decisions, or read-only analysis.
---

# Handoff to Luna

Keep the primary agent, Sol, responsible for user discussion, decisions, and final acceptance. Use
Luna as a single execution-focused writer after agreement is complete.

## Gate the delegation

Delegate only when all of these conditions hold:

- The user has explicitly authorized implementation or documentation work.
- The intended outcome, scope, non-goals, and acceptance criteria are concrete.
- Material product, domain, architecture, and data-policy questions are resolved or explicitly out
  of scope.
- The work can proceed without new authority, destructive actions, or external coordination.
- The repository is in a state where Luna can distinguish existing user changes from its own work.

If any condition fails, continue the discussion as Sol. Do not send an ambiguous task to Luna.

## Build the handoff packet

Construct a self-contained prompt with this structure. Prefer links and identifiers over copied
prose.

```text
Objective:
User-approved decisions:
In scope:
Out of scope:
Acceptance criteria:
Authoritative Docs and relevant Wiki entry points:
Current code and test evidence to verify:
TDD starting point and expected first failing test:
Docs/Wiki impact to review:
Required validation commands:
Allowed external or destructive actions:
Escalate to Sol when:
Return to Sol with:
```

Always require Luna to return changed-file scope, test evidence, validation results, Docs/Wiki
impact, and unresolved issues. State that commit and push are unauthorized unless the user already
authorized them for this task.

## Delegate

Spawn exactly one project custom agent named `luna_worker` for write work and pass the handoff
packet unchanged. Do not run another writer in parallel against the same worktree. Sol may continue
read-only coordination while Luna works, but must not edit overlapping files.

If the current Codex surface cannot select the configured `luna_worker` role, report that limitation
instead of claiming Luna was used. Continue without Luna only when the user authorizes the fallback.

Wait for Luna to finish. Use a follow-up task for a bounded correction when the handoff remains
valid. If Luna reports a missing decision, contradictory source, required scope expansion, or new
authority requirement, stop delegation and return the issue to the user as Sol.

## Review and finish as Sol

After Luna returns:

1. Inspect the complete diff and verify that it stays within the handoff.
2. Confirm the red-green-refactor evidence for behavior changes.
3. Run or independently confirm the relevant repository validation.
4. Check Docs and Wiki impact and the knowledge-review receipt.
5. Ask Luna for a correction if the agreed outcome is incomplete; do not silently broaden scope.
6. Report the consolidated result to the user. Commit or push only when authorized.

Sol remains accountable for the final answer even when Luna performed all file changes.

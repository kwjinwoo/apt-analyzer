---
name: query-project-wiki
description: Retrieve scoped project context, concept relationships, unresolved questions, and repository navigation from the apt-analyzer Wiki. Use whenever a task reads or relies on wiki/ to investigate requirements, metrics, data policies, architecture, implementation entry points, tests, or cross-document dependencies before answering, planning, reviewing, or changing code.
---

# Query Project Wiki

Use the Wiki as a graph-backed navigation layer. Do not treat it as authoritative for product policy or current behavior.

## Workflow

1. Read `wiki/index.md` to choose the closest topic or project map.
2. Search `wiki/` for the task's primary terms, stable IDs, aliases, and closely related terms. Prefer `rg` for repository search.
3. Read the smallest relevant set of topic pages. Follow meaningful one-hop Wiki connections when they can change the task's interpretation, scope, or likely entry points.
4. Open the linked authoritative requirements, domain documents, ADRs, and open questions. Let those sources control normative claims.
5. For claims about current behavior, inspect the linked code and representative tests during the current task. If no evidence link exists, locate the implementation independently before relying on the claim.
6. Build a scoped context packet for the active task containing:
   - normative intent and constraints;
   - relevant concepts and relationships;
   - unresolved questions or disputed claims;
   - likely code and test entry points;
   - claims that still require verification.
7. Continue with the user's task using that context. Cite or name supporting repository sources when reporting conclusions that depend on them.

## Scope control

- Do not read the entire Wiki by default.
- Expand beyond one hop only when a discovered dependency, ambiguity, or conflict is material to the task.
- Stop when normative intent, current-behavior verification targets, and relevant uncertainty are sufficiently clear to proceed.
- Do not copy Wiki prose into Docs or code comments as a substitute for verifying its sources.

## Conflicts and stale evidence

- If the Wiki conflicts with Docs, code, or tests, do not silently reconcile the conflict. Prefer the authoritative source and report the discrepancy.
- Treat a broken, moved, or contradicted evidence link as a Wiki impact candidate for the task's completion review.
- Keep an unresolved candidate visibly unresolved. Do not infer an accepted policy from Wiki synthesis.

## Write boundary

- Do not modify Wiki files during an ordinary query.
- If the user asks to update or maintain the Wiki, finish the query first, then read `wiki/AGENTS.md` and follow its ingest, graph, decomposition, and lint rules.
- Create an archive page only when the user explicitly asks to preserve a point-in-time synthesis.

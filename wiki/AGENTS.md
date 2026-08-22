# Wiki maintenance instructions

These instructions apply to every file under `wiki/`. The wiki is an LLM-maintained synthesis and navigation graph. It does not replace human-approved documentation, code, or tests.

## Authority and ownership

- Requirements, domain definitions, and accepted ADRs under `docs/` are authoritative for product intent, terminology, metric meaning, constraints, and decision rationale.
- Code and tests are authoritative for current behavior.
- Wiki pages synthesize relationships among those sources and provide paths for investigation.
- An agent may write and maintain the wiki. Humans review changes through Git diffs and direct the synthesis.
- If the wiki conflicts with docs, code, or tests, do not silently reconcile the conflict. Mark or report it and update the wiki only after checking the authoritative source.

## Page model

Every living knowledge page must have YAML frontmatter with these fields:

```yaml
---
title: Page title
type: domain
role: topic
status: active
updated: YYYY-MM-DD
aliases: []
tags: []
---
```

Allowed values:

- `type`: `domain`, `metric`, `data`, `project`, `archive`
- `role`: `topic`, `hub`
- `status`: `active`, `disputed`, `outdated`, `archived`

Use standard relative Markdown links. Do not use Obsidian-only wikilinks. A living page should contain these sections unless its role makes one irrelevant:

- `Scope`
- `Knowledge`
- `Graph connections`
- `Requirements`
- `Decisions and open questions`
- `Evidence and interpretation risks`
- `Verify in the repository`
- `Related pages`

Write `None.` or `No implementation evidence exists yet.` instead of omitting a deliberately empty section.

## Graph rules

- One independently queryable concept belongs on one page.
- Internal Markdown links between wiki pages are graph edges.
- Links to docs, code, and tests are evidence or navigation edges.
- Every living topic page must have at least one meaningful internal outgoing link.
- Every living page should have an incoming link from another living page; the root index alone does not prevent orphan status.
- Hub pages created by decomposing a larger topic contain a `Topics` section that lists child topics. Each child links back to its hub.
- Cycles are allowed and often useful. Do not require every ordinary edge to be reciprocal.
- Name pages by concept, never by source document, date, or part number.

## Sources and claims

- Link normative claims to the relevant requirement, domain document, ADR, or open question.
- Do not copy a metric definition when a link and a short synthesis are sufficient.
- Do not claim current implementation behavior without inspecting code and tests during the current task.
- In `Verify in the repository`, point to representative symbols and tests when they exist. Do not invent future paths.
- A candidate policy must remain visibly unresolved until an accepted ADR or requirement resolves it.
- External evidence that carries a durable project claim should first be captured or referenced through the appropriate documentation process.

## Ingest

Ingest is required when a source change creates durable knowledge or changes existing relationships. Typical triggers include a new or materially changed requirement, accepted or superseded ADR, resolved open question, validated data-source finding, durable experiment result, or first implementation evidence for a concept.

1. Read `wiki/index.md` and search the full wiki for the source's concepts and aliases.
2. Classify the source impact as `New`, `Update`, `Disputed`, or `No material` in the active task or PR description. Do not create a permanent wiki log.
3. Prefer updating an existing concept page over creating a source-summary page.
4. Search for cascade effects and update every materially affected living page.
5. Update `wiki/index.md` when pages are added, removed, renamed, or materially reclassified.
6. Run mechanical wiki lint.
7. Review the Git diff for duplicated definitions, unsupported claims, and missed neighbors.

`No material` is a valid outcome. Wording-only source changes and internal refactors do not require wiki edits.

## Query

Use the repository `$query-project-wiki` skill whenever retrieving knowledge or repository navigation from the Wiki. An ordinary query must not modify Wiki files. Follow the maintenance rules in this file only when the task requires an ingest, correction, decomposition, or explicitly requested archive.

## Archive

- Archive pages are point-in-time query results under `wiki/archive/`.
- Use `type: archive`, `role: topic`, and `status: archived`.
- Archive pages cite the living pages used to produce the answer.
- Never cascade-update an archive as if it were current knowledge.
- If its sources change materially, semantic lint may report the archive as stale.

## Page decomposition

Semantic cohesion takes priority over file size.

- Review pages above 1,500 words for possible decomposition.
- Split pages above 2,500 words when they contain independently queryable concepts.
- Pages above 5,000 words require a non-empty `size_exception` in frontmatter.
- Preserve the original path as a concise hub when splitting a page.
- Name child pages after concepts, not `part-1`, `details`, `misc`, or similar containers.
- Do not duplicate child content in the hub.
- Update inbound links, child backlinks, and the index after a split.

## Lint

Run:

```bash
python3 scripts/wiki_lint.py
```

Mechanical lint checks frontmatter, allowed values, required sections, local paths and anchors, index consistency, graph connectivity, orphans, hub backlinks, meaningless filenames, and page-size rules. Broken references and invalid schema are errors. Orphans, disconnected components, weak graph connectivity, and review-size pages are warnings unless a stricter rule applies.

Semantic lint is an agent review. Inspect changed pages, their one-hop wiki neighbors, and linked docs for contradictions, outdated policies, duplicated concepts, missed cascade updates, unsupported implementation claims, and candidate policies presented as accepted. Report factual concerns with evidence; do not auto-fix facts or decisions.

Do not maintain `wiki/log.md`. Git history, task context, issues, and pull requests are the operational record.

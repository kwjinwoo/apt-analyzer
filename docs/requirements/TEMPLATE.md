---
id: R-XXX
title: Requirement title
status: proposed
priority: P0
created: YYYY-MM-DD
updated: YYYY-MM-DD
origin: null
supersedes: []
superseded_by: null
related_requirements: []
related_decisions: []
---

# R-XXX: Requirement title

## Intent

Explain the user problem and why this outcome matters. Describe the desired outcome, not an implementation.

## Requirement

State one clear and externally observable system requirement.

## Acceptance criteria

- **AC-1:** State a verifiable outcome.
- **AC-2:** State an important boundary or failure outcome.

## Constraints

- List data, accuracy, interpretation, or presentation constraints.

Use `None` when there are no requirement-specific constraints.

## Non-goals

- List adjacent behavior that this requirement does not promise.

Use `None` when the scope is already unambiguous.

## Verification

### Automated

Not established yet.

When tests exist, link only representative evidence and identify the covered acceptance criteria:

```markdown
- Acceptance test file: `tests/acceptance/test_example.py`
  - `test_observable_outcome` — AC-1
```

### Manual or data validation

None.

### Verification gaps

- Record acceptance criteria that do not yet have adequate evidence.

## Open questions

- [OQ-XXX](../open-questions.md#oq-xxx-question-title)

Use `None` when there are no unresolved questions.

## Related documentation

- [Glossary](../domain/glossary.md)
- [Metric definitions](../domain/metrics.md)
- Related ADR, when one exists

# apt-analyzer Documentation

This documentation records information that cannot be reliably reconstructed from the code alone: product requirements, domain meaning, architectural intent, accepted decisions, constraints, and unresolved questions.

The documentation is a context and navigation layer. It is not an alternative description of the current implementation. When documentation mentions behavior, verify the current behavior in code and tests.

## Start here

1. [Requirements](requirements/index.md) defines the product outcomes the system must provide.
2. [Glossary](domain/glossary.md) defines the domain language used by the project.
3. [Metric definitions](domain/metrics.md) defines the meaning and interpretation limits of the initial analytics.
4. [Architecture overview](architecture/overview.md) explains the intended system boundaries and dependency direction.
5. [Roadmap](roadmap.md) organizes development around outcomes and completion criteria.
6. [Open questions](open-questions.md) records issues that require evidence or a decision.
7. [Architecture Decision Records](decisions/index.md) explains accepted and superseded decisions.
8. [LLM-maintained wiki](../wiki/index.md) connects these sources as a navigable knowledge graph.

## Authority

| Question | Authoritative source |
|---|---|
| What outcome must the product provide? | Requirements |
| What does a domain term or metric mean? | Domain documentation and accepted ADRs |
| Why was an important design direction selected? | ADRs |
| What does the system currently do? | Code and tests |
| What is currently being worked on? | Issues, pull requests, or the active agent task |
| What was previously written? | Git history |

## Documentation rules

- Do not duplicate function behavior, control flow, data structures, or current implementation details.
- Link requirements to representative acceptance, contract, integration, or domain tests once those tests exist.
- Keep unresolved matters in [open questions](open-questions.md); do not present candidates as decisions.
- Record a consequential decision in an ADR when its rationale would be difficult to recover from code.
- Keep roadmap entries outcome-oriented. Implementation task lists belong in issues or active plans.
- Use stable document IDs in links and discussion: `R-XXX`, `OQ-XXX`, and `ADR-XXXX`.

# Release Design Documents

Design docs for each feature release. Each doc specifies deliverables, requirements covered,
design guidance, testability considerations, and acceptance criteria.

---

## Releases

| Release | Title | Status |
| --- | --- | --- |
| [R0](r0_foundation/design.md) | Foundation | Completed |
| [R1](r1_database/design.md) | Database Layer | Complete |
| [R2](r2_ingestion/design.md) | Source Ingestion and Chunking | Complete |
| [R3](r3_extraction/design.md) | Extraction Pipeline | Complete |
| [R4](r4_review_load/design.md) | Human Review and Load | In Progress |
| [R5](r5_retrieval/design.md) | Retrieval and Answering | Pending R4 |
| [R6](r6_evaluation/design.md) | Evaluation | Pending R5 |

---

## Cross-Reference Index

| Document type | Location |
| --- | --- |
| ADRs | `docs/architecture/decisions/adr_00x.md` |
| Functional requirements | `docs/architecture/requirements/functional/fr_00x.md` |
| Non-functional requirements | `docs/architecture/requirements/non-functional/nfr_00x.md` |
| Workflows | `docs/guides/workflows.md` |
| Glossary | `docs/guides/reference.md` |
| Schemas | `saskan_lore/data/schema/` |
| Prompts | `saskan_lore/analyzer/` |
| Backlog | `docs/design/backlog.md` |

---

## Dependency Chain

```txt
R0 (done) → R1 → R2 → R3 → R4 → R5 → R6
```

Each release depends on the previous. R4 (human review and load) is the current priority.

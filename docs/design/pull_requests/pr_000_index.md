# Release Design Documents

Design docs for each feature release. Each doc specifies deliverables, requirements covered,
design guidance, testability considerations, and acceptance criteria.

These are instructions to the development team, not git pull requests in the strict sense.

---

## Releases

| Release | Title | Status |
| --- | --- | --- |
| [R0](r0_foundation/design.md) | Foundation | Completed |
| [R1](r1_database/design.md) | Database Layer | Ready to build |
| [R2](r2_ingestion/design.md) | Source Ingestion and Chunking | Pending R1 |
| [R3](r3_extraction/design.md) | Extraction Pipeline | Pending R2 |
| [R4](r4_review_load/design.md) | Human Review and Load | Pending R3 |
| [R5](r5_retrieval/design.md) | Retrieval and Answering | Pending R4 |
| [R6](r6_evaluation/design.md) | Evaluation | Pending R5 |

---

## Cross-Reference Index

| Document type | Location |
| --- | --- |
| ADRs | `docs/architecture/decisions/adr_00x.md` |
| Functional requirements | `docs/architecture/requirements/functional/fr_00x.md` |
| Non-functional requirements | `docs/architecture/requirements/non-functional/nfr_00x.md` |
| Workflows | `docs/design/workflows.md` |
| Glossary | `docs/design/reference.md` |
| Schemas | `saskan_lore/data/schema/` |
| Prompts | `saskan_lore/analyzer/` |

---

## Dependency Chain

```txt
R0 (done) → R1 → R2 → R3 → R4 → R5 → R6
```

Each release depends on the previous. R1 (database layer) is the current priority.

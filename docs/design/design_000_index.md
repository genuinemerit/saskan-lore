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
| [R4](r4_review_load/design.md) | Human Review and Load | Complete |
| [R5](r5_retrieval/design.md) | Retrieval and Answering | Complete |
| [R6](r6_evaluation/design.md) | Evaluation | Concluded at v0.6.2 (MVP experiment completion; not graduated) |

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

Each release depended on the previous. R6 (evaluation) concluded the MVP experiment at
`v0.6.2` — see `r6_evaluation/design.md` Status for the decision not to pursue v1.0.0
graduation, and `docs/design/backlog.md` for the direction of a possible next iteration.

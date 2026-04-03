# Release 0: Foundation

Status: **Completed**

## Objective

Establish the project structure, all design documentation, data schemas, prompt templates,
and the core chunking module. No runtime pipeline yet — this release defines the rules
everything else will follow.

---

## Deliverables

All completed:

- Repo structure and Python package scaffolding (`saskan-lore/saskan_lore/`)
- `pyproject.toml` with Poetry, Python 3.12, all dependencies declared
- Design docs: `workflows.md`, `reference.md`
- ADR-001 through ADR-007
- FR-001 through FR-008
- NFR-001 through NFR-005
- Database design sketch: `data/schema/data_schema.py`
- Prompt templates: `analyzer/extract_claims.txt`, `analyzer/structure_claims_metadata.txt`
- `analyzer/chunker.py` — sentence-aware, reproducible text chunker
- `analyzer/extractor.py` — OpenAI gpt-4o extraction; `extract_claims()` and `structure_claims()`
- Utility stubs: `utils/platform.py`, `utils/stamps.py`, `utils/file_io.py`,
  `utils/shell.py`, `utils/match_semver.py`

---

## Requirements Covered

| Ref | Item |
| --- | --- |
| ADR-001 | No training — retrieval only, local model |
| ADR-002 | SQLite + SQLAlchemy as system of record |
| ADR-003 | Claims as first-class records |
| ADR-004 | Truth-status awareness |
| ADR-005 | Relationships modeled from the start |
| ADR-006 | Scope limited to Covenant of Varkaar |
| ADR-007 | No lore expansion during extraction |
| NFR-005 | Pilot pragmatism — favor simplicity, keep artifacts inspectable |

---

## Notes

The database design sketch in `data/schema/data_schema.py` is a reference document,
not runnable code. It is superseded by the SQLAlchemy models built in R1.

`chunker.py` is complete. It is wired to the database in R2.

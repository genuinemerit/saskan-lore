# R1 Database Layer — Test Cases

Status: **Complete** — all 10 tests passing

---

## Scope

Unit tests for the R1 database layer: SQLAlchemy ORM models, schema structure,
default values, nullability, unique constraints, and FK enforcement.

All tests use an in-memory SQLite engine with FK pragma enabled.
Test module: `tests/unit/r1_database/test_r1_db.py`
Shared fixture: `tests/conftest.py::db_session`

---

## Test Cases

| ID | Test function | What it verifies | Status |
| --- | --- | --- | --- |
| TC-R1-01 | `test_all_tables_present` | All 9 tables exist after `create_all` | Pass |
| TC-R1-02 | `test_claim_status_default` | `Claim.status` defaults to `'pending'` on insert | Pass |
| TC-R1-03 | `test_timestamp_mixin_is_active_default` | `is_active` defaults to `True` on all models | Pass |
| TC-R1-04 | `test_document_region_nullable` | `Document.region=None` inserts without error | Pass |
| TC-R1-05 | `test_chunk_fk_orphan_raises` | `Chunk` with nonexistent `document_id` raises `IntegrityError` | Pass |
| TC-R1-06 | `test_claim_fk_orphan_raises` | `Claim` with nonexistent `chunk_id` raises `IntegrityError` | Pass |
| TC-R1-07 | `test_entity_canonical_name_unique` | Duplicate `canonical_name` on `Entity` raises `IntegrityError` | Pass |
| TC-R1-08 | `test_entity_alias_unique_constraint` | Duplicate `(entity_id, alias)` on `EntityAlias` raises `IntegrityError` | Pass |
| TC-R1-09 | `test_claim_entity_fk_orphan_raises` | `ClaimEntity` with nonexistent `claim_id` raises `IntegrityError` | Pass |
| TC-R1-10 | `test_full_insert_chain` | Full chain Document → Chunk → Claim → Entity → ClaimEntity inserts cleanly | Pass |

---

## Requirements Coverage

| Test | FR / NFR / ADR |
| --- | --- |
| TC-R1-01 | FR-001, FR-002, FR-003, FR-004, FR-005, FR-008 |
| TC-R1-02 | FR-004 (claim `status` default), ADR-004 |
| TC-R1-03 | NFR-004 (is_active audit column) |
| TC-R1-04 | FR-001 (optional region field) |
| TC-R1-05 | NFR-003 (FK enforcement) |
| TC-R1-06 | NFR-003, ADR-003 (claims linked to chunks and documents) |
| TC-R1-07 | FR-003 (entity canonical name uniqueness) |
| TC-R1-08 | FR-003 (alias uniqueness per entity) |
| TC-R1-09 | NFR-003 (FK enforcement on junction tables) |
| TC-R1-10 | FR-001–FR-004 (full pipeline insert chain) |

---

## Run Results

| Date | Command | Result |
| --- | --- | --- |
| 2026-03-30 | `poetry run pytest tests/unit/r1_database/test_r1_db.py -v` | 10 passed in 0.09s |

---

## Notes

- FK enforcement depends on `PRAGMA foreign_keys=ON` being set on every connection.
  The test fixture sets this explicitly via an event listener on the in-memory engine.
- `is_active` is a Python-side `default=True`, not a `server_default`.
  It is set by SQLAlchemy before the INSERT, so it is readable immediately after `flush()`.

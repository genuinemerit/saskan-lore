# R4 Review and Load — Test Cases

Status: **Complete** — all 10 tests passing

---

## Scope

Unit tests for the R4 review and load pipeline: `review_staging.py`,
`load_entities.py`, `load_relationships.py`, and `load_reviewed.py`.

All tests use the shared `db_session` fixture (in-memory SQLite, FK pragma ON,
fresh per test). No real staging files are read from `var/reviewed/` — each test
writes its own fixture JSON to `tmp_path`. `typer.prompt` and `typer.echo` are
patched in interactive review tests.

Test module: `tests/unit/r4_review_load/test_r4_review_load.py`
Shared fixture: `tests/conftest.py::db_session`

---

## Test Cases

| ID | Test function | What it verifies | Status |
| --- | --- | --- | --- |
| TC-R4-01 | `test_load_entities_inserts_from_staging` | Entities from places, characters, and factions lists are inserted with correct types; returned map contains correct name→id entries | Pass |
| TC-R4-02 | `test_load_entities_idempotent` | Calling `load_entities()` twice with the same staging data creates no duplicate Entity records | Pass |
| TC-R4-03 | `test_load_file_approved_claim_inserted` | A claim with `reviewed=true` is inserted into the DB with `status='approved'` | Pass |
| TC-R4-04 | `test_load_file_unreviewed_claim_skipped` | A claim with `reviewed=false` and no `status='rejected'` is not inserted; summary reflects skipped count | Pass |
| TC-R4-05 | `test_load_file_rejected_claim_inserted` | A claim with `status='rejected'` is inserted with `status='rejected'`, not silently dropped | Pass |
| TC-R4-06 | `test_load_file_invalid_claim_skipped` | A claim missing `source_span` fails validation and is not inserted; summary reflects skipped count | Pass |
| TC-R4-07 | `test_load_file_idempotent` | Loading the same staging file twice produces no duplicate Claim or Entity records | Pass |
| TC-R4-08 | `test_load_file_missing_chunk_raises` | `load_file()` raises `ValueError` when `chunk_id` references a chunk that does not exist in the DB | Pass |
| TC-R4-09 | `test_load_relationships_unknown_entity_skipped` | `load_relationships()` skips a relationship whose source entity is absent from `entity_map`; returns 0, raises no error | Pass |
| TC-R4-10 | `test_review_file_approve_writes_reviewed_true` | Approve action (`A`) in `review_file()` sets `reviewed=true` on the claim and writes the updated JSON back to disk | Pass |

---

## Requirements Coverage

| Test | FR / NFR / ADR |
| --- | --- |
| TC-R4-01 | FR-003 (entity catalog populated with canonical names and types) |
| TC-R4-02 | FR-003, NFR-003 (idempotent entity load; no phantom duplicates) |
| TC-R4-03 | FR-004, NFR-004 (reviewed claims inserted; human review gate respected) |
| TC-R4-04 | NFR-004 (unreviewed claims never enter DB as trusted) |
| TC-R4-05 | ADR-003, ADR-007 (rejected claims preserved in audit trail) |
| TC-R4-06 | NFR-003 (source span required; invalid records skipped not crashed) |
| TC-R4-07 | FR-004, NFR-003 (idempotent load; safe to re-run) |
| TC-R4-08 | NFR-003 (referential integrity; load fails cleanly on missing chunk) |
| TC-R4-09 | FR-005 (relationships skipped when referenced entities absent) |
| TC-R4-10 | NFR-004, ADR-007 (reviewer approves; staging file updated correctly) |

---

## Run Results

| Date | Command | Result |
| --- | --- | --- |
| 2026-04-03 | `poetry run pytest tests/unit/r4_review_load/test_r4_review_load.py -v` | 10 passed in 0.20s |

---

## Notes

- Staging JSON files are written to `tmp_path` per test — no writes to `var/reviewed/`.
- `load_file()` calls `session.commit()` internally; the shared `db_session` fixture
  supports this via StaticPool (single in-memory connection).
- `typer.prompt` is patched in TC-R4-10 to simulate reviewer keypresses without
  requiring interactive input.
- `load_relationships()` and `load_entity_aliases()` are called with empty lists by
  `load_file()` for all current tests — both are no-ops and are verified separately
  (TC-R4-09).

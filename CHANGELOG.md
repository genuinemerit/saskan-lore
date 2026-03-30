# Changelog

All notable changes are documented here.
Format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

---

## [0.1.3] - 2026-03-30

### Changed

- `LICENSE` — added explicit carve-out for lore source documents in `data/lore_texts/`
- `saskan_lore/data/lore_texts/COPYRIGHT` — new All Rights Reserved notice covering the
  six SaskanCanon PDF source documents; excluded from the MIT license
- Repository visibility changed from private to public

---

## [0.1.2] - 2026-03-30

### Changed

- `pyproject.toml` — bumped black dev dependency from `^24.8` to `^26.3`; resolves
  Dependabot security alert (arbitrary file writes via unsanitized cache filename)

---

## [0.1.1] - 2026-03-30

### Removed

- `matplotlib` removed from the `analytics` extra dependency; eliminates transitive
  Pillow vulnerability flagged by Dependabot

---

## [0.1.0] - 2026-03-30 — R1 Database Layer

### Added

- `saskan_lore/data/models.py` — SQLAlchemy ORM models for all 9 tables with `TimestampMixin`
  (`is_active`, `created_at`, `updated_at`), indexes, unique constraints, and FK constraints
- `saskan_lore/infra/db/db.py` — engine singleton, `get_session()` context manager,
  SQLite FK pragma hook, `reset_engine()` for test fixtures
- `saskan_lore/infra/db/dba.py` — DB admin/reporting utilities: `summary()`, `row_counts()`,
  `inactive_counts()`, `check_schema()`, `table_info()`, `show_rows()`, `alembic_version()`,
  `db_size()`
- `saskan_lore/infra/db/init_db.py` — one-shot DB initialisation via `alembic upgrade head`
- `alembic/` — Alembic configuration, initial schema migration, and FK constraint migration
- `data/saskan_lore.db` — local SQLite DB (gitignored); created and validated in DBeaver
- `tests/conftest.py` — shared pytest fixture: in-memory SQLite, StaticPool, FK pragma ON
- `tests/unit/r1_database/test_r1_db.py` — 10 unit tests covering schema structure, column
  defaults, nullability, unique constraints, FK enforcement, and full insert chain
- `tests/fixtures/`, `tests/output/` — test data directories
- `scripts/commit.sh`, `scripts/release.sh` — git commit and release automation scripts
- `docs/design/pull_requests/r1_database/test_cases.md` — R1 test case register
- `.pre-commit-config.yaml` — pre-commit hooks: black (formatting) and ruff (linting)

### Changed

- `pyproject.toml` — added `ruff` dev dependency; added pytest markers (`unit`, `integration`);
  activated semantic versioning starting at `v0.1.0`
- `saskan_lore/analyzer/character_counter.py` — promoted bare stub code to a proper function
- `docs/design/workflows.md` — added Testing and Version Control sections

---

## [Pre-release] - 2026-03-30

### Added

- Repo structure and Python package scaffolding (`saskan-lore/saskan_lore/`)
- `pyproject.toml` — Poetry, Python 3.12, all dependencies declared
- Design docs: `workflows.md`, `reference.md`
- ADR-001 through ADR-007 — architecture decisions
- FR-001 through FR-008 — functional requirements
- NFR-001 through NFR-005 — non-functional requirements
- Release design docs: R0 through R6
- Database design sketch: `data/schema/database_schema.py`
- Prompt templates: `analyzer/extract_claims.txt`, `analyzer/structure_claims_metadata.txt`
- `analyzer/chunker.py` — sentence-aware, reproducible text chunker
- `analyzer/extractor.py` — LLM-based claim extraction and structuring
- Utility modules: `tools/utils/platform.py`, `tools/utils/stamps.py`,
  `tools/utils/file_io.py`, `tools/utils/shell.py`, `tools/utils/match_semver.py`
- Six PDF lore source texts added to `data/lore_texts/`

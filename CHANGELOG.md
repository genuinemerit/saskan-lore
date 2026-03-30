# Changelog

All notable changes are documented here.
Format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

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

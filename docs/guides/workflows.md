# Workflows

## Pipeline

```text
saskan_lore/data/lore_texts/   →   analyzer/   →   var/reviewed/   →   loader/   →   SQLite DB
       (source PDFs)              (chunk +          (human review)     (DB load)
                                   extract)
```

Record state per artifact:

| State | Meaning |
| --- | --- |
| `raw` | original text passage |
| `extracted` | LLM output (untrusted) |
| `reviewed` | your corrected version (trusted) |
| `loaded` | persisted in DB |

---

## Stages

### Stage 1 — Source Selection

| | |
| --- | --- |
| **Input** | a lore passage or document in scope |
| **Output** | source registered as a document candidate |
| **Acceptance** | source is in scope; stable enough to extract from; has an identifier |

### Stage 2 — Chunking

| | |
| --- | --- |
| **Input** | one selected source document |
| **Output** | ordered chunks linked to document |
| **Acceptance** | chunk order preserved; boundaries reproducible; text unchanged except approved normalization |

### Stage 3 — Extraction

| | |
| --- | --- |
| **Input** | one chunk or small document section |
| **Output** | summary, entities, claims, source spans, claim type |
| **Acceptance** | no invented details; every claim has an evidence span; uncertain items marked accordingly |

### Stage 4 — Human Review

| | |
| --- | --- |
| **Input** | extracted draft records |
| **Output** | approved, corrected, or rejected records |
| **Acceptance** | all approved claims reviewed by you; no dubious claims silently loaded as trusted |

### Stage 5 — Load to DB

| | |
| --- | --- |
| **Input** | reviewed extraction records |
| **Output** | persisted documents, chunks, entities, claims, relationships |
| **Acceptance** | referential integrity holds; rerunning load is controlled and predictable |

### Stage 6 — Evaluation

| | |
| --- | --- |
| **Input** | stored evaluation questions |
| **Output** | retrieved evidence, generated answer, result record |
| **Acceptance** | answer includes supporting evidence; pass/fail recorded; notes allow failure analysis |

**Retrieval approach (MVP):** SQLite FTS5 full-text search over approved claims, ranked by BM25.
Returns top N claims as context for the model. Embedding-based retrieval is deferred to a later
release.

---

## Testing

### Structure

```text
tests/
  conftest.py          shared fixtures (db_session, etc.)
  unit/
    r1_database/       unit tests for R1 — DB models, schema, constraints
    r2_ingestion/      unit tests for R2 — document registration and chunking
    r3_extraction/     unit tests for R3 — extraction, staging utilities
    r4_review_load/    unit tests for R4 — review, load, entity and claim loading
    r5_retrieval/      unit tests for R5 — FTS5 retrieval, context formatting, answering
    r6_evaluation/     unit tests for R6 — eval questions, run, grade, summary, export
  integration/         cross-release tests: pipeline flows, acceptance criteria
```

Unit tests target a single release boundary (one module or a closely related group of
modules). Integration tests may cross release boundaries and verify end-to-end flows
or acceptance criteria that span multiple layers.

### pytest configuration

Settings are in `pyproject.toml`:

```toml
[tool.pytest.ini_options]
addopts = "-q"
testpaths = ["tests"]
```

pytest discovers all `test_*.py` files under `tests/` automatically.
No `__init__.py` files are required in test directories.

### Running tests

```bash
# Activate the venv and load env vars (once per shell session)
source scripts/poetry_activate.sh
source scripts/setenv.sh local

# Run all tests
poetry run pytest

# Run all unit tests for one release
poetry run pytest tests/unit/r1_database/

# Run a single test module
poetry run pytest tests/unit/r1_database/test_r1_db.py

# Run a single test function
poetry run pytest tests/unit/r1_database/test_r1_db.py::test_claim_status_default

# Run with verbose output
poetry run pytest -v tests/unit/r1_database/

# Run with coverage report
poetry run pytest --cov=saskan_lore tests/unit/

# Run only integration tests
poetry run pytest tests/integration/
```

### Test case documentation

Each release has a companion `test_cases.md` under its design folder, e.g.:

```text
docs/design/r1_database/test_cases.md
```

That file records planned test cases, requirements coverage, and run results.

---

## Version Control and Releases

### Semantic versioning

This project follows [semver.org](https://semver.org) with a three-part version number:
`MAJOR.MINOR.PATCH`. Build metadata suffixes are not used.

| Segment | When to bump |
| --- | --- |
| `MAJOR` | After mutual agreement — likely when all planned feature releases are complete |
| `MINOR` | At the completion of each feature release (R1, R2, ...) with all tests passing |
| `PATCH` | For any fix or correction to a released MINOR prior to the next MINOR |

The project starts at `v0.1.0`. MAJOR=0 signals initial/pre-production development per the
semver spec. `v1.0.0` marks the first stable, complete release.

Version tags are annotated (`git tag -a`) so they carry a tagger, date, and description.
The `pyproject.toml` version field is kept in sync with the current tag.

### Commit conventions

Use a short type prefix on every commit message. No tooling enforces this — it is
convention only.

| Prefix | Use for |
| --- | --- |
| `feat:` | new feature or capability |
| `fix:` | bug fix |
| `test:` | test additions or changes |
| `docs:` | documentation only |
| `chore:` | maintenance: dependencies, version bumps, config |
| `refactor:` | code restructuring with no behaviour change |

### Code quality on commit

`pre-commit` runs **black** (formatting) and **ruff** (linting) automatically on every
`git commit`. No manual step required. To run the hooks against all files manually:

```bash
poetry run pre-commit run --all-files
```

To update hook versions periodically:

```bash
poetry run pre-commit autoupdate
```

### Day-to-day commit workflow

```bash
# 1. Stage specific files, or all changes
git add <file> [<file> ...]
git add .                          # stage everything (respects .gitignore)

# 2. Commit — pre-commit hooks run automatically
git commit -m "feat: add chunker unit tests"

# 3. Push when ready (not required after every commit)
git push origin main
```

Or use the commit helper script, which also runs the test suite before committing:

```bash
./scripts/commit.sh "feat: add chunker unit tests"
./scripts/commit.sh "fix: correct FK name" --push   # also pushes
```

### Release workflow

Before tagging a MINOR release, manually update `CHANGELOG.md` to summarise what changed.

Then run the release script:

```bash
# Feature release complete (MINOR bump): v0.0.0 -> v0.1.0
./scripts/release.sh minor "R1 database layer complete"

# Fix after a release (PATCH bump): v0.1.0 -> v0.1.1
./scripts/release.sh patch "Fix entity alias unique constraint"
```

The release script:

1. Verifies the working tree is clean (no uncommitted changes)
2. Runs the full test suite (`poetry run pytest`)
3. Computes the next version from the most recent `v*` tag
4. Updates `pyproject.toml` version field
5. Commits the version bump (`chore: bump version to vX.Y.Z`)
6. Creates an annotated tag with the provided description
7. Pushes the branch and the tag to origin

### Viewing tags and history

```bash
# List all release tags, newest first
git tag --list 'v*' --sort=-version:refname

# Show tag detail (tagger, date, message)
git show v0.1.0

# Show log since a given tag
git log v0.1.0..HEAD --oneline
```

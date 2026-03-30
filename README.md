# saskan-lore

A lore catalog and AI-assisted query tool for the fictional world of **Saskantinon**.

---

## What it does

Worldbuilding produces a large amount of written material — documents, notes, and canon texts
that accumulate over time. Keeping facts consistent across that material is difficult. This
project builds a structured, queryable database of **claims** extracted from lore texts, so
that any fact can be traced back to its source.

The initial scope covers the **Covenant of Varkaar**, one region of Saskantinon.

---

## How it works

```text
PDF lore texts → chunker → LLM extraction → human review → SQLite DB → query / ideation
```

1. **Chunk** — source texts are split into short, retrievable passages.
2. **Extract** — a language model reads each passage and identifies discrete facts (*claims*),
   named entities, and relationships.
3. **Review** — a human checks all extracted output before it is stored. Nothing enters the
   database as trusted without review.
4. **Load** — approved records are written to a SQLite database via SQLAlchemy.
5. **Query** — stored claims and chunks support retrieval-augmented answers to lore questions.

---

## Key design choices

- **Claims are the unit of meaning.** Every claim is linked to a source span — the exact
  passage it came from. No claim without evidence.
- **Truth-status is explicit.** Each claim is labeled: `fact`, `belief`, `interpretation`,
  or `rumor`. The system tracks what is known versus what is merely believed in-world.
- **Human review is required.** LLM output is treated as untrusted until a person approves it.
- **No training.** The system uses retrieval-augmented generation (RAG). The model reads
  retrieved passages and answers from them — it does not learn from the lore data.
- **Local inference.** The target runtime model is a small (3B-parameter) open-weight model
  running locally via llama.cpp. No external API calls for the core pipeline.

---

## Project status

This is a pre-pilot learning project. Releases follow a defined dependency chain:

| Release | Name | Status |
| --- | --- | --- |
| R0 | Foundation | Complete |
| R1 | Database | Next |
| R2 | Ingestion | Planned |
| R3 | Extraction | Planned |
| R4 | Review and Load | Planned |
| R5 | Retrieval | Planned |
| R6 | Evaluation | Planned |

See [`CHANGELOG.md`](CHANGELOG.md) and [`docs/design/pull_requests/`](docs/design/pull_requests/)
for details.

---

## Getting started

Requires Python 3.12 and [Poetry](https://python-poetry.org/).

```bash
poetry install              # install dependencies and create virtual environment
source saskan-lore/tools/poetry_activate  # activate the environment
poetry run pytest           # run tests
```

---

## License

MIT — see [`LICENSE`](LICENSE).

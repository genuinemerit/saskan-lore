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
- **Local inference.** All model calls run locally via llama.cpp. No external API is used
  for the core pipeline.

---

## Models and hardware

The project runs on two machines with different models:

| Machine | OS | Model | Notes |
| --- | --- | --- | --- |
| Apple M2 Pro desktop | macOS | Qwen2.5-7B-Instruct-Q4_K_M | Runs on Metal GPU |
| Dell XPS 13 laptop | Ubuntu Linux | Qwen2.5-3B-Instruct-Q4_K_M | Runs on CPU only |

The Mac uses a larger (7B) model because the Metal GPU makes it fast enough. The Linux
laptop uses a smaller (3B) model to keep inference time reasonable on CPU. Both use the
same quantized GGUF format. Model files are stored in `~/models/` on each machine and
are not part of the repository.

---

## Project status

This is a pre-pilot learning project. Releases follow a defined dependency chain:

| Release | Name | Status |
| --- | --- | --- |
| R0 | Foundation | Complete |
| R1 | Database | Complete |
| R2 | Ingestion | Complete |
| R3 | Extraction | Complete |
| R4 | Review and Load | In Progress |
| R5 | Retrieval | Planned |
| R6 | Evaluation | Planned |

Current version: v0.3.0

The extraction pipeline (R3) is complete. The local model reads lore text chunks and
produces structured JSON files with claims, entities, and source spans. R4 adds the
human review step and loads approved records into the database.

See [`CHANGELOG.md`](CHANGELOG.md) and [`docs/design/`](docs/design/) for details.

---

## Getting started

Requires Python 3.12 and [Poetry](https://python-poetry.org/).

```bash
poetry install                     # install dependencies
source scripts/poetry_activate.sh  # activate the environment
source scripts/setenv.sh           # set LOCAL_MODEL_PATH and LLAMA_N_GPU_LAYERS
poetry run pytest                  # run tests
```

---

## License

MIT — see [`LICENSE`](LICENSE).

The lore source documents in `saskan_lore/data/lore_texts/` are **not** covered by the
MIT license. See [`saskan_lore/data/lore_texts/COPYRIGHT`](saskan_lore/data/lore_texts/COPYRIGHT).

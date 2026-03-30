# Glossary

Terms, acronyms, and concepts used in this project.

---

## 3B Class Model

A language model with approximately 3 billion parameters. Small enough to run on consumer hardware without a dedicated GPU, large enough for structured extraction tasks such as claim identification and metadata labeling.

---

## ADR (Architecture Decision Record)

A short, dated document capturing a design decision, its context, options considered, and consequences. One ADR per decision, stored in `docs/architecture/decisions/`.

Example: ADR-002 — Use SQLite as the system of record.

---

## Chunk

A retrievable slice of a Document, stored in the database. Typically one to two sentences. Chunks are the unit of retrieval.

Example: "The Covenant of Varkaar governed oath law in the northern provinces during the Ashen Era."

---

## Claim

A discrete, source-quoted fact extracted from a Chunk. Claims are the primary unit of meaning in the system — every claim must be traceable to a source span.

Example: claim text = "The Varkaar regarded oath-breaking as a capital offense", source_span = "...oath-breakers were put to death by the Covenant..."

---

## Document

A narrative source text. Stored under `data/lore_texts/`. The starting point of the pipeline.

Example: `SaskanCanon-VarkaarCovenant.pdf`

---

## GGUF

A binary file format for storing quantized language models, used by llama.cpp. A GGUF file packages model weights and metadata into a single portable file. Quantized weights are stored at reduced precision (e.g., 4-bit or 8-bit integers) to reduce memory footprint and enable CPU inference without a GPU.

Example: `qwen2.5-3b-instruct-q4_k_m.gguf`

---

## LLM (Large Language Model)

A type of AI model trained on large amounts of text. Given a text input (a *prompt*), it
generates a text response. LLMs do not look up facts — they predict plausible output based
on patterns learned during training. This makes them useful for tasks like extracting
structured data from prose, but it also means their output can contain errors.

In this project, an LLM reads lore text chunks and identifies claims, entities, and
relationships. All output is treated as untrusted until a human reviews it.

---

## Llama 3

An open-weight language model family released by Meta, available in 1B, 3B, 8B, and larger sizes. GGUF-format versions suitable for local llama.cpp inference are available via Hugging Face.

---

## M2 Mac vs. Dell Linux Laptop (Local Inference)

Apple Silicon M2 uses a unified memory architecture in which the CPU and GPU share the same high-bandwidth memory pool. llama.cpp uses the Metal GPU backend on M2, accelerating inference significantly — even for 3B models.

An older Intel/AMD Dell laptop running Ubuntu runs llama.cpp CPU-only, with no GPU offloading. This is substantially slower for the same model and quantization level.

For this project, the M2 Mac is the preferred local inference machine.

---

## Qwen

An open-weight language model family from Alibaba (Qwen 2.5). The 3B instruct variant is well-suited for structured extraction tasks at small scale. GGUF versions are available for local inference via llama.cpp.

---

## RAG (Retrieval-Augmented Generation)

A pattern for grounding LLM answers in retrieved source material rather than model memory.

Steps:

1. Search chunks/claims for relevant passages.
2. Insert retrieved passages into the model prompt.
3. Model answers using only the supplied material.

Example: User asks "What did the Covenant believe about oath-breaking?" → system retrieves top 3 matching chunks → model answers from those chunks.

Used here because lore is custom, truth and traceability matter, and no training is planned.

---

## Testable (Claim)

A claim is testable if a specific question can be written against it with a verifiable answer.

| | Example |
| --- | --- |
| Not testable | "The Covenant was important." |
| Testable | "The Covenant of Varkaar governed oath law in the northern provinces during the Ashen Era." |

---

## Poetry (Virtual Environment)

[Poetry](https://python-poetry.org/) manages dependencies and the virtual environment for this
project. All commands assume Python 3.12.

**Activate the environment:**

```bash
source saskan-lore/tools/poetry_activate
```

Run this from the repo root. The script wraps `poetry env activate` so you do not need to
copy-paste the `eval` form each time. Use `deactivate` to exit.

**Common commands** (run outside an activated environment):

```bash
poetry install                           # install deps and create venv
poetry add <package>                     # add a dependency
poetry run <command>                     # run a command without activating
poetry lock --no-update && poetry install  # resync lock file and venv
poetry env list                          # list known environments
poetry env remove python                 # remove the current env (then reinstall)
```

Applications should commit `poetry.lock`. See `docs/design/workflows.md` for a quick reference.

---

## Type Annotations (`from __future__ import annotations`)

A future import that makes Python type hints lazy — stored as strings at runtime rather than evaluated immediately. Prevents circular import errors and is the default behavior in Python 3.11+.

Include at the top of any module that uses type hints.

# Release 3: Extraction Pipeline

Status: **In Progress**

## Objective

For each chunk, call the local GGUF model with the existing prompt templates, parse the
output, and write a structured JSON file to the `reviewed/` staging area. Extraction output
is untrusted until human review in R4. The model inference layer is isolated behind a
single interface function.

---

## Environment Setup Progress

| Machine | OS | llama-cpp-python | Model | Status |
| --- | --- | --- | --- | --- |
| Apple M2 Pro | macOS (Metal) | Installed (Poetry) | Qwen2.5-7B-Instruct-Q4_K_M | Installed, verified ✓ |
| Dell laptop | Ubuntu (CPU) | Installed (Poetry) | Qwen2.5-?B-Instruct-Q4_K_M | Installed (verify size) |

Notes:

- `LLAMA_N_GPU_LAYERS=-1` on Mac (all layers to Metal); `0` on Linux (CPU only)
- Model files stored at `~/models/` on each machine — outside Dropbox. See ADR-008.
- `setenv.sh` now auto-detects platform via `uname -s` and sets `LOCAL_MODEL_PATH`
  and `LLAMA_N_GPU_LAYERS` after sourcing the env file. `env.example` updated to
  document this. Model filenames are editable variables at the top of `setenv.sh`.

---

## Deliverables

- `saskan_lore/analyzer/inference.py` — model interface: single callable wrapping llama.cpp ✓
- `saskan_lore/analyzer/extractor.py` — formats prompt, calls inference, parses output,
  writes staging JSON ✓
- `saskan_lore/analyzer/staging.py` — utilities for reading/writing the `reviewed/` staging area
- CLI command: `saskan-lore extract --chunk-id <id>` (or batch: `--document-id <id>`)
- Staging output format matches `data/schema/extract_schema.json`
- Malformed model output saved with an `error` flag rather than silently dropped

---

## Requirements Covered

| Ref | Item |
| --- | --- |
| FR-003 | Entities identified during extraction (saved to staging, not yet to DB) |
| FR-004 | Claims extracted with source spans and truth-status labels |
| NFR-001 | Inference runs locally via llama.cpp; no external API |
| NFR-002 | Inference isolated behind `inference.py`; not called inline |
| NFR-003 | Source span required in extraction output schema |
| ADR-001 | Local GGUF model, 3B class (Qwen or Llama 3) |
| ADR-004 | Truth-status label extracted for each claim |
| ADR-007 | Prompt explicitly instructs model not to invent or infer beyond source |
| Workflow Stage 3 | Metadata/claim extraction from a chunk |
| Glossary | GGUF, 3B class, Qwen, Llama 3, RAG |

---

## Design Notes

### inference.py — the model interface

Expose a single function. All llama.cpp setup stays inside this module.

```python
def complete(prompt: str, *, max_tokens: int = 512, temperature: float = 0.1) -> str:
    """Send prompt to local GGUF model, return raw text response."""
    ...
```

The model path is read from config (not hardcoded). Temperature should be low (0.0–0.1)
for structured extraction — determinism matters more than creativity here.

Swapping to a different backend (e.g., a hosted API) requires changes only in this module.
See NFR-002.

### extractor.py — extraction flow

```txt
1. Load prompt template from prompts/extract_claims.txt
2. Format prompt with chunk.text
3. Call complete(prompt)
4. Attempt to parse response as JSON matching extract_schema.json
5a. If parse succeeds: write to reviewed/<chunk_id>_extraction.json
5b. If parse fails: write raw output to reviewed/<chunk_id>_extraction_error.json
    with { "error": true, "raw": "...", "chunk_id": ... }
```

The extractor does not write to the database. It only produces staging files.

### Staging file format

Each staging file follows `extract_schema.json`:

```json
{
  "chunk_id": "chunk_0042",
  "document_id": "doc_001",
  "summary": "...",
  "entities": [{"name": "...", "type": "..."}],
  "claims": [
    {
      "claim_text": "...",
      "source_span": "...",
      "truth_status": "fact",
      "reviewed": false
    }
  ]
}
```

All claims in staging have `reviewed: false`. The reviewer sets this to `true` in R4.

### Scope guard

Before extracting, check that the chunk's parent document has `scope="varkaar"`.
Reject out-of-scope chunks with a logged warning, not a hard error. See ADR-006.

### Prompt enforcement (ADR-007)

The prompt templates already include no-expansion instructions. Verify that
`extract_claims.txt` contains explicit language such as:

- "Extract only what is explicitly stated in the passage."
- "Do not infer, complete, or add details not present in the text."
- "If a detail is unclear, mark the claim as `interpretation`, not `fact`."

---

## Testability Considerations

- Mock `complete()` in tests to return fixture JSON strings — avoids needing the model.
- Test that a well-formed model response produces the expected staging file.
- Test that a malformed response (invalid JSON, missing fields) produces an `_error.json`
  file rather than crashing.
- Test the scope guard: a chunk from a non-varkaar document is skipped.
- Test that `reviewed` is always `false` in staging output, never `true`.

---

## Progress

### Environment Setup

- [x] `llama-cpp-python` installed via Poetry on both machines
- [x] Qwen2.5-7B-Instruct-Q4_K_M.gguf downloaded to `~/models/` on Mac M2 Pro (verified)
- [x] Qwen2.5-3B-Instruct-Q4_K_M.gguf downloaded to `~/models/` on Dell Linux (verify filename)
- [x] `scripts/setenv.sh` updated — auto-detects platform, sets `LOCAL_MODEL_PATH` and
  `LLAMA_N_GPU_LAYERS` (Darwin: gpu_layers=-1; Linux: gpu_layers=0)
- [x] `saskan_lore/infra/config/env.example` updated to document platform-specific model config
- [x] ADR-008 written — multi-environment configuration and platform-aware model selection

### Implementation

- [x] `saskan_lore/analyzer/inference.py` — `complete()`: env validation at import time,
  model loaded once at module level, single public function, no llama_cpp types exported
- [x] `saskan_lore/analyzer/extractor.py` — `extract_chunk()`: ChatML prompt formatting,
  scope guard, JSON parse + structural validation, staging file write, error file on failure;
  `reviewed=False` injected at write time
- [x] `saskan_lore/analyzer/staging.py` — staging area read utilities: `list_staging()`,
  `list_errors()`, `load_staging()`, `validate_staging()`, `load_for_document()`
- [x] CLI command: `saskan-lore extract --chunk-id <id>` / `--document-id <id>` — added
  to existing Typer app in `loader/ingest.py`; inference import deferred to avoid model
  load on unrelated commands
- [x] `saskan_lore/data/schema/extract_schema.json` — JSON Schema (draft 2020-12) for staging
  file validation; derived from `ExtractionRecord` and `ExtractionClaimRecord` dataclasses;
  enforces `reviewed=false` constraint, `truth_status` enum, `source_span` non-empty (NFR-003)

### Testing

- [x] `tests/unit/r3_extraction/test_r3_extraction.py` — 10/10 passing (TC-R3-01 through
  TC-R3-10); `llama_cpp` mocked via `sys.modules` in `conftest.py`

### Notes

- `extractor.py` replaces the earlier OpenAI-based stub. The old stub used `gpt-4o` and
  `response_format=json_object`; the new version calls `inference.complete()` only.
- ChatML prompt template (`_CHAT_TEMPLATE`) is a single constant in `extractor.py`.
  Switching models with a different chat format requires updating only that constant.
- `extract_schema.json` was created from `ExtractionRecord` / `ExtractionClaimRecord`
  dataclasses before tests were written, making the staging contract explicit up front.

---

## Acceptance Criteria

- Running `extract` on a chunk with a loaded model produces a valid staging JSON file.
- The staging file validates against `extract_schema.json`.
- All claims in staging have `reviewed: false`.
- A parse error produces an error-flagged file, not an exception.
- The `complete()` function is the only point of contact with the model — nothing in
  `extractor.py` imports llama.cpp directly.
- Out-of-scope chunks are skipped with a log message.

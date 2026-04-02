# -*- coding: utf-8 -*-
"""
extractor.py

Lore extraction pipeline for saskan-lore.

Public function:

    extract_chunk(chunk, document) -> Path | None
        Extract claims from a chunk using the local GGUF model.
        Writes a staging JSON file to REVIEWED_DIR and returns its path.
        On scope mismatch: logs a warning and returns None (no file written).
        On parse failure: writes an error-flagged file and returns that path.

The extractor does not write to the database. It produces staging JSON files only.
Human review of staging files occurs in R4 before any DB load.

See: R3 design doc, NFR-002 (replaceable model layer), NFR-003 (traceability),
     ADR-006 (varkaar scope guard), ADR-007 (no lore expansion).
"""

from __future__ import annotations

import json
import logging
import os
from pathlib import Path

from ..data.models import Chunk, Document
from .inference import complete

log = logging.getLogger(__name__)

_PROMPT_PATH = Path(__file__).parent / "extract_claims.txt"
_VALID_SCOPE = "varkaar"

# ChatML prompt format expected by Qwen2.5-Instruct (and compatible models).
# If switching to a model with a different chat template, update this constant
# only — no other changes required in this module. See NFR-002.
_CHAT_TEMPLATE = (
    "<|im_start|>system\n{system}\n<|im_end|>\n"
    "<|im_start|>user\n{user}\n<|im_end|>\n"
    "<|im_start|>assistant\n"
)

# Required top-level fields in a valid model response.
_REQUIRED_FIELDS = {"chunk_id", "document_id", "claims"}


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _get_reviewed_dir() -> Path:
    """Resolve and create REVIEWED_DIR from the environment."""
    raw = os.environ.get("REVIEWED_DIR", "").strip()
    if not raw:
        raise EnvironmentError("REVIEWED_DIR is not set. Run 'source scripts/setenv.sh' first.")
    path = Path(raw)
    path.mkdir(parents=True, exist_ok=True)
    return path


def _build_prompt(chunk: Chunk) -> str:
    """Format the full ChatML prompt for a chunk."""
    system = _PROMPT_PATH.read_text(encoding="utf-8")
    chunk_id = f"chunk_{chunk.id:04d}"
    document_id = f"doc_{chunk.document_id:03d}"
    user = f"chunk_id: {chunk_id}\n" f"document_id: {document_id}\n\n" f"Passage:\n{chunk.text}"
    return _CHAT_TEMPLATE.format(system=system, user=user)


def _chunk_label(chunk: Chunk) -> str:
    return f"chunk_{chunk.id:04d}"


def _write_staging(out_dir: Path, chunk: Chunk, data: dict) -> Path:
    """Write a successful extraction result to a staging JSON file.

    Adds reviewed=false to every claim before writing (NFR staging requirement).
    Returns the path written.
    """
    for claim in data.get("claims", []):
        claim["reviewed"] = False
    path = out_dir / f"{_chunk_label(chunk)}_extraction.json"
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def _write_error(out_dir: Path, chunk: Chunk, raw: str, reason: str) -> Path:
    """Write an error-flagged staging file for a failed extraction.

    Returns the path written.
    """
    payload = {
        "error": True,
        "chunk_id": _chunk_label(chunk),
        "reason": reason,
        "raw": raw,
    }
    path = out_dir / f"{_chunk_label(chunk)}_extraction_error.json"
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def extract_chunk(chunk: Chunk, document: Document) -> Path | None:
    """Extract claims from a chunk and write a staging JSON file.

    Scope guard: if the document scope is not 'varkaar', logs a warning and
    returns None without writing any file (ADR-006).

    On success: writes <chunk_id>_extraction.json to REVIEWED_DIR.
    On parse failure: writes <chunk_id>_extraction_error.json to REVIEWED_DIR.
    In both non-skipped cases, returns the Path of the file written.

    All claims in the staging file have reviewed=false. The reviewer sets
    this to true in R4 before DB load.

    Args:
        chunk:    ORM Chunk record to extract from.
        document: Parent Document record (used for scope check).

    Returns:
        Path of the staging file written, or None if the chunk was skipped.

    Raises:
        EnvironmentError: If REVIEWED_DIR is not set.
        RuntimeError:     Propagated from inference.complete() on empty response.
    """
    # Scope guard — ADR-006
    if document.scope != _VALID_SCOPE:
        log.warning(
            "Skipping %s: document scope '%s' is not '%s'.",
            _chunk_label(chunk),
            document.scope,
            _VALID_SCOPE,
        )
        return None

    out_dir = _get_reviewed_dir()
    prompt = _build_prompt(chunk)

    log.info("Extracting %s (document_id=%d).", _chunk_label(chunk), chunk.document_id)
    raw = complete(prompt, max_tokens=512, temperature=0.1)

    # Parse JSON response
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        log.warning(
            "%s: JSON parse failed — %s. Writing error file.",
            _chunk_label(chunk),
            exc,
        )
        return _write_error(out_dir, chunk, raw, f"JSON parse error: {exc}")

    # Structural validation: required top-level fields must be present
    missing = _REQUIRED_FIELDS - data.keys()
    if missing:
        reason = f"Missing required fields: {sorted(missing)}"
        log.warning("%s: %s. Writing error file.", _chunk_label(chunk), reason)
        return _write_error(out_dir, chunk, raw, reason)

    out_path = _write_staging(out_dir, chunk, data)
    log.info("%s: staging file written -> %s", _chunk_label(chunk), out_path)
    return out_path

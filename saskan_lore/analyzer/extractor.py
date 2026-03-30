# -*- coding: utf-8 -*-
"""
extractor.py

OpenAI-based lore extraction functions.

Two public functions:

    extract_claims(chunk_text, chunk_id, document_id) -> ExtractionRecord | None
        Primary extraction step. Takes a raw chunk of lore text and returns a
        structured ExtractionRecord. Uses the extract_claims.txt system prompt.

    structure_claims(raw_text, chunk_id, document_id) -> ExtractionRecord | None
        Recovery/structuring step. Takes malformed or free-text extraction output
        and normalizes it to ExtractionRecord. Uses structure_claims_metadata.txt.
        Use this when extract_claims() returns None due to malformed model output.

Both functions return None on API error or JSON parse failure; errors are logged.

Model: gpt-4o (JSON mode via response_format).
Requires: OPENAI_API_KEY environment variable.

See: R3 design doc, ADR-007 (no lore expansion), NFR-002 (replaceable model layer).
"""

from __future__ import annotations

import json
import logging
import os
from pathlib import Path

from openai import OpenAI

from ..data.schema.database_schema import ExtractionClaimRecord, ExtractionRecord

log = logging.getLogger(__name__)

_MODEL = "gpt-4o"
_PROMPTS_DIR = Path(__file__).parent


def _load_prompt(filename: str) -> str:
    """Read a prompt file from the prompts directory."""
    return (_PROMPTS_DIR / filename).read_text(encoding="utf-8")


def _get_client() -> OpenAI:
    """Return an OpenAI client. Raises EnvironmentError if key is missing."""
    key = os.getenv("OPENAI_API_KEY")
    if not key:
        raise EnvironmentError("OPENAI_API_KEY environment variable is not set")
    return OpenAI(api_key=key)


def _parse_extraction(data: dict) -> ExtractionRecord:
    """Build an ExtractionRecord from a parsed JSON response dict."""
    claims = [
        ExtractionClaimRecord(
            statement=c.get("statement", ""),
            source_span=c.get("source_span", ""),
            truth_status=c.get("truth_status", ""),
            confidence=c.get("confidence") or None,
        )
        for c in data.get("claims", [])
    ]
    return ExtractionRecord(
        chunk_id=data.get("chunk_id", ""),
        document_id=data.get("document_id", ""),
        title=data.get("title", ""),
        summary=data.get("summary", ""),
        era=data.get("era", ""),
        canon_level=data.get("canon_level", ""),
        truth_status=data.get("truth_status", ""),
        region=data.get("region", []),
        places=data.get("places", []),
        characters=data.get("characters", []),
        factions=data.get("factions", []),
        key_events=data.get("key_events", []),
        claims=claims,
    )


def extract_claims(
    chunk_text: str,
    chunk_id: str,
    document_id: str,
) -> ExtractionRecord | None:
    """
    Extract lore claims and entities from a raw chunk of text.

    Sends the chunk to OpenAI using the extract_claims.txt system prompt.
    The chunk_id and document_id are injected into the user message and
    also enforced on the returned record, so they always match the caller.

    Args:
        chunk_text:   verbatim chunk content (ChunkRecord.text)
        chunk_id:     string identifier, e.g. "chunk_0042"
        document_id:  string identifier, e.g. "doc_001"

    Returns:
        ExtractionRecord on success, None on API error or parse failure.
    """
    system_prompt = _load_prompt("extract_claims.txt")
    user_message = (
        f"chunk_id: {chunk_id}\n"
        f"document_id: {document_id}\n\n"
        f"Passage:\n{chunk_text}"
    )
    try:
        response = _get_client().chat.completions.create(
            model=_MODEL,
            response_format={"type": "json_object"},
            temperature=0.0,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_message},
            ],
        )
        raw = response.choices[0].message.content or ""
        data = json.loads(raw)
        data["chunk_id"] = chunk_id
        data["document_id"] = document_id
        return _parse_extraction(data)
    except json.JSONDecodeError as exc:
        log.error("extract_claims: JSON parse error for %s: %s", chunk_id, exc)
        return None
    except Exception as exc:
        log.error("extract_claims: API error for %s: %s", chunk_id, exc)
        return None


def structure_claims(
    raw_text: str,
    chunk_id: str = "",
    document_id: str = "",
) -> ExtractionRecord | None:
    """
    Convert raw or malformed extraction text into a structured ExtractionRecord.

    Use this as a recovery step when extract_claims() returns None. The raw_text
    argument should be whatever the model returned before the parse failure.

    Args:
        raw_text:    raw or malformed extraction output from a previous attempt
        chunk_id:    string identifier to inject into the result (optional)
        document_id: string identifier to inject into the result (optional)

    Returns:
        ExtractionRecord on success, None on API error or parse failure.
    """
    system_prompt = _load_prompt("structure_claims_metadata.txt")
    try:
        response = _get_client().chat.completions.create(
            model=_MODEL,
            response_format={"type": "json_object"},
            temperature=0.0,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": raw_text},
            ],
        )
        raw = response.choices[0].message.content or ""
        data = json.loads(raw)
        if chunk_id:
            data["chunk_id"] = chunk_id
        if document_id:
            data["document_id"] = document_id
        return _parse_extraction(data)
    except json.JSONDecodeError as exc:
        log.error("structure_claims: JSON parse error: %s", exc)
        return None
    except Exception as exc:
        log.error("structure_claims: API error: %s", exc)
        return None

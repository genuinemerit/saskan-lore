# -*- coding: utf-8 -*-
"""
staging.py

Utilities for reading and inspecting the var/reviewed/ staging area.

Staging files are written by extractor.py. This module provides the read side:
listing, loading, and validating staging files against extract_schema.json.

Public functions:

    list_staging(reviewed_dir) -> list[Path]
        Return paths of all successful staging files (_extraction.json).

    list_errors(reviewed_dir) -> list[Path]
        Return paths of all error staging files (_extraction_error.json).

    load_staging(path) -> dict
        Read and return a staging file as a dict. No validation.

    validate_staging(data) -> list[str]
        Validate a staging record against extract_schema.json.
        Returns a list of error messages; empty list means valid.

    load_for_document(reviewed_dir, document_id) -> list[dict]
        Return all valid staging records for a given document_id string
        (e.g. 'doc_001'). Skips error files and files that fail validation.

See: R3 design doc, NFR-003 (traceability), extract_schema.json.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path

import jsonschema

log = logging.getLogger(__name__)

_SCHEMA_PATH = Path(__file__).parent.parent / "data" / "schema" / "extract_schema.json"
_SCHEMA: dict | None = None


def _get_schema() -> dict:
    """Load extract_schema.json once and cache it."""
    global _SCHEMA
    if _SCHEMA is None:
        _SCHEMA = json.loads(_SCHEMA_PATH.read_text(encoding="utf-8"))
    return _SCHEMA


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def list_staging(reviewed_dir: Path) -> list[Path]:
    """Return paths of all successful extraction staging files in reviewed_dir.

    Successful files match the pattern *_extraction.json (not *_error.json).
    Returns an empty list if reviewed_dir does not exist.

    Args:
        reviewed_dir: Path to the staging directory (REVIEWED_DIR).

    Returns:
        Sorted list of Path objects for successful staging files.
    """
    if not reviewed_dir.exists():
        return []
    return sorted(
        p for p in reviewed_dir.glob("*_extraction.json") if "_extraction_error" not in p.name
    )


def list_errors(reviewed_dir: Path) -> list[Path]:
    """Return paths of all error staging files in reviewed_dir.

    Error files match the pattern *_extraction_error.json.
    Returns an empty list if reviewed_dir does not exist.

    Args:
        reviewed_dir: Path to the staging directory (REVIEWED_DIR).

    Returns:
        Sorted list of Path objects for error staging files.
    """
    if not reviewed_dir.exists():
        return []
    return sorted(reviewed_dir.glob("*_extraction_error.json"))


def load_staging(path: Path) -> dict:
    """Read a staging file and return its contents as a dict.

    No schema validation is performed. Use validate_staging() separately
    if you need to confirm the record is well-formed.

    Args:
        path: Path to a staging JSON file.

    Returns:
        Parsed JSON content as a dict.

    Raises:
        FileNotFoundError: If the file does not exist.
        json.JSONDecodeError: If the file is not valid JSON.
    """
    return json.loads(path.read_text(encoding="utf-8"))


def validate_staging(data: dict) -> list[str]:
    """Validate a staging record against extract_schema.json.

    Args:
        data: A dict loaded from a staging file.

    Returns:
        A list of validation error message strings. Empty list means valid.
    """
    validator = jsonschema.Draft202012Validator(_get_schema())
    return [
        error.message for error in sorted(validator.iter_errors(data), key=lambda e: list(e.path))
    ]


def load_for_document(reviewed_dir: Path, document_id: str) -> list[dict]:
    """Return all valid staging records for a given document_id.

    Reads all successful staging files in reviewed_dir, filters to those
    whose document_id field matches the given string, and validates each
    against the schema. Invalid records and error files are skipped with
    a logged warning.

    Args:
        reviewed_dir: Path to the staging directory (REVIEWED_DIR).
        document_id:  Document identifier string, e.g. 'doc_001'.

    Returns:
        List of valid staging record dicts for the document, in filename order.
    """
    results = []
    for path in list_staging(reviewed_dir):
        try:
            data = load_staging(path)
        except (json.JSONDecodeError, OSError) as exc:
            log.warning("staging: could not read %s — %s", path.name, exc)
            continue

        if data.get("document_id") != document_id:
            continue

        errors = validate_staging(data)
        if errors:
            log.warning(
                "staging: %s failed validation (%d error(s)); skipping.",
                path.name,
                len(errors),
            )
            continue

        results.append(data)

    return results

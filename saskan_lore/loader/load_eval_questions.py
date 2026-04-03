# -*- coding: utf-8 -*-
"""
load_eval_questions.py

Load evaluation questions from varkaar_questions.json into the database.

Public functions:

    load_eval_questions(session, path=None) -> dict
        Validate varkaar_questions.json against testing_schema.json, then
        insert EvalQuestion records. Idempotent by question_id. Returns a
        summary dict with 'loaded' and 'skipped' counts.

    print_summary(summary)
        Print a formatted load summary to stdout.

Default source: saskan_lore/data/eval/varkaar_questions.json
Schema:         saskan_lore/data/schema/testing_schema.json

See: FR-008, R6 design doc.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path

import jsonschema
import typer
from sqlalchemy.orm import Session

from saskan_lore.data.models import EvalQuestion

log = logging.getLogger(__name__)

_QUESTIONS_PATH = Path(__file__).parent.parent / "data" / "eval" / "varkaar_questions.json"
_SCHEMA_PATH = Path(__file__).parent.parent / "data" / "schema" / "testing_schema.json"
_SCHEMA: dict | None = None


def _get_schema() -> dict:
    """Load testing_schema.json once and cache it."""
    global _SCHEMA
    if _SCHEMA is None:
        _SCHEMA = json.loads(_SCHEMA_PATH.read_text(encoding="utf-8"))
    return _SCHEMA


def _validate(data: list) -> list[str]:
    """Validate a questions list against testing_schema.json.

    Returns a list of error messages; empty list means valid.
    """
    errors = []
    validator = jsonschema.Draft202012Validator(_get_schema())
    for err in validator.iter_errors(data):
        errors.append(err.message)
    return errors


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def load_eval_questions(
    session: Session,
    path: Path | None = None,
) -> dict:
    """Load evaluation questions from JSON into the database.

    Validates the file against testing_schema.json before inserting.
    Idempotent: questions already present (matched by question_id) are skipped.

    Args:
        session: Active SQLAlchemy session.
        path:    Path to the questions JSON file. Defaults to
                 saskan_lore/data/eval/varkaar_questions.json.

    Returns:
        Dict with keys 'loaded' and 'skipped'.

    Raises:
        FileNotFoundError:   If the questions file does not exist.
        json.JSONDecodeError: If the file is not valid JSON.
        ValueError:          If the file fails schema validation.
    """
    source = path or _QUESTIONS_PATH
    data = json.loads(source.read_text(encoding="utf-8"))

    errors = _validate(data)
    if errors:
        raise ValueError(
            "varkaar_questions.json failed schema validation:\n"
            + "\n".join(f"  - {e}" for e in errors)
        )

    loaded = 0
    skipped = 0

    for entry in data:
        existing = session.query(EvalQuestion).filter_by(question_id=entry["question_id"]).first()
        if existing is not None:
            log.info(
                "load_eval_questions: %s already present — skipped.",
                entry["question_id"],
            )
            skipped += 1
            continue

        session.add(
            EvalQuestion(
                question_id=entry["question_id"],
                question_text=entry["question_text"],
                expected_answer=entry["expected_answer"],
                scope=entry["scope"],
            )
        )
        loaded += 1

    session.commit()
    log.info(
        "load_eval_questions: %d loaded, %d skipped.",
        loaded,
        skipped,
    )
    return {"loaded": loaded, "skipped": skipped}


def print_summary(summary: dict) -> None:
    """Print a formatted load summary to stdout."""
    typer.echo("")
    typer.echo("── Eval questions load summary " + "─" * 26)
    typer.echo(f"  Loaded  : {summary['loaded']}")
    typer.echo(f"  Skipped : {summary['skipped']} (already present)")
    typer.echo("")

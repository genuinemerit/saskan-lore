# -*- coding: utf-8 -*-
"""
answering.py

Grounded question-answering for the saskan-lore RAG pipeline.

Public function:

    answer(question, session) -> AnswerResult
        Retrieve relevant approved claims for the question, format them as
        context, call the local GGUF model via inference.complete(), and
        return the answer together with the supporting evidence list.

        Returns AnswerResult(answerable=False) without calling the model if
        retrieve() returns no hits.

        If the model signals that it cannot answer from the supplied context,
        that response is preserved as-is in AnswerResult.answer — it is not
        treated as an error.

The model is never called directly here. All inference goes through
inference.complete() in accordance with NFR-002 (replaceable model layer).

See: R5 design doc, FR-006, FR-007, ADR-001, ADR-007, NFR-002.
"""

from __future__ import annotations

import logging
from pathlib import Path

from sqlalchemy.orm import Session

from saskan_lore.analyzer.inference import complete
from saskan_lore.analyzer.retrieval import format_context, retrieve
from saskan_lore.data.schema.data_schema import AnswerResult

log = logging.getLogger(__name__)

_PROMPT_PATH = Path(__file__).parent / "answer.txt"


def _load_prompt() -> str:
    """Load the answer prompt template from answer.txt."""
    return _PROMPT_PATH.read_text(encoding="utf-8")


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def answer(question: str, session: Session, top_n: int = 3) -> AnswerResult:
    """Retrieve relevant claims and generate a grounded answer.

    Steps:
        1. Retrieve top-N approved claims matching the question (FTS5).
        2. If no hits: return AnswerResult(answerable=False) — no model call.
        3. Format hits as a numbered context block.
        4. Build the answer prompt and call inference.complete().
        5. Return AnswerResult with the model response and evidence claim IDs.

    Args:
        question: Free-text question from the user.
        session:  Active SQLAlchemy session.
        top_n:    Maximum number of claims to retrieve as context (default 3).

    Returns:
        AnswerResult with answerable, answer text, and evidence claim ID list.
    """
    hits = retrieve(question, session, top_n=top_n)

    if not hits:
        log.debug("answer: no retrieval hits for %r — skipping model call.", question)
        return AnswerResult(answerable=False, answer=None, evidence=[])

    context = format_context(hits)
    prompt = _load_prompt().format(context=context, question=question)

    log.debug("answer: calling model with %d hit(s) as context.", len(hits))
    raw = complete(prompt, max_tokens=512, temperature=0.1)

    evidence = [h.claim_id for h in hits]
    log.info("answer: returned %d-char answer backed by %d claim(s).", len(raw), len(evidence))

    return AnswerResult(answerable=True, answer=raw, evidence=evidence)

# -*- coding: utf-8 -*-
"""
retrieval.py

FTS5-based claim retrieval for the saskan-lore RAG pipeline.

Public functions:

    tokenize(query) -> list[str]
        Lowercase and split a query string into alphanumeric tokens.
        Returns an empty list if the query contains no usable terms.

    retrieve(query, session, top_n=3) -> list[RetrievalHit]
        Search approved claims using FTS5 full-text search. Returns the
        top_n results ranked by BM25 relevance. Returns an empty list if
        the query yields no tokens or no matching claims.

    format_context(hits) -> str
        Format a list of RetrievalHits as a numbered context block suitable
        for insertion into the answer prompt template.

Only claims with status='approved' are eligible for retrieval.
The claims_fts virtual table is queried via raw SQL (it is not an ORM model).

See: R5 design doc, FR-006, FR-007, NFR-001, NFR-003, ADR-001.
"""

from __future__ import annotations

import logging
import re

from sqlalchemy import text
from sqlalchemy.orm import Session

from saskan_lore.data.schema.data_schema import RetrievalHit

log = logging.getLogger(__name__)

_TOKEN_RE = re.compile(r"[^\w]+")  # split on anything that is not a word character

# Common English function words that add no retrieval signal when used as FTS5
# AND terms.  Filtering these prevents queries like "How many X are there?" from
# requiring every claim to contain "how", "many", "are", "there".
_STOPWORDS = frozenset(
    {
        "a",
        "an",
        "and",
        "are",
        "as",
        "at",
        "be",
        "been",
        "but",
        "by",
        "did",
        "do",
        "does",
        "for",
        "from",
        "had",
        "has",
        "have",
        "how",
        "i",
        "in",
        "is",
        "it",
        "its",
        "many",
        "no",
        "not",
        "of",
        "on",
        "or",
        "s",
        "so",
        "than",
        "that",
        "the",
        "their",
        "there",
        "they",
        "this",
        "to",
        "was",
        "were",
        "what",
        "when",
        "where",
        "which",
        "who",
        "why",
        "will",
        "with",
    }
)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def tokenize(query: str) -> list[str]:
    """Return lowercase alphanumeric tokens from a query string.

    Splits on whitespace and punctuation. Returns an empty list if no
    tokens remain after splitting (e.g. a query of only punctuation).

    Args:
        query: Free-text query string from the user.

    Returns:
        List of non-empty lowercase token strings.
    """
    return [t for t in _TOKEN_RE.split(query.lower()) if t and t not in _STOPWORDS]


def retrieve(query: str, session: Session, top_n: int = 3) -> list[RetrievalHit]:
    """Search approved claims using FTS5 and return the top matches.

    Tokenizes the query, builds a FTS5 MATCH expression (implicit AND across
    all tokens), and queries the claims_fts virtual table joined to claims,
    chunks, and documents. Only claims with status='approved' are returned.

    Results are ordered by BM25 rank (lower/more-negative = stronger match).

    Args:
        query:   Free-text query string from the user.
        session: Active SQLAlchemy session.
        top_n:   Maximum number of results to return (default 3).

    Returns:
        List of RetrievalHit objects, ordered by relevance. Empty list if
        the query yields no tokens or no approved claims match.
    """
    tokens = tokenize(query)
    if not tokens:
        log.debug("retrieve: query yielded no tokens — returning empty.")
        return []

    match_expr = " ".join(tokens)

    sql = text("""
        SELECT
            c.id            AS claim_id,
            c.claim_text,
            c.source_span,
            c.truth_status,
            d.title         AS document_title,
            ch.sequence     AS chunk_sequence,
            claims_fts.rank AS bm25_rank
        FROM claims_fts
        JOIN claims    c  ON claims_fts.rowid = c.id
        JOIN chunks    ch ON c.chunk_id       = ch.id
        JOIN documents d  ON c.document_id    = d.id
        WHERE claims_fts MATCH :match_expr
          AND c.status    = 'approved'
          AND c.is_active = 1
        ORDER BY claims_fts.rank
        LIMIT :top_n
        """)

    try:
        rows = session.execute(sql, {"match_expr": match_expr, "top_n": top_n}).fetchall()
    except Exception as exc:
        log.warning("retrieve: FTS5 query failed — %s. Returning empty.", exc)
        return []

    hits = [
        RetrievalHit(
            claim_id=row.claim_id,
            claim_text=row.claim_text,
            source_span=row.source_span,
            truth_status=row.truth_status,
            document_title=row.document_title,
            chunk_sequence=row.chunk_sequence,
            bm25_rank=row.bm25_rank,
        )
        for row in rows
    ]

    log.debug("retrieve: query=%r tokens=%r hits=%d", query, tokens, len(hits))
    return hits


def format_context(hits: list[RetrievalHit]) -> str:
    """Format retrieval hits as a numbered context block for the answer prompt.

    Each entry includes the claim text, its source span, and a reference
    line showing truth status, document title, and chunk sequence number.
    Entries are separated by blank lines.

    Args:
        hits: List of RetrievalHit objects from retrieve().

    Returns:
        Multi-line string ready for insertion at {context} in answer.txt.
        Returns an empty string if hits is empty.
    """
    if not hits:
        return ""

    parts = []
    for i, hit in enumerate(hits, start=1):
        parts.append(
            f'[{i}] ({hit.truth_status}) — "{hit.document_title}", chunk {hit.chunk_sequence}\n'
            f'    Source: "{hit.source_span}"\n'
            f'    Claim:  "{hit.claim_text}"'
        )

    return "\n\n".join(parts)

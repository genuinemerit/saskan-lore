# saskan_lore/loader/ingest.py
"""
Top-level CLI entry point for saskan-lore.

Commands:
    ingest  -- extract text from a PDF, register it, and chunk it (R2)
    extract -- run lore extraction on one chunk or all chunks for a document (R3)

CLI entry point (pyproject.toml):
    [tool.poetry.scripts]
    saskan-lore = "saskan_lore.loader.ingest:app"

Note: the extract command imports inference.py inside the command function,
not at module level. This defers GGUF model loading until extract is actually
called, so `saskan-lore ingest` has no model startup overhead.
"""

from __future__ import annotations

import re
import sys

import typer
from pdfminer.high_level import extract_text

from saskan_lore.data.models import Chunk, Document
from saskan_lore.infra.db.db import get_session
from saskan_lore.infra.log.logger import configure, get_logger
from saskan_lore.loader.load_chunks import load_chunks
from saskan_lore.loader.register_lore_text import register_document

app = typer.Typer(
    name="saskan-lore",
    help="Saskan Lore ingestion and management tools.",
    no_args_is_help=True,
    add_completion=False,
)

log = get_logger(__name__)


def _extract_text(path: str) -> str:
    """Extract plain text from a PDF and apply approved normalization.

    Normalization: collapse runs of whitespace (including newlines from page
    breaks and headers) to a single space, then strip leading/trailing space.
    Text content is not altered beyond this.
    """
    raw = extract_text(path)
    return re.sub(r"\s+", " ", raw).strip()


@app.command()
def ingest(
    path: str = typer.Option(
        ...,
        "--path",
        help=(
            "Path to the source PDF file. "
            "Relative paths are resolved from the working directory. "
            "Example: data/lore_texts/SaskanCanon-VarkaarCovenant.pdf"
        ),
    ),
    title: str = typer.Option(
        ...,
        "--title",
        help=(
            "Human-readable title for the document. "
            "Used as the display name in the database and reports. "
            'Example: "Saskan Canon: Varkaar Covenant"'
        ),
    ),
    scope: str = typer.Option(
        "varkaar",
        "--scope",
        help=(
            "Lore scope for this document. "
            "Only 'varkaar' is accepted in the pre-pilot release. "
            "Documents outside the allowed scope are rejected. "
            "[default: varkaar]"
        ),
    ),
) -> None:
    """Ingest a lore source text: extract, register, and chunk.

    Reads a PDF from PATH, registers the document in the database, and
    splits its text into chunks ready for downstream extraction (R3).

    Re-running on a previously ingested file is safe: the document record
    and its chunks are returned as-is if already complete.
    """
    configure()

    typer.echo(f"Ingesting: {title}")
    typer.echo(f"  path:  {path}")
    typer.echo(f"  scope: {scope}")

    try:
        text = _extract_text(path)
    except FileNotFoundError:
        typer.echo(f"Error: file not found: {path}", err=True)
        log.error("PDF not found", extra={"path": path})
        raise typer.Exit(code=1)
    except Exception as exc:
        typer.echo(f"Error: could not extract text from PDF: {exc}", err=True)
        log.error("PDF extraction failed", extra={"path": path, "error": str(exc)})
        raise typer.Exit(code=1)

    if not text:
        typer.echo("Error: extracted text is empty. Check the PDF file.", err=True)
        log.error("Empty text extracted", extra={"path": path})
        raise typer.Exit(code=1)

    try:
        with get_session() as session:
            doc = register_document(
                session=session,
                title=title,
                source_path=path,
                scope=scope,
            )
            n = load_chunks(session=session, document=doc, text=text)
    except ValueError as exc:
        typer.echo(f"Error: {exc}", err=True)
        log.error("Ingestion rejected", extra={"reason": str(exc)})
        raise typer.Exit(code=1)
    except Exception as exc:
        typer.echo(f"Error: ingestion failed: {exc}", err=True)
        log.error("Ingestion failed", extra={"error": str(exc)})
        raise typer.Exit(code=1)

    if n == 0:
        typer.echo(f"Already ingested: {title!r} (no changes made)")
        log.info("Already ingested", extra={"title": title, "path": path})
    else:
        typer.echo(f"Ingested {title!r}: {n} chunks stored (document id={doc.id})")
        log.info(
            "Ingestion complete",
            extra={"title": title, "path": path, "doc_id": doc.id, "chunks": n},
        )


@app.command()
def extract(
    chunk_id: int | None = typer.Option(
        None,
        "--chunk-id",
        help=("ID of a single chunk to extract from. " "Mutually exclusive with --document-id."),
    ),
    document_id: int | None = typer.Option(
        None,
        "--document-id",
        help=(
            "ID of a document. Extracts all chunks for that document. "
            "Mutually exclusive with --chunk-id."
        ),
    ),
) -> None:
    """Extract lore claims from one chunk or all chunks for a document.

    Exactly one of --chunk-id or --document-id must be provided.

    Output is written to REVIEWED_DIR (set in env.local). Each chunk
    produces either a staging file (<chunk_id>_extraction.json) or an
    error file (<chunk_id>_extraction_error.json) if the model output
    could not be parsed. No database writes are made.

    Chunks whose parent document scope is not 'varkaar' are skipped.
    """
    configure()

    # Deferred import — loads GGUF model; must not happen at module level.
    from saskan_lore.analyzer.extractor import extract_chunk  # noqa: PLC0415

    if (chunk_id is None) == (document_id is None):
        typer.echo("Error: provide exactly one of --chunk-id or --document-id.", err=True)
        raise typer.Exit(code=1)

    try:
        with get_session() as session:
            if chunk_id is not None:
                chunks_to_process = _get_chunks_for_id(session, chunk_id)
            else:
                chunks_to_process = _get_chunks_for_document(session, document_id)
    except Exception as exc:
        typer.echo(f"Error: database query failed: {exc}", err=True)
        log.error("Extract DB query failed", extra={"error": str(exc)})
        raise typer.Exit(code=1)

    if not chunks_to_process:
        typer.echo("No chunks found for the given ID.")
        raise typer.Exit(code=0)

    typer.echo(f"Extracting {len(chunks_to_process)} chunk(s)...")

    ok_count = 0
    err_count = 0
    skip_count = 0

    for chunk, document in chunks_to_process:
        try:
            out_path = extract_chunk(chunk, document)
        except Exception as exc:
            typer.echo(f"  {_label(chunk)}: failed — {exc}", err=True)
            log.error(
                "extract_chunk raised",
                extra={"chunk_id": chunk.id, "error": str(exc)},
            )
            err_count += 1
            continue

        if out_path is None:
            typer.echo(f"  {_label(chunk)}: skipped (out of scope)")
            skip_count += 1
        elif "_error" in out_path.name:
            typer.echo(f"  {_label(chunk)}: parse error -> {out_path.name}")
            err_count += 1
        else:
            typer.echo(f"  {_label(chunk)}: ok -> {out_path.name}")
            ok_count += 1

    typer.echo(f"Done: {ok_count} extracted, {err_count} errors, {skip_count} skipped.")
    log.info(
        "Extraction complete",
        extra={"ok": ok_count, "errors": err_count, "skipped": skip_count},
    )


# ---------------------------------------------------------------------------
# Internal helpers for extract command
# ---------------------------------------------------------------------------


def _label(chunk: Chunk) -> str:
    return f"chunk_{chunk.id:04d}"


def _get_chunks_for_id(session, chunk_id: int) -> list[tuple[Chunk, Document]]:
    """Return [(chunk, document)] for a single chunk ID."""
    chunk = session.get(Chunk, chunk_id)
    if chunk is None:
        typer.echo(f"Error: chunk id={chunk_id} not found.", err=True)
        raise typer.Exit(code=1)
    document = session.get(Document, chunk.document_id)
    if document is None:
        typer.echo(f"Error: document id={chunk.document_id} not found.", err=True)
        raise typer.Exit(code=1)
    return [(chunk, document)]


def _get_chunks_for_document(session, document_id: int) -> list[tuple[Chunk, Document]]:
    """Return [(chunk, document), ...] for all active chunks of a document."""
    document = session.get(Document, document_id)
    if document is None:
        typer.echo(f"Error: document id={document_id} not found.", err=True)
        raise typer.Exit(code=1)
    chunks = (
        session.query(Chunk)
        .filter_by(document_id=document_id, is_active=True)
        .order_by(Chunk.sequence)
        .all()
    )
    return [(chunk, document) for chunk in chunks]


if __name__ == "__main__":
    sys.exit(app())

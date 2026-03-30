# saskan_lore/loader/ingest.py
"""
Top-level ingestion pipeline for lore source texts.

Chains PDF text extraction, document registration, and chunk persistence
into a single operation. Exposed as the `saskan-lore ingest` CLI command.

CLI entry point (pyproject.toml):
    [tool.poetry.scripts]
    saskan-lore = "saskan_lore.loader.ingest:app"
"""

from __future__ import annotations

import re
import sys

import typer
from pdfminer.high_level import extract_text

from saskan_lore.infra.db.db import get_session
from saskan_lore.infra.log.logger import configure, get_logger
from saskan_lore.loader.load_chunks import load_chunks
from saskan_lore.loader.register_lore_text import register_document

app = typer.Typer(
    name="saskan-lore",
    help="Saskan Lore ingestion and management tools.",
    no_args_is_help=True,
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


if __name__ == "__main__":
    sys.exit(app())

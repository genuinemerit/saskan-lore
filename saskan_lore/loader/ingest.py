# saskan_lore/loader/ingest.py
"""
Top-level CLI entry point for saskan-lore.

Commands:
    ingest              -- extract text from a PDF, register it, and chunk it (R2)
    extract             -- run lore extraction on one chunk or all chunks for a document (R3)
    review              -- interactively review claims in a staging file (R4)
    load                -- load a reviewed staging file into the database (R4)
    ask                 -- answer a natural-language question from retrieved lore claims (R5)
    load-eval-questions -- load evaluation questions from varkaar_questions.json (R6)
    evaluate            -- run all eval questions through the pipeline; write results (R6)
    grade               -- set pass/fail on one eval result (R6)
    eval-summary        -- print pass rate and failure breakdown (R6)
    export-eval         -- export all eval results to JSON (R6)

CLI entry point (pyproject.toml):
    [tool.poetry.scripts]
    saskan-lore = "saskan_lore.loader.ingest:app"

Note: the extract command imports inference.py inside the command function,
not at module level. This defers GGUF model loading until extract is actually
called, so `saskan-lore ingest` has no model startup overhead.
"""

from __future__ import annotations

import os
import re
import sys

import typer
from pdfminer.high_level import extract_text

from saskan_lore.data.models import Chunk, Document
from saskan_lore.infra.db.db import get_session
from saskan_lore.infra.log.logger import configure, get_logger
from saskan_lore.loader.load_chunks import load_chunks
from saskan_lore.loader.register_lore_text import register_document
from saskan_lore.loader.load_eval_questions import (
    load_eval_questions,
    print_summary as print_eval_load_summary,
)
from saskan_lore.loader.load_reviewed import load_file, print_load_summary
from saskan_lore.loader.review_staging import print_summary, review_file

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
            "Only 'varkaar' is accepted in the pilot. "
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
            doc_id = doc.id
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
        typer.echo(f"Ingested {title!r}: {n} chunks stored (document id={doc_id})")
        log.info(
            "Ingestion complete",
            extra={"title": title, "path": path, "doc_id": doc_id, "chunks": n},
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

    ok_count = 0
    err_count = 0
    skip_count = 0

    try:
        with get_session() as session:
            if chunk_id is not None:
                chunks_to_process = _get_chunks_for_id(session, chunk_id)
            else:
                chunks_to_process = _get_chunks_for_document(session, document_id)

            if not chunks_to_process:
                typer.echo("No chunks found for the given ID.")
                raise typer.Exit(code=0)

            typer.echo(f"Extracting {len(chunks_to_process)} chunk(s)...")

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

    except typer.Exit:
        raise
    except Exception as exc:
        typer.echo(f"Error: extraction failed: {exc}", err=True)
        log.error("Extraction failed", extra={"error": str(exc)})
        raise typer.Exit(code=1)

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


@app.command()
def review(
    staging_file: str = typer.Argument(
        ...,
        help=(
            "Path to a staging JSON file to review. "
            "Example: var/reviewed/chunk_0001_extraction.json"
        ),
    ),
) -> None:
    """Interactively review claims in a staging file.

    Presents each pending claim with its claim_text, source_span, and
    truth_status, then prompts for Approve / Correct / Reject / Quit.

    Approved claims are marked review_status='approved'. Rejected claims are
    marked review_status='rejected' with an optional reason. Claims marked for
    correction are left unchanged for direct JSON editing and a subsequent re-run.

    Partial state is written back if the session ends early (Q or Ctrl-C).
    Already-decided claims are skipped automatically.
    """
    configure()

    from pathlib import Path  # noqa: PLC0415

    path = Path(staging_file)
    if not path.exists():
        typer.echo(f"Error: file not found: {staging_file}", err=True)
        log.error("Staging file not found", extra={"path": staging_file})
        raise typer.Exit(code=1)

    if not path.suffix == ".json":
        typer.echo("Error: staging file must be a .json file.", err=True)
        raise typer.Exit(code=1)

    try:
        counts = review_file(path)
    except Exception as exc:
        typer.echo(f"Error: review failed: {exc}", err=True)
        log.error("Review failed", extra={"path": staging_file, "error": str(exc)})
        raise typer.Exit(code=1)

    print_summary(counts)
    log.info("Review complete", extra={"path": staging_file, **counts})


@app.command()
def load(
    staging_file: str = typer.Argument(
        ...,
        help=(
            "Path to a reviewed staging JSON file to load. "
            "Example: var/reviewed/chunk_0001_extraction.json"
        ),
    ),
) -> None:
    """Load a reviewed staging file into the database.

    Runs the full load sequence in dependency order: entities, claims,
    claim-entity links, and relationships. Only claims marked
    review_status='approved' are inserted as approved. Claims marked
    review_status='rejected' are inserted with that status to preserve the
    audit trail. Pending claims are skipped.

    The load is idempotent: re-running on the same file produces no
    duplicate records.
    """
    configure()

    from pathlib import Path  # noqa: PLC0415

    path = Path(staging_file)
    if not path.exists():
        typer.echo(f"Error: file not found: {staging_file}", err=True)
        log.error("Staging file not found", extra={"path": staging_file})
        raise typer.Exit(code=1)

    if not path.suffix == ".json":
        typer.echo("Error: staging file must be a .json file.", err=True)
        raise typer.Exit(code=1)

    typer.echo(f"Loading: {path.name}")

    try:
        with get_session() as session:
            summary = load_file(session, path)
    except ValueError as exc:
        typer.echo(f"Error: {exc}", err=True)
        log.error("Load rejected", extra={"path": staging_file, "reason": str(exc)})
        raise typer.Exit(code=1)
    except Exception as exc:
        typer.echo(f"Error: load failed: {exc}", err=True)
        log.error("Load failed", extra={"path": staging_file, "error": str(exc)})
        raise typer.Exit(code=1)

    print_load_summary(summary)
    log.info("Load complete", extra={"path": staging_file, **summary})


@app.command()
def ask(
    question: str = typer.Argument(
        ...,
        help='Natural-language question to answer from the lore. Example: "What is the Covenant?"',
    ),
    top_n: int = typer.Option(
        3,
        "--top-n",
        help="Maximum number of claims to retrieve as context.",
    ),
) -> None:
    """Answer a question grounded in reviewed lore claims.

    Searches approved claims using full-text search (FTS5), formats the top
    results as context, and calls the local GGUF model to produce an answer.
    The model is instructed to answer only from the supplied evidence.

    If no relevant claims are found the model is not called and a message is
    printed instead. Every answer is accompanied by a numbered evidence list
    showing the supporting claim IDs, truth status, chunk, and source span.
    """
    configure()

    # Deferred import — loads GGUF model; must not happen at module level.
    from saskan_lore.analyzer.answering import answer as _answer  # noqa: PLC0415
    from saskan_lore.data.models import Claim, Document  # noqa: PLC0415

    try:
        with get_session() as session:
            result = _answer(question, session, top_n=top_n)

            if not result.answerable:
                typer.echo("No relevant claims found for that question.")
                raise typer.Exit(code=0)

            typer.echo(f"\nAnswer: {result.answer}")
            typer.echo("\nEvidence:")

            for i, claim_id in enumerate(result.evidence, start=1):
                claim = session.get(Claim, claim_id)
                if claim is None:
                    continue
                doc = session.get(Document, claim.document_id)
                chunk_label = f"chunk_{claim.chunk_id:04d}"
                doc_title = doc.title if doc else "unknown"
                typer.echo(
                    f"  [{i}] claim_{claim_id:04d} ({claim.truth_status})"
                    f' — {chunk_label} — "{doc_title}"'
                )
                typer.echo(f'      "{claim.source_span}"')

            typer.echo("")

    except typer.Exit:
        raise
    except Exception as exc:
        typer.echo(f"Error: {exc}", err=True)
        log.error("Ask failed", extra={"question": question, "error": str(exc)})
        raise typer.Exit(code=1)


@app.command("load-eval-questions")
def load_eval_questions_cmd(
    path: str = typer.Option(
        None,
        "--path",
        help=(
            "Path to an alternative questions JSON file. "
            "Defaults to saskan_lore/data/eval/varkaar_questions.json."
        ),
    ),
) -> None:
    """Load evaluation questions into the database from varkaar_questions.json.

    Validates the file against testing_schema.json before inserting. Safe to
    run more than once — questions already present are skipped (idempotent by
    question_id).
    """
    configure()
    from pathlib import Path  # noqa: PLC0415

    try:
        src = Path(path) if path else None
        with get_session() as session:
            summary = load_eval_questions(session, src)
        print_eval_load_summary(summary)
    except Exception as exc:
        typer.echo(f"Error: {exc}", err=True)
        log.error("load-eval-questions failed", extra={"error": str(exc)})
        raise typer.Exit(code=1)


@app.command()
def evaluate() -> None:
    """Run all Varkaar evaluation questions through the retrieval and answering pipeline.

    Creates one EvalResult record per question. Answers are written to the
    database with pass_fail=None — use `saskan-lore grade` to set pass/fail
    after reviewing each answer.

    Loads the local GGUF model on startup.
    """
    configure()

    # Deferred import — loads GGUF model; must not happen at module level.
    from saskan_lore.analyzer.evaluate import (  # noqa: PLC0415
        run_evaluation,
    )

    try:
        with get_session() as session:
            records = run_evaluation(session)
            result_refs = [(r.id, r.question_id) for r in records]

        if not result_refs:
            typer.echo("No active Varkaar evaluation questions found.")
            raise typer.Exit(code=0)

        typer.echo(f"\nEvaluation complete: {len(result_refs)} result(s) written.")
        typer.echo("Result IDs:")
        for result_id, question_id in result_refs:
            typer.echo(f"  result_id={result_id}  question_id={question_id}")
        typer.echo("\nReview answers then run `saskan-lore grade <result-id> pass|fail`.")
        typer.echo("")

    except typer.Exit:
        raise
    except Exception as exc:
        typer.echo(f"Error: {exc}", err=True)
        log.error("evaluate failed", extra={"error": str(exc)})
        raise typer.Exit(code=1)


@app.command()
def grade(
    result_id: int = typer.Argument(
        ...,
        help="Primary key of the EvalResult to grade (from `saskan-lore evaluate` output).",
    ),
    verdict: str = typer.Argument(
        ...,
        help="Grade: 'pass' or 'fail'.",
        metavar="pass|fail",
    ),
    failure_type: str = typer.Option(
        None,
        "--type",
        help=(
            "Failure classification (required when verdict=fail). "
            "One of: wrong_fact, hallucination, incomplete, style."
        ),
    ),
    notes: str = typer.Option(
        None,
        "--notes",
        help="Optional free-text note for failure analysis.",
    ),
) -> None:
    """Set pass/fail on one evaluation result.

    After running `saskan-lore evaluate`, inspect each model answer and
    grade it against the expected answer in varkaar_questions.json. Run
    `saskan-lore eval-summary` when all results are graded.
    """
    configure()

    try:
        from saskan_lore.analyzer.evaluate import grade_result  # noqa: PLC0415

        with get_session() as session:
            record = grade_result(
                session,
                result_id=result_id,
                pass_fail=verdict,
                failure_type=failure_type or None,
                notes=notes or None,
            )
            result_pass_fail = record.pass_fail
            result_failure_type = record.failure_type

        typer.echo(
            f"Graded result_id={result_id}: {result_pass_fail}"
            + (f" ({result_failure_type})" if result_failure_type else "")
        )
    except Exception as exc:
        typer.echo(f"Error: {exc}", err=True)
        log.error("grade failed", extra={"result_id": result_id, "error": str(exc)})
        raise typer.Exit(code=1)


@app.command("eval-summary")
def eval_summary_cmd() -> None:
    """Print pass rate and failure type breakdown for graded Varkaar eval results."""
    configure()
    from saskan_lore.analyzer.evaluate import eval_summary, print_eval_summary  # noqa: PLC0415

    try:
        with get_session() as session:
            summary = eval_summary(session)
        print_eval_summary(summary)
    except Exception as exc:
        typer.echo(f"Error: {exc}", err=True)
        log.error("eval-summary failed", extra={"error": str(exc)})
        raise typer.Exit(code=1)


@app.command("export-eval")
def export_eval_cmd(
    output_path: str = typer.Option(
        None,
        "--output",
        help=(
            "Destination path for the JSON export. "
            "Defaults to $SASKAN_VAR_DIR/eval_export_<timestamp>.json."
        ),
    ),
) -> None:
    """Export all evaluation results to JSON.

    Joins EvalResult records to their EvalQuestion for a self-contained
    export. Run this before wiping the database at graduation.
    """
    configure()
    from datetime import datetime  # noqa: PLC0415
    from pathlib import Path  # noqa: PLC0415

    from saskan_lore.analyzer.evaluate import export_results  # noqa: PLC0415

    try:
        if output_path:
            dest = Path(output_path)
        else:
            ts = datetime.now().strftime("%Y%m%d_%H%M%S")
            var_dir = os.environ.get("SASKAN_VAR_DIR", "var")
            dest = Path(var_dir) / f"eval_export_{ts}.json"

        with get_session() as session:
            written = export_results(session, dest)

        typer.echo(f"Exported eval results to: {written}")
    except Exception as exc:
        typer.echo(f"Error: {exc}", err=True)
        log.error("export-eval failed", extra={"error": str(exc)})
        raise typer.Exit(code=1)


if __name__ == "__main__":
    sys.exit(app())

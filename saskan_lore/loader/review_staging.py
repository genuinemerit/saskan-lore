# -*- coding: utf-8 -*-
"""
review_staging.py

Interactive per-claim review helper for saskan-lore.

Public functions:

    review_file(path) -> dict
        Present each pending claim in a staging JSON file for approve / correct / reject.
        Writes the updated JSON back on completion or interrupt (partial state is preserved).
        Returns a summary dict: {approved, corrected, rejected, skipped}.

    print_summary(counts)
        Print a formatted review session summary.

Review actions per claim:
    A — Approve:  sets reviewed=true.
    C — Correct:  leaves the claim unchanged; reviewer edits the JSON and re-runs.
    R — Reject:   sets status="rejected"; prompts for an optional reject_reason.
    Q — Quit:     ends the session early; partial state is written back.

Claims already marked reviewed=true or status="rejected" are skipped automatically.

reject_reason is a staging-only field. It is not written to the database; the loader
logs it during a load run for the reviewer's benefit.

See: R4 design doc, NFR-004, ADR-007.
"""

from __future__ import annotations

import json
from pathlib import Path

import typer

# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _is_decided(claim: dict) -> bool:
    """Return True if a claim has already been approved or rejected."""
    return claim.get("reviewed") is True or claim.get("status") == "rejected"


def _display_claim(index: int, total: int, claim: dict) -> None:
    """Print a claim for review."""
    typer.echo("")
    typer.echo(f"── Claim {index}/{total} " + "─" * 38)
    typer.echo(f"  truth_status : {claim.get('truth_status', '?')}")
    typer.echo(f"  confidence   : {claim.get('confidence', '—')}")
    typer.echo("")
    typer.echo(f"  claim_text   : {claim.get('claim_text', '')}")
    typer.echo("")
    typer.echo(f"  source_span  : {claim.get('source_span', '')}")
    typer.echo("")


def _prompt_action() -> str:
    """Prompt the reviewer for an action. Loops until a valid key is entered."""
    label = typer.style("[A]pprove  [C]orrect  [R]eject  [Q]uit", fg=typer.colors.CYAN)
    while True:
        raw = typer.prompt(label, default="", show_default=False).strip().upper()
        if raw in ("A", "C", "R", "Q"):
            return raw
        typer.echo("  Enter A, C, R, or Q.", err=True)


def _prompt_reason() -> str:
    """Prompt for an optional rejection reason. Returns empty string if skipped."""
    return typer.prompt("  Reason (optional, press Enter to skip)", default="").strip()


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def review_file(path: Path) -> dict:
    """Present pending claims in a staging file for approve / correct / reject.

    Iterates over claims that have not yet been decided (reviewed != True and
    status != "rejected"). Writes the updated JSON back to the same file on
    completion or interrupt so that partial state is never lost.

    Args:
        path: Path to a staging JSON file.

    Returns:
        Summary dict with keys: approved, corrected, rejected, skipped.

    Raises:
        FileNotFoundError: If path does not exist.
        json.JSONDecodeError: If the file is not valid JSON.
    """
    data = json.loads(path.read_text(encoding="utf-8"))
    claims = data.get("claims", [])

    already_decided = sum(1 for c in claims if _is_decided(c))
    total_pending = len(claims) - already_decided

    counts = {
        "approved": 0,
        "corrected": 0,
        "rejected": 0,
        "skipped": already_decided,
    }

    typer.echo(f"\nReviewing: {path.name}")
    typer.echo(f"  {total_pending} claim(s) to review, " f"{already_decided} already decided.")

    if total_pending == 0:
        typer.echo("  Nothing to do.")
        return counts

    pending_index = 0

    try:
        for claim in claims:
            if _is_decided(claim):
                continue

            pending_index += 1
            _display_claim(pending_index, total_pending, claim)
            action = _prompt_action()

            if action == "A":
                claim["reviewed"] = True
                counts["approved"] += 1

            elif action == "C":
                typer.echo(
                    "  Edit the JSON file directly and re-run " "`saskan-lore review` to continue."
                )
                counts["corrected"] += 1

            elif action == "R":
                reason = _prompt_reason()
                claim["status"] = "rejected"
                if reason:
                    claim["reject_reason"] = reason
                counts["rejected"] += 1

            elif action == "Q":
                typer.echo("\n  Session ended early. Writing partial state.")
                break

    finally:
        path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

    return counts


def print_summary(counts: dict) -> None:
    """Print a formatted review session summary to stdout."""
    typer.echo("")
    typer.echo("── Review summary " + "─" * 38)
    typer.echo(f"  Approved  : {counts['approved']}")
    typer.echo(f"  To correct: {counts['corrected']}")
    typer.echo(f"  Rejected  : {counts['rejected']}")
    typer.echo(f"  Skipped   : {counts['skipped']}")
    typer.echo("")

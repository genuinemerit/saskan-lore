#!/usr/bin/env bash
# scripts/load_reviewed.sh
#
# Load all reviewed staging files from var/reviewed/ into the database.
# Only approved and rejected claims are written; pending claims are skipped.
# Safe to re-run — the loader is idempotent.
#
# Usage (from project root, with venv activated):
#   bash scripts/load_reviewed.sh
#
# Optional: pass a glob pattern to load a subset, e.g.:
#   bash scripts/load_reviewed.sh "var/reviewed/chunk_00[0-9][0-9]_extraction.json"

set -euo pipefail

ROOT=$(git rev-parse --show-toplevel)
cd "$ROOT"

PATTERN="${1:-var/reviewed/chunk_*_extraction.json}"

files=( $PATTERN )

if [[ ${#files[@]} -eq 0 ]]; then
    echo "No files matched: $PATTERN"
    exit 1
fi

echo "Loading ${#files[@]} staging file(s)..."
echo ""

ok=0
fail=0

for f in "${files[@]}"; do
    if poetry run saskan-lore load "$f"; then
        (( ok++ )) || true
    else
        echo "  FAILED: $f" >&2
        (( fail++ )) || true
    fi
done

echo ""
echo "Done: $ok loaded, $fail failed."

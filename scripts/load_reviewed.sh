#!/usr/bin/env bash
# scripts/load_reviewed.sh
#
# Load all reviewed staging files from $REVIEWED_DIR into the database.
# Only approved and rejected claims are written; pending claims are skipped.
# Files with no approved/rejected claims are skipped without invoking the
# loader at all, since each invocation pays its own Python/Poetry startup
# cost and a file with nothing decided has nothing to write.
# Safe to re-run — the loader is idempotent.
#
# Usage (from project root, with venv activated, REVIEWED_DIR set via setenv.sh):
#   bash scripts/load_reviewed.sh
#
# Optional: pass a glob pattern to load a subset, e.g.:
#   bash scripts/load_reviewed.sh "$REVIEWED_DIR/chunk_00[0-9][0-9]_extraction.json"

set -euo pipefail

ROOT=$(git rev-parse --show-toplevel)
cd "$ROOT"

: "${REVIEWED_DIR:?REVIEWED_DIR not set; source scripts/setenv.sh first}"
PATTERN="${1:-$REVIEWED_DIR/chunk_*_extraction.json}"

candidates=( $PATTERN )

if [[ ${#candidates[@]} -eq 0 ]]; then
    echo "No files matched: $PATTERN"
    exit 1
fi

files=()
for f in "${candidates[@]}"; do
    if grep -qE '"review_status": "(approved|rejected)"' "$f"; then
        files+=( "$f" )
    fi
done

if [[ ${#files[@]} -eq 0 ]]; then
    echo "No files with approved/rejected claims among ${#candidates[@]} matched: $PATTERN"
    exit 0
fi

echo "Loading ${#files[@]} of ${#candidates[@]} matched file(s) with decided claims..."
echo ""

ok=0
fail=0

for f in "${files[@]}"; do
    echo "$f"
    if LOG_LEVEL=WARNING poetry run saskan-lore load "$f"; then
        (( ok++ )) || true
    else
        echo "  FAILED: $f" >&2
        (( fail++ )) || true
    fi
done

echo ""
echo "Done: $ok loaded, $fail failed."

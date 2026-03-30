#!/usr/bin/env bash
# scripts/commit.sh "<message>" [--push]
#
# Stage all changes, run the test suite, and commit.
# pre-commit hooks (black, ruff) run automatically on git commit.
#
# Options:
#   --push    also push to origin after committing
#
# Usage:
#   ./scripts/commit.sh "feat: add chunker unit tests"
#   ./scripts/commit.sh "fix: correct FK constraint name" --push

set -euo pipefail

# --------------------------------------------------------------------------
# Args
# --------------------------------------------------------------------------
MESSAGE="${1:-}"
PUSH=false

for arg in "$@"; do
    case "$arg" in
        --push) PUSH=true ;;
    esac
done

if [[ -z "$MESSAGE" ]]; then
    echo "Error: commit message is required."
    echo "Usage: ./scripts/commit.sh '<message>' [--push]"
    exit 1
fi

# --------------------------------------------------------------------------
# Repo root (so git add works regardless of where the script is called from)
# --------------------------------------------------------------------------
ROOT=$(git rev-parse --show-toplevel)
BRANCH=$(git rev-parse --abbrev-ref HEAD)

cd "$ROOT"

# --------------------------------------------------------------------------
# Verify there is something to commit
# --------------------------------------------------------------------------
if git diff --quiet && git diff --cached --quiet && \
   [[ -z "$(git ls-files --others --exclude-standard)" ]]; then
    echo "Nothing to commit — working tree is clean."
    exit 0
fi

# --------------------------------------------------------------------------
# Run tests
# --------------------------------------------------------------------------
echo "Running tests..."
poetry run pytest
echo "Tests passed."

# --------------------------------------------------------------------------
# Stage and commit
# --------------------------------------------------------------------------
git add .
git commit -m "$MESSAGE"

# --------------------------------------------------------------------------
# Optional push
# --------------------------------------------------------------------------
if [[ "$PUSH" == true ]]; then
    git push origin "$BRANCH"
    echo "Pushed to origin/$BRANCH."
fi

echo "Done."

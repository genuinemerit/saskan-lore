#!/usr/bin/env bash
# scripts/release.sh <minor|patch> "<description>"
#
# Full release workflow:
#   1. Verify working tree is clean
#   2. Run the full test suite
#   3. Compute the next semver tag (minor or patch bump)
#   4. Update version in pyproject.toml
#   5. Commit the version bump
#   6. Create an annotated git tag
#   7. Push branch and tag to origin
#
# Usage:
#   ./scripts/release.sh minor "R1 database layer complete"
#   ./scripts/release.sh patch "Fix entity alias unique constraint"
#
# See: https://semver.org

set -euo pipefail

# --------------------------------------------------------------------------
# Args
# --------------------------------------------------------------------------
BUMP="${1:-}"
DESC="${2:-}"

if [[ "$BUMP" != "minor" && "$BUMP" != "patch" ]]; then
    echo "Error: first argument must be 'minor' or 'patch'."
    echo "Usage: ./scripts/release.sh <minor|patch> '<description>'"
    exit 1
fi

if [[ -z "$DESC" ]]; then
    echo "Error: release description is required."
    echo "Usage: ./scripts/release.sh <minor|patch> '<description>'"
    exit 1
fi

# --------------------------------------------------------------------------
# Repo root and branch
# --------------------------------------------------------------------------
ROOT=$(git rev-parse --show-toplevel)
BRANCH=$(git rev-parse --abbrev-ref HEAD)
cd "$ROOT"

# --------------------------------------------------------------------------
# Working tree must be clean
# --------------------------------------------------------------------------
if ! git diff --quiet || ! git diff --cached --quiet; then
    echo "Error: uncommitted changes present. Commit or stash before releasing."
    git status --short
    exit 1
fi

# --------------------------------------------------------------------------
# Run full test suite
# --------------------------------------------------------------------------
echo "Running tests..."
poetry run pytest
echo "Tests passed."

# --------------------------------------------------------------------------
# Compute next version
# --------------------------------------------------------------------------
CURRENT=$(git tag --list 'v*' --sort=-version:refname | head -1)
if [[ -z "$CURRENT" ]]; then
    CURRENT="v0.0.0"
    echo "No existing tags found; starting from $CURRENT."
fi

MAJOR=$(echo "$CURRENT" | sed 's/v//' | cut -d. -f1)
MINOR=$(echo "$CURRENT" | sed 's/v//' | cut -d. -f2)
PATCH=$(echo "$CURRENT" | sed 's/v//' | cut -d. -f3)

if [[ "$BUMP" == "minor" ]]; then
    NEW="v${MAJOR}.$((MINOR + 1)).0"
else
    NEW="v${MAJOR}.${MINOR}.$((PATCH + 1))"
fi

echo "Version: $CURRENT -> $NEW"

# --------------------------------------------------------------------------
# Update pyproject.toml
# --------------------------------------------------------------------------
NEW_BARE="${NEW#v}"   # strip leading 'v' for pyproject.toml
# -i.bak + rm is portable across BSD sed (macOS) and GNU sed (Linux); plain
# `sed -i "s/.../"` works on Linux but fails on macOS, which requires an
# explicit (possibly empty) backup-suffix argument after -i.
sed -i.bak "s/^version = \".*\"/version = \"${NEW_BARE}\"/" pyproject.toml
rm -f pyproject.toml.bak

echo "Updated pyproject.toml to version $NEW_BARE."

# --------------------------------------------------------------------------
# Commit version bump if pyproject.toml actually changed
# (pre-commit hooks run here — safe on .toml files)
# --------------------------------------------------------------------------
git add pyproject.toml
if ! git diff --cached --quiet; then
    git commit -m "chore: bump version to $NEW"
else
    echo "pyproject.toml already at $NEW_BARE — skipping version bump commit."
fi

# --------------------------------------------------------------------------
# Annotated tag
# --------------------------------------------------------------------------
git tag -a "$NEW" -m "Release $NEW: $DESC"
echo "Tagged $NEW."

# --------------------------------------------------------------------------
# Push branch and tag
# --------------------------------------------------------------------------
git push origin "$BRANCH"
git push origin "$NEW"

echo ""
echo "Released $NEW to origin/$BRANCH."
echo "Description: $DESC"

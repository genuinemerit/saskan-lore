#!/usr/bin/env bash
# scripts/setenv.sh
#
# Source the environment config for the given environment name.
# Must be SOURCED (not executed) to export variables into the current shell.
#
# Usage:
#   source scripts/setenv.sh [local|test|prod]
#   source scripts/setenv.sh          # defaults to 'local'
#
# Environment files live at: saskan_lore/infra/config/env.<name>
# Copy env.example to create a new env file.

ENV_NAME="${1:-local}"
ENV_FILE="saskan_lore/infra/config/env.${ENV_NAME}"

if [[ -f "$ENV_FILE" ]]; then
    set -a
    # shellcheck source=/dev/null
    source "$ENV_FILE"
    set +a
    echo "Environment loaded: $ENV_FILE"
else
    echo "Error: $ENV_FILE not found." >&2
    # Return when sourced; exit when run directly (incorrect usage).
    return 1 2>/dev/null || exit 1
fi

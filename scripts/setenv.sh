#!/usr/bin/env bash
# scripts/setenv.sh
#
# Source the environment config for the given environment name, then apply
# platform-specific overrides for model path and GPU settings.
# Must be SOURCED (not executed) to export variables into the current shell.
#
# Usage:
#   source scripts/setenv.sh [local|test|prod]
#   source scripts/setenv.sh          # defaults to 'local'
#
# Environment files live at: saskan_lore/infra/config/env.<name>
# Copy env.example to create a new env file.
#
# Platform-specific vars set automatically (see ADR-008):
#   LOCAL_MODEL_PATH   — absolute path to GGUF model file at ~/models/
#   LLAMA_N_GPU_LAYERS — -1 (Metal, Mac) or 0 (CPU, Linux)

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

# ---------------------------------------------------------------------------
# Platform detection — overrides LOCAL_MODEL_PATH and LLAMA_N_GPU_LAYERS
# regardless of what env.<name> contains. See ADR-008.
# ---------------------------------------------------------------------------
_SASKAN_PLATFORM="$(uname -s)"

# Model filenames — update here when the installed model changes.
_MAC_MODEL="Qwen2.5-7B-Instruct-Q4_K_M.gguf"
_LINUX_MODEL="Qwen2.5-3B-Instruct-Q4_K_M.gguf"   # verify size after Linux install

case "$_SASKAN_PLATFORM" in
    Darwin)
        LOCAL_MODEL_PATH="$HOME/models/$_MAC_MODEL"
        LLAMA_N_GPU_LAYERS=-1
        ;;
    Linux)
        LOCAL_MODEL_PATH="$HOME/models/$_LINUX_MODEL"
        LLAMA_N_GPU_LAYERS=0
        ;;
    *)
        echo "Warning: unrecognized platform '$_SASKAN_PLATFORM'." >&2
        echo "  LOCAL_MODEL_PATH and LLAMA_N_GPU_LAYERS not set." >&2
        ;;
esac

export LOCAL_MODEL_PATH LLAMA_N_GPU_LAYERS
echo "Platform: $_SASKAN_PLATFORM  →  model=$(basename "$LOCAL_MODEL_PATH")  gpu_layers=$LLAMA_N_GPU_LAYERS"

unset _SASKAN_PLATFORM _MAC_MODEL _LINUX_MODEL

# ---------------------------------------------------------------------------
# Runtime data directory — machine-local, outside the Dropbox-synced repo.
# SASKAN_VAR_DIR may be set in env.local to override. If not set, defaults
# to $HOME/.local/share/saskan-lore so that each machine has its own
# isolated DB and staging area. See BL-023.
# ---------------------------------------------------------------------------
SASKAN_VAR_DIR="${SASKAN_VAR_DIR:-$HOME/.local/share/saskan-lore}"
mkdir -p "$SASKAN_VAR_DIR/reviewed" "$SASKAN_VAR_DIR/logs"

DATABASE_URL="sqlite:///${SASKAN_VAR_DIR}/saskan_lore.db"
REVIEWED_DIR="${SASKAN_VAR_DIR}/reviewed"
LOG_DIR="${SASKAN_VAR_DIR}/logs"

export SASKAN_VAR_DIR DATABASE_URL REVIEWED_DIR LOG_DIR
echo "Var dir:  $SASKAN_VAR_DIR"

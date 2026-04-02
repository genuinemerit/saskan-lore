# -*- coding: utf-8 -*-
"""
inference.py

Local GGUF model interface for saskan-lore.

Exposes a single public function:

    complete(prompt, *, max_tokens, temperature) -> str
        Send a prompt to the local GGUF model and return the raw text response.

The model is loaded once at module level from the path in LOCAL_MODEL_PATH.
GPU offload layers are controlled by LLAMA_N_GPU_LAYERS (set by setenv.sh).

To swap the inference backend, change only this module. Nothing in extractor.py
or any other module imports llama_cpp directly. See NFR-002, ADR-008.

Environment variables (required — set via scripts/setenv.sh):
    LOCAL_MODEL_PATH    Absolute path to the GGUF model file.
    LLAMA_N_GPU_LAYERS  Number of layers to offload to GPU (-1 = all, 0 = CPU only).

Raises EnvironmentError at import time if LOCAL_MODEL_PATH is missing or empty.
"""

from __future__ import annotations

import logging
import os

from llama_cpp import Llama

log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Environment — validated at import time per ADR-008.
# ---------------------------------------------------------------------------

_model_path = os.environ.get("LOCAL_MODEL_PATH", "").strip()
if not _model_path:
    raise EnvironmentError(
        "LOCAL_MODEL_PATH is not set. "
        "Run 'source scripts/setenv.sh' before using the inference module."
    )

_n_gpu_layers = int(os.environ.get("LLAMA_N_GPU_LAYERS", "0"))

# ---------------------------------------------------------------------------
# Model — loaded once at module level.
# ---------------------------------------------------------------------------

log.info("Loading model: %s (gpu_layers=%d)", _model_path, _n_gpu_layers)

_model = Llama(
    model_path=_model_path,
    n_gpu_layers=_n_gpu_layers,
    n_ctx=2048,
    verbose=False,
)

log.info("Model loaded.")

# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

_DEFAULT_MAX_TOKENS = 512
_DEFAULT_TEMPERATURE = 0.1


def complete(
    prompt: str,
    *,
    max_tokens: int = _DEFAULT_MAX_TOKENS,
    temperature: float = _DEFAULT_TEMPERATURE,
) -> str:
    """Send a prompt to the local GGUF model and return the raw text response.

    Args:
        prompt:       The full prompt string to send to the model.
        max_tokens:   Maximum number of tokens to generate. Default: 512.
        temperature:  Sampling temperature. Default: 0.1 (near-deterministic).
                      Use 0.0 for fully deterministic output where supported.

    Returns:
        Raw text response from the model as a string.

    Raises:
        RuntimeError: If the model returns an empty or malformed response.
    """
    result = _model(
        prompt,
        max_tokens=max_tokens,
        temperature=temperature,
        echo=False,
    )
    try:
        text = result["choices"][0]["text"]
    except (KeyError, IndexError) as exc:
        raise RuntimeError(f"Unexpected model output structure: {result!r}") from exc

    if not text or not text.strip():
        raise RuntimeError("Model returned an empty response.")

    return text.strip()

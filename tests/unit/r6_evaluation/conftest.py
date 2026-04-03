# tests/unit/r6_evaluation/conftest.py
"""
R6 evaluation unit test configuration.

Mocks llama_cpp in sys.modules before any test module is imported so that
inference.py (imported transitively by evaluate.py → answering.py) can be
loaded without a real GGUF model file on disk.

This module runs at pytest collection time — the sys.modules patch and env
vars must be set here, not in a fixture, so they are in place before the
first import of saskan_lore.analyzer.inference.
"""

from __future__ import annotations

import os
import sys
from unittest.mock import MagicMock

# Required by inference.py at import time (ADR-008).
os.environ.setdefault("LOCAL_MODEL_PATH", "/fake/model.gguf")
os.environ.setdefault("LLAMA_N_GPU_LAYERS", "0")

# Replace llama_cpp before inference.py is imported so Llama() is never called
# against a real file. Individual tests patch answer() directly for response
# control.
_mock_llama_module = MagicMock()
_mock_llama_module.Llama.return_value = MagicMock()
sys.modules["llama_cpp"] = _mock_llama_module

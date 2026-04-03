# tests/integration/conftest.py
"""
Integration test configuration.

Mocks llama_cpp in sys.modules before any test module is imported so that
inference.py (imported transitively through extract_chunk and answering) can
be loaded without a real GGUF model file on disk.

This module runs at pytest collection time.
"""

from __future__ import annotations

import os
import sys
from unittest.mock import MagicMock

os.environ.setdefault("LOCAL_MODEL_PATH", "/fake/model.gguf")
os.environ.setdefault("LLAMA_N_GPU_LAYERS", "0")

_mock_llama_module = MagicMock()
_mock_llama_module.Llama.return_value = MagicMock()
sys.modules["llama_cpp"] = _mock_llama_module

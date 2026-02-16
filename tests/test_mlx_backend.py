"""Tests for the MLX backend."""

import sys
from unittest.mock import MagicMock, patch

import pytest


@pytest.fixture
def mock_mlx_modules():
    """Mock mlx_lm modules so MLXBackend can be imported without Apple Silicon."""
    mock_mlx_lm = MagicMock()
    mock_sample_utils = MagicMock()
    mock_mlx_lm.sample_utils = mock_sample_utils

    originals = {}
    for mod in ("mlx_lm", "mlx_lm.sample_utils"):
        originals[mod] = sys.modules.get(mod)
        sys.modules[mod] = mock_mlx_lm if mod == "mlx_lm" else mock_sample_utils

    # Force re-import
    if "backends.mlx_backend" in sys.modules:
        del sys.modules["backends.mlx_backend"]

    yield mock_mlx_lm, mock_sample_utils

    # Restore
    for mod, original in originals.items():
        if original is not None:
            sys.modules[mod] = original
        elif mod in sys.modules:
            del sys.modules[mod]
    if "backends.mlx_backend" in sys.modules:
        del sys.modules["backends.mlx_backend"]


class TestEnableThinking:
    """Tests for the enable_thinking parameter."""

    def test_default_enable_thinking_is_true(self, mock_mlx_modules):
        """Default enable_thinking is True (preserves current behavior)."""
        from backends.mlx_backend import MLXBackend

        backend = MLXBackend()
        assert backend.enable_thinking is True

    def test_enable_thinking_false_stored(self, mock_mlx_modules):
        """enable_thinking=False is stored on the instance."""
        from backends.mlx_backend import MLXBackend

        backend = MLXBackend(enable_thinking=False)
        assert backend.enable_thinking is False

    def test_thinking_disabled_passes_kwarg_to_template(self, mock_mlx_modules):
        """When thinking disabled, apply_chat_template gets enable_thinking=False."""
        mock_mlx_lm, mock_sample_utils = mock_mlx_modules
        from backends.mlx_backend import MLXBackend

        backend = MLXBackend(enable_thinking=False)

        # Set up mocks for generate flow
        mock_model = MagicMock()
        mock_tokenizer = MagicMock()
        mock_tokenizer.apply_chat_template.return_value = "formatted prompt"
        mock_tokenizer.encode.return_value = [1, 2, 3]

        backend._model = mock_model
        backend._tokenizer = mock_tokenizer
        backend._sampler = MagicMock()
        backend._logits_processors = MagicMock()

        mock_mlx_lm.generate.return_value = "response"

        backend.generate("test prompt")

        # Verify apply_chat_template was called with enable_thinking=False
        mock_tokenizer.apply_chat_template.assert_called_once()
        call_kwargs = mock_tokenizer.apply_chat_template.call_args
        assert call_kwargs.kwargs.get("enable_thinking") is False

    def test_thinking_enabled_omits_kwarg(self, mock_mlx_modules):
        """When thinking enabled (default), enable_thinking is not passed."""
        mock_mlx_lm, mock_sample_utils = mock_mlx_modules
        from backends.mlx_backend import MLXBackend

        backend = MLXBackend(enable_thinking=True)

        mock_model = MagicMock()
        mock_tokenizer = MagicMock()
        mock_tokenizer.apply_chat_template.return_value = "formatted prompt"
        mock_tokenizer.encode.return_value = [1, 2, 3]

        backend._model = mock_model
        backend._tokenizer = mock_tokenizer
        backend._sampler = MagicMock()
        backend._logits_processors = MagicMock()

        mock_mlx_lm.generate.return_value = "response"

        backend.generate("test prompt")

        # enable_thinking should NOT be in the kwargs (preserve default behavior)
        call_kwargs = mock_tokenizer.apply_chat_template.call_args
        assert "enable_thinking" not in call_kwargs.kwargs

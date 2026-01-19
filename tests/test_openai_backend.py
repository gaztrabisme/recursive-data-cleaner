"""Tests for the OpenAI-compatible backend."""

import os
import sys
import pytest
from unittest.mock import MagicMock, patch


class TestOpenAIBackendImport:
    """Test import handling for OpenAI backend."""

    def test_import_error_without_openai(self):
        """OpenAIBackend raises ImportError when openai not installed."""
        # Save original module if exists
        original_openai = sys.modules.get("openai")

        try:
            # Remove openai from modules to simulate not installed
            sys.modules["openai"] = None

            # Force re-import
            import importlib
            if "backends.openai_backend" in sys.modules:
                del sys.modules["backends.openai_backend"]

            import backends.openai_backend as backend_module

            with pytest.raises(ImportError, match="OpenAI SDK not installed"):
                backend_module.OpenAIBackend(model="test")
        finally:
            # Restore original state
            if original_openai is not None:
                sys.modules["openai"] = original_openai
            elif "openai" in sys.modules:
                del sys.modules["openai"]

            # Force re-import to restore normal state
            if "backends.openai_backend" in sys.modules:
                del sys.modules["backends.openai_backend"]


class TestOpenAIBackendInit:
    """Test OpenAI backend initialization."""

    @pytest.fixture
    def mock_openai_module(self):
        """Mock the openai module at sys.modules level."""
        mock = MagicMock()

        # Save and replace
        original = sys.modules.get("openai")
        sys.modules["openai"] = mock

        # Clear cached import
        if "backends.openai_backend" in sys.modules:
            del sys.modules["backends.openai_backend"]

        yield mock

        # Restore
        if original is not None:
            sys.modules["openai"] = original
        elif "openai" in sys.modules:
            del sys.modules["openai"]

        if "backends.openai_backend" in sys.modules:
            del sys.modules["backends.openai_backend"]

    def test_backend_uses_explicit_api_key(self, mock_openai_module):
        """Backend uses explicitly provided API key."""
        from backends.openai_backend import OpenAIBackend

        backend = OpenAIBackend(model="gpt-4o", api_key="explicit-key")

        # Check the client was created with the explicit key
        mock_openai_module.OpenAI.assert_called_once()
        call_kwargs = mock_openai_module.OpenAI.call_args[1]
        assert call_kwargs["api_key"] == "explicit-key"

    def test_backend_uses_env_var_api_key(self, mock_openai_module, monkeypatch):
        """Backend reads API key from OPENAI_API_KEY env var."""
        monkeypatch.setenv("OPENAI_API_KEY", "env-api-key")

        from backends.openai_backend import OpenAIBackend

        backend = OpenAIBackend(model="gpt-4o")

        call_kwargs = mock_openai_module.OpenAI.call_args[1]
        assert call_kwargs["api_key"] == "env-api-key"

    def test_backend_uses_not_needed_for_local(self, mock_openai_module, monkeypatch):
        """Backend uses 'not-needed' when no API key available."""
        # Ensure no env var
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)

        from backends.openai_backend import OpenAIBackend

        backend = OpenAIBackend(model="local-model")

        call_kwargs = mock_openai_module.OpenAI.call_args[1]
        assert call_kwargs["api_key"] == "not-needed"

    def test_backend_custom_base_url(self, mock_openai_module):
        """Backend passes custom base_url to client."""
        from backends.openai_backend import OpenAIBackend

        backend = OpenAIBackend(
            model="local-model",
            base_url="http://localhost:1234/v1"
        )

        call_kwargs = mock_openai_module.OpenAI.call_args[1]
        assert call_kwargs["base_url"] == "http://localhost:1234/v1"

    def test_backend_default_base_url_is_none(self, mock_openai_module):
        """Backend uses None for base_url by default (uses OpenAI's API)."""
        from backends.openai_backend import OpenAIBackend

        backend = OpenAIBackend(model="gpt-4o", api_key="key")

        call_kwargs = mock_openai_module.OpenAI.call_args[1]
        assert call_kwargs["base_url"] is None


class TestOpenAIBackendGenerate:
    """Test OpenAI backend generate method."""

    @pytest.fixture
    def mock_openai_with_response(self):
        """Mock openai module with response setup."""
        mock = MagicMock()

        # Setup mock response
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = "Generated response"

        mock_client = MagicMock()
        mock_client.chat.completions.create.return_value = mock_response
        mock.OpenAI.return_value = mock_client

        # Save and replace
        original = sys.modules.get("openai")
        sys.modules["openai"] = mock

        # Clear cached import
        if "backends.openai_backend" in sys.modules:
            del sys.modules["backends.openai_backend"]

        yield mock, mock_client, mock_response

        # Restore
        if original is not None:
            sys.modules["openai"] = original
        elif "openai" in sys.modules:
            del sys.modules["openai"]

        if "backends.openai_backend" in sys.modules:
            del sys.modules["backends.openai_backend"]

    def test_generate_returns_content(self, mock_openai_with_response):
        """Generate returns the message content from response."""
        mock, mock_client, mock_response = mock_openai_with_response

        from backends.openai_backend import OpenAIBackend

        backend = OpenAIBackend(model="gpt-4o", api_key="key")
        result = backend.generate("Test prompt")

        assert result == "Generated response"

    def test_generate_passes_correct_parameters(self, mock_openai_with_response):
        """Generate passes model, messages, max_tokens, temperature."""
        mock, mock_client, mock_response = mock_openai_with_response

        from backends.openai_backend import OpenAIBackend

        backend = OpenAIBackend(
            model="gpt-4o",
            api_key="key",
            max_tokens=2048,
            temperature=0.5
        )
        backend.generate("Test prompt")

        mock_client.chat.completions.create.assert_called_once_with(
            model="gpt-4o",
            messages=[{"role": "user", "content": "Test prompt"}],
            max_tokens=2048,
            temperature=0.5,
        )

    def test_generate_handles_empty_content(self):
        """Generate returns empty string when content is None."""
        mock = MagicMock()

        # Setup mock response with None content
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = None

        mock_client = MagicMock()
        mock_client.chat.completions.create.return_value = mock_response
        mock.OpenAI.return_value = mock_client

        original = sys.modules.get("openai")
        sys.modules["openai"] = mock

        if "backends.openai_backend" in sys.modules:
            del sys.modules["backends.openai_backend"]

        try:
            from backends.openai_backend import OpenAIBackend

            backend = OpenAIBackend(model="gpt-4o", api_key="key")
            result = backend.generate("Test prompt")

            assert result == ""
        finally:
            if original is not None:
                sys.modules["openai"] = original
            elif "openai" in sys.modules:
                del sys.modules["openai"]

            if "backends.openai_backend" in sys.modules:
                del sys.modules["backends.openai_backend"]


class TestOpenAIBackendExport:
    """Test that OpenAIBackend is properly exported."""

    def test_export_from_backends(self):
        """OpenAIBackend is exported from backends package."""
        from backends import OpenAIBackend
        assert OpenAIBackend is not None

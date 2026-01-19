"""Tests for the CLI module."""

import os
import sys
import pytest
from unittest.mock import MagicMock, patch

from recursive_cleaner.cli import (
    create_parser,
    create_backend,
    read_instructions,
    main,
)


class MockLLM:
    """Mock LLM for testing."""

    def __init__(self, response: str = ""):
        self.response = response

    def generate(self, prompt: str) -> str:
        return self.response


# Sample valid XML response for integration tests
RESPONSE_CLEAN = '''
<cleaning_analysis>
  <issues_detected>
    <issue id="1" solved="true">Data is clean</issue>
  </issues_detected>
  <chunk_status>clean</chunk_status>
</cleaning_analysis>
'''


class TestHelpCommand:
    """Test help commands."""

    def test_help_returns_zero(self, capsys):
        """--help returns exit code 0."""
        parser = create_parser()
        with pytest.raises(SystemExit) as exc_info:
            parser.parse_args(["--help"])
        assert exc_info.value.code == 0

    def test_generate_help_returns_zero(self, capsys):
        """generate --help returns exit code 0."""
        parser = create_parser()
        with pytest.raises(SystemExit) as exc_info:
            parser.parse_args(["generate", "--help"])
        assert exc_info.value.code == 0

    def test_analyze_help_returns_zero(self, capsys):
        """analyze --help returns exit code 0."""
        parser = create_parser()
        with pytest.raises(SystemExit) as exc_info:
            parser.parse_args(["analyze", "--help"])
        assert exc_info.value.code == 0

    def test_resume_help_returns_zero(self, capsys):
        """resume --help returns exit code 0."""
        parser = create_parser()
        with pytest.raises(SystemExit) as exc_info:
            parser.parse_args(["resume", "--help"])
        assert exc_info.value.code == 0


class TestGenerateCommandArgs:
    """Test generate command argument parsing."""

    def test_parse_generate_required_args(self):
        """Parse generate with required args."""
        parser = create_parser()
        args = parser.parse_args([
            "generate", "data.jsonl",
            "--provider", "mlx",
            "--model", "test-model"
        ])
        assert args.command == "generate"
        assert args.file == "data.jsonl"
        assert args.provider == "mlx"
        assert args.model == "test-model"

    def test_parse_generate_all_options(self):
        """Parse generate with all optional args."""
        parser = create_parser()
        args = parser.parse_args([
            "generate", "data.jsonl",
            "-p", "openai",
            "-m", "gpt-4o",
            "-i", "Fix phones",
            "--base-url", "http://localhost:1234/v1",
            "--api-key", "test-key",
            "--chunk-size", "100",
            "--max-iterations", "3",
            "--mode", "structured",
            "-o", "output.py",
            "--report", "report.md",
            "--state-file", "state.json",
            "--tui",
            "--optimize",
            "--track-metrics",
            "--early-termination"
        ])
        assert args.provider == "openai"
        assert args.model == "gpt-4o"
        assert args.instructions == "Fix phones"
        assert args.base_url == "http://localhost:1234/v1"
        assert args.api_key == "test-key"
        assert args.chunk_size == 100
        assert args.max_iterations == 3
        assert args.mode == "structured"
        assert args.output == "output.py"
        assert args.report == "report.md"
        assert args.state_file == "state.json"
        assert args.tui is True
        assert args.optimize is True
        assert args.track_metrics is True
        assert args.early_termination is True

    def test_generate_defaults(self):
        """Generate has correct defaults."""
        parser = create_parser()
        args = parser.parse_args([
            "generate", "data.jsonl",
            "-p", "mlx", "-m", "model"
        ])
        assert args.instructions == ""
        assert args.chunk_size == 50
        assert args.max_iterations == 5
        assert args.mode == "auto"
        assert args.output == "cleaning_functions.py"
        assert args.report == "cleaning_report.md"
        assert args.state_file is None
        assert args.tui is False
        assert args.optimize is False


class TestAnalyzeCommandArgs:
    """Test analyze command argument parsing."""

    def test_parse_analyze_required_args(self):
        """Parse analyze with required args."""
        parser = create_parser()
        args = parser.parse_args([
            "analyze", "data.jsonl",
            "--provider", "mlx",
            "--model", "test-model"
        ])
        assert args.command == "analyze"
        assert args.file == "data.jsonl"
        assert args.provider == "mlx"
        assert args.model == "test-model"

    def test_parse_analyze_with_options(self):
        """Parse analyze with optional args."""
        parser = create_parser()
        args = parser.parse_args([
            "analyze", "data.jsonl",
            "-p", "openai",
            "-m", "gpt-4o",
            "-i", "Check data quality",
            "--chunk-size", "25",
            "--tui"
        ])
        assert args.instructions == "Check data quality"
        assert args.chunk_size == 25
        assert args.tui is True


class TestResumeCommandArgs:
    """Test resume command argument parsing."""

    def test_parse_resume_required_args(self):
        """Parse resume with required args."""
        parser = create_parser()
        args = parser.parse_args([
            "resume", "state.json",
            "--provider", "mlx",
            "--model", "test-model"
        ])
        assert args.command == "resume"
        assert args.state_file == "state.json"
        assert args.provider == "mlx"
        assert args.model == "test-model"

    def test_parse_resume_with_provider_options(self):
        """Parse resume with provider options."""
        parser = create_parser()
        args = parser.parse_args([
            "resume", "state.json",
            "-p", "openai",
            "-m", "gpt-4o",
            "--base-url", "http://localhost:1234/v1",
            "--api-key", "key"
        ])
        assert args.base_url == "http://localhost:1234/v1"
        assert args.api_key == "key"


class TestInstructionsFromFile:
    """Test reading instructions from file."""

    def test_instructions_inline(self):
        """Inline instructions are returned as-is."""
        result = read_instructions("Normalize phone numbers")
        assert result == "Normalize phone numbers"

    def test_instructions_from_file(self, tmp_path):
        """@file.txt reads from file."""
        inst_file = tmp_path / "instructions.txt"
        inst_file.write_text("Fix dates\nNormalize phones")

        result = read_instructions(f"@{inst_file}")
        assert result == "Fix dates\nNormalize phones"

    def test_instructions_file_not_found(self, tmp_path):
        """Missing instructions file exits with code 1."""
        with pytest.raises(SystemExit) as exc_info:
            read_instructions("@/nonexistent/file.txt")
        assert exc_info.value.code == 1

    def test_instructions_strips_whitespace(self, tmp_path):
        """Instructions from file are stripped."""
        inst_file = tmp_path / "instructions.txt"
        inst_file.write_text("  Clean data  \n")

        result = read_instructions(f"@{inst_file}")
        assert result == "Clean data"


class TestBackendFactory:
    """Test backend factory function."""

    def test_backend_factory_invalid_provider(self, capsys):
        """Factory exits with code 2 for invalid provider."""
        with pytest.raises(SystemExit) as exc_info:
            create_backend("invalid", "model", None, None)
        assert exc_info.value.code == 2

    def test_backend_factory_openai(self):
        """Factory creates OpenAIBackend for openai provider."""
        mock = MagicMock()
        original = sys.modules.get("openai")
        sys.modules["openai"] = mock

        # Clear cached import
        if "backends.openai_backend" in sys.modules:
            del sys.modules["backends.openai_backend"]

        try:
            backend = create_backend("openai", "gpt-4o", None, "test-key")
            assert backend is not None
        finally:
            if original is not None:
                sys.modules["openai"] = original
            elif "openai" in sys.modules:
                del sys.modules["openai"]

            if "backends.openai_backend" in sys.modules:
                del sys.modules["backends.openai_backend"]

    def test_backend_factory_openai_custom_url(self):
        """Factory passes custom base_url to OpenAIBackend."""
        mock = MagicMock()
        original = sys.modules.get("openai")
        sys.modules["openai"] = mock

        # Clear cached import
        if "backends.openai_backend" in sys.modules:
            del sys.modules["backends.openai_backend"]

        try:
            backend = create_backend(
                "openai", "local-model",
                "http://localhost:1234/v1", "key"
            )
            call_kwargs = mock.OpenAI.call_args[1]
            assert call_kwargs["base_url"] == "http://localhost:1234/v1"
        finally:
            if original is not None:
                sys.modules["openai"] = original
            elif "openai" in sys.modules:
                del sys.modules["openai"]

            if "backends.openai_backend" in sys.modules:
                del sys.modules["backends.openai_backend"]


class TestExitCodes:
    """Test CLI exit codes."""

    def test_exit_code_file_not_found(self, tmp_path):
        """Returns 1 for missing input file."""
        result = main([
            "generate", "/nonexistent/file.jsonl",
            "-p", "mlx", "-m", "model"
        ])
        assert result == 1

    def test_exit_code_invalid_provider(self, tmp_path, capsys):
        """Returns 2 for invalid provider."""
        test_file = tmp_path / "data.jsonl"
        test_file.write_text('{"a": 1}\n')

        # Capture stderr and check exit code
        with pytest.raises(SystemExit) as exc_info:
            create_backend("invalid", "model", None, None)
        assert exc_info.value.code == 2

    def test_exit_code_missing_state_file(self):
        """Resume returns 1 for missing state file."""
        result = main([
            "resume", "/nonexistent/state.json",
            "-p", "mlx", "-m", "model"
        ])
        assert result == 1

    def test_no_command_returns_zero(self, capsys):
        """No command shows help and returns 0."""
        result = main([])
        assert result == 0


class TestIntegrationWithMockLLM:
    """Integration tests with mocked LLM."""

    def test_generate_end_to_end(self, tmp_path):
        """Full generate command with mock LLM."""
        # Create test file
        test_file = tmp_path / "data.jsonl"
        test_file.write_text('{"name": "test"}\n')

        mock_backend = MockLLM(RESPONSE_CLEAN)

        with patch("recursive_cleaner.cli.create_backend", return_value=mock_backend):
            result = main([
                "generate", str(test_file),
                "-p", "mlx", "-m", "model",
                "-i", "Test"
            ])
            assert result == 0

    def test_analyze_end_to_end(self, tmp_path):
        """Full analyze command with mock LLM."""
        test_file = tmp_path / "data.jsonl"
        test_file.write_text('{"name": "test"}\n')

        mock_backend = MockLLM(RESPONSE_CLEAN)

        with patch("recursive_cleaner.cli.create_backend", return_value=mock_backend):
            result = main([
                "analyze", str(test_file),
                "-p", "mlx", "-m", "model"
            ])
            assert result == 0

    def test_resume_end_to_end(self, tmp_path):
        """Full resume command with mock LLM and valid state file."""
        # Create test data file
        test_file = tmp_path / "data.jsonl"
        test_file.write_text('{"name": "test"}\n')

        # Create valid state file
        state_file = tmp_path / "state.json"
        state_file.write_text('''{
            "version": "0.5.0",
            "file_path": "''' + str(test_file) + '''",
            "instructions": "Test",
            "chunk_size": 50,
            "last_completed_chunk": -1,
            "total_chunks": 1,
            "functions": []
        }''')

        mock_backend = MockLLM(RESPONSE_CLEAN)

        with patch("recursive_cleaner.cli.create_backend", return_value=mock_backend):
            result = main([
                "resume", str(state_file),
                "-p", "mlx", "-m", "model"
            ])
            assert result == 0


class TestEnvVarApiKey:
    """Test environment variable API key handling."""

    def test_env_var_api_key(self, monkeypatch):
        """Backend reads OPENAI_API_KEY from environment."""
        monkeypatch.setenv("OPENAI_API_KEY", "env-test-key")

        mock = MagicMock()
        original = sys.modules.get("openai")
        sys.modules["openai"] = mock

        if "backends.openai_backend" in sys.modules:
            del sys.modules["backends.openai_backend"]

        try:
            backend = create_backend("openai", "gpt-4o", None, None)
            call_kwargs = mock.OpenAI.call_args[1]
            assert call_kwargs["api_key"] == "env-test-key"
        finally:
            if original is not None:
                sys.modules["openai"] = original
            elif "openai" in sys.modules:
                del sys.modules["openai"]

            if "backends.openai_backend" in sys.modules:
                del sys.modules["backends.openai_backend"]

    def test_explicit_key_overrides_env(self, monkeypatch):
        """Explicit API key overrides environment variable."""
        monkeypatch.setenv("OPENAI_API_KEY", "env-key")

        mock = MagicMock()
        original = sys.modules.get("openai")
        sys.modules["openai"] = mock

        if "backends.openai_backend" in sys.modules:
            del sys.modules["backends.openai_backend"]

        try:
            backend = create_backend("openai", "gpt-4o", None, "explicit-key")
            call_kwargs = mock.OpenAI.call_args[1]
            assert call_kwargs["api_key"] == "explicit-key"
        finally:
            if original is not None:
                sys.modules["openai"] = original
            elif "openai" in sys.modules:
                del sys.modules["openai"]

            if "backends.openai_backend" in sys.modules:
                del sys.modules["backends.openai_backend"]

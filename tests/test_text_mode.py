"""Tests for text mode functionality in DataCleaner."""

import tempfile
from pathlib import Path

import pytest

from recursive_cleaner import DataCleaner, build_prompt
from recursive_cleaner.parsers import chunk_file, chunk_text_sentences, _detect_mode
from recursive_cleaner.validation import extract_sample_data, validate_function
from recursive_cleaner.prompt import TEXT_PROMPT_TEMPLATE, STRUCTURED_PROMPT_TEMPLATE


class MockLLM:
    """Mock LLM that returns predefined responses."""

    def __init__(self, responses: list[str]):
        self.responses = iter(responses)
        self.calls = []

    def generate(self, prompt: str) -> str:
        self.calls.append(prompt)
        return next(self.responses)


# Sample valid XML responses for text mode
TEXT_RESPONSE_WITH_FUNCTION = '''
<cleaning_analysis>
  <issues_detected>
    <issue id="1" solved="false">Multiple spaces between words</issue>
  </issues_detected>
  <function_to_generate>
    <name>normalize_whitespace</name>
    <docstring>Normalize multiple spaces to single space.</docstring>
    <code>
```python
def normalize_whitespace(text: str) -> str:
    import re
    return re.sub(r' +', ' ', text)
```
    </code>
  </function_to_generate>
  <chunk_status>needs_more_work</chunk_status>
</cleaning_analysis>
'''

TEXT_RESPONSE_CLEAN = '''
<cleaning_analysis>
  <issues_detected>
    <issue id="1" solved="true">Whitespace - handled by normalize_whitespace</issue>
  </issues_detected>
  <chunk_status>clean</chunk_status>
</cleaning_analysis>
'''


# =============================================================================
# Mode Detection Tests
# =============================================================================


class TestModeDetection:
    """Tests for automatic mode detection from file extension."""

    def test_detect_mode_txt_returns_text(self):
        """Test that .txt files are detected as text mode."""
        assert _detect_mode(".txt") == "text"

    def test_detect_mode_md_returns_text(self):
        """Test that .md files are detected as text mode."""
        assert _detect_mode(".md") == "text"

    def test_detect_mode_jsonl_returns_structured(self):
        """Test that .jsonl files are detected as structured mode."""
        assert _detect_mode(".jsonl") == "structured"

    def test_detect_mode_csv_returns_structured(self):
        """Test that .csv files are detected as structured mode."""
        assert _detect_mode(".csv") == "structured"

    def test_detect_mode_json_returns_structured(self):
        """Test that .json files are detected as structured mode."""
        assert _detect_mode(".json") == "structured"

    def test_detect_mode_unknown_returns_text(self):
        """Test that unknown extensions default to text mode."""
        assert _detect_mode(".xyz") == "text"
        assert _detect_mode(".log") == "text"
        assert _detect_mode("") == "text"


class TestDataCleanerModeDetection:
    """Tests for DataCleaner mode detection."""

    def test_auto_mode_detects_txt_as_text(self, tmp_path):
        """Test that auto mode detects .txt as text mode."""
        test_file = tmp_path / "test.txt"
        test_file.write_text("Hello world. This is a test.")

        mock_llm = MockLLM([TEXT_RESPONSE_CLEAN])
        cleaner = DataCleaner(
            llm_backend=mock_llm,
            file_path=str(test_file),
            mode="auto",
            chunk_size=4000,  # Use character count for text mode
        )
        cleaner.run()

        assert cleaner._effective_mode == "text"

    def test_auto_mode_detects_jsonl_as_structured(self, tmp_path):
        """Test that auto mode detects .jsonl as structured mode."""
        test_file = tmp_path / "test.jsonl"
        test_file.write_text('{"key": "value"}\n')

        # Use structured response format
        structured_response = '''
<cleaning_analysis>
  <issues_detected></issues_detected>
  <chunk_status>clean</chunk_status>
</cleaning_analysis>
'''
        mock_llm = MockLLM([structured_response])
        cleaner = DataCleaner(
            llm_backend=mock_llm,
            file_path=str(test_file),
            mode="auto",
        )
        cleaner.run()

        assert cleaner._effective_mode == "structured"

    def test_mode_override_works(self, tmp_path):
        """Test that explicit mode overrides auto-detection."""
        # Create a .jsonl file but force text mode
        test_file = tmp_path / "test.jsonl"
        test_file.write_text('{"key": "value"}\n')

        mock_llm = MockLLM([TEXT_RESPONSE_CLEAN])
        cleaner = DataCleaner(
            llm_backend=mock_llm,
            file_path=str(test_file),
            mode="text",  # Force text mode
            chunk_size=4000,  # Use character count for text mode
        )
        cleaner.run()

        assert cleaner._effective_mode == "text"


# =============================================================================
# Text Chunking Tests
# =============================================================================


class TestTextChunking:
    """Tests for text mode chunking with sentence awareness."""

    def test_chunk_text_sentences_basic(self):
        """Test basic sentence-aware chunking."""
        text = "First sentence. Second sentence. Third sentence."
        chunks = chunk_text_sentences(text, chunk_size=50, chunk_overlap=10)

        assert len(chunks) >= 1
        # All content should be preserved across chunks
        combined = " ".join(chunks)
        assert "First sentence" in combined
        assert "Third sentence" in combined

    def test_chunk_text_sentences_respects_size(self):
        """Test that chunks respect size limit."""
        text = "A" * 100 + ". " + "B" * 100 + ". " + "C" * 100
        chunks = chunk_text_sentences(text, chunk_size=150, chunk_overlap=20)

        # Most chunks should be within size limit (allowing some flexibility)
        for chunk in chunks:
            # Allow some overhead for paragraph joining
            assert len(chunk) <= 200

    def test_chunk_text_with_paragraphs(self):
        """Test chunking with paragraph breaks."""
        text = "First paragraph.\n\nSecond paragraph.\n\nThird paragraph."
        chunks = chunk_text_sentences(text, chunk_size=100, chunk_overlap=20)

        assert len(chunks) >= 1

    def test_chunk_file_text_mode(self, tmp_path):
        """Test chunk_file uses sentence chunking for text files."""
        test_file = tmp_path / "test.txt"
        test_file.write_text("First sentence. Second sentence. Third sentence.")

        chunks = chunk_file(str(test_file), chunk_size=4000, mode="text")

        assert len(chunks) >= 1
        assert "sentence" in chunks[0]

    def test_chunk_file_passes_overlap(self, tmp_path):
        """Test that chunk_file passes overlap parameter for text mode."""
        test_file = tmp_path / "test.txt"
        # Create content that will need multiple chunks
        text = ("This is a sentence. " * 100)
        test_file.write_text(text)

        chunks_with_overlap = chunk_file(
            str(test_file), chunk_size=500, mode="text", chunk_overlap=50
        )
        chunks_without_overlap = chunk_file(
            str(test_file), chunk_size=500, mode="text", chunk_overlap=0
        )

        # With overlap, chunks may have shared content
        assert len(chunks_with_overlap) >= 1
        assert len(chunks_without_overlap) >= 1


# =============================================================================
# Prompt Template Tests
# =============================================================================


class TestTextPromptTemplate:
    """Tests for text mode prompt template."""

    def test_text_prompt_template_exists(self):
        """Test that TEXT_PROMPT_TEMPLATE is defined."""
        assert TEXT_PROMPT_TEMPLATE is not None
        assert len(TEXT_PROMPT_TEMPLATE) > 0

    def test_text_prompt_has_text_signature(self):
        """Test that TEXT_PROMPT_TEMPLATE shows text function signature."""
        assert "def function_name(text: str) -> str:" in TEXT_PROMPT_TEMPLATE

    def test_text_prompt_mentions_text_issues(self):
        """Test that TEXT_PROMPT_TEMPLATE mentions text-specific issues."""
        assert "text" in TEXT_PROMPT_TEMPLATE.lower()
        assert "artifacts" in TEXT_PROMPT_TEMPLATE.lower() or "spacing" in TEXT_PROMPT_TEMPLATE.lower()

    def test_build_prompt_uses_text_template(self):
        """Test that build_prompt uses TEXT_PROMPT_TEMPLATE for text mode."""
        prompt = build_prompt(
            instructions="Fix OCR errors",
            context="(No functions yet)",
            chunk="Sorne text with OCR errers.",
            schema="",
            mode="text",
        )

        # Should have text-specific content
        assert "def function_name(text: str) -> str:" in prompt
        # Should NOT have schema section
        assert "=== DATA SCHEMA ===" not in prompt

    def test_build_prompt_uses_structured_template(self):
        """Test that build_prompt uses structured template by default."""
        prompt = build_prompt(
            instructions="Fix data",
            context="(No functions yet)",
            chunk='{"key": "value"}',
            schema="key: string",
            mode="structured",
        )

        # Should have structured-specific content
        assert "def function_name(data):" in prompt
        # Should have schema section
        assert "=== DATA SCHEMA ===" in prompt


# =============================================================================
# Validation Tests
# =============================================================================


class TestTextModeValidation:
    """Tests for validation in text mode."""

    def test_extract_sample_data_text_mode(self):
        """Test that extract_sample_data returns string for text mode."""
        chunk = "This is some text content."
        result = extract_sample_data(chunk, mode="text")

        assert isinstance(result, str)
        assert result == chunk

    def test_extract_sample_data_structured_mode(self):
        """Test that extract_sample_data returns list for structured mode."""
        chunk = '{"key": "value1"}\n{"key": "value2"}'
        result = extract_sample_data(chunk, mode="structured")

        assert isinstance(result, list)
        assert len(result) == 2

    def test_validate_function_text_mode_valid(self):
        """Test validation passes for valid text function."""
        code = '''
def fix_spaces(text: str) -> str:
    return text.replace("  ", " ")
'''
        valid, error = validate_function(
            code, "Hello  world", "fix_spaces", mode="text"
        )

        assert valid is True
        assert error is None

    def test_validate_function_text_mode_checks_return_type(self):
        """Test validation fails if text function doesn't return string."""
        code = '''
def bad_func(text: str) -> str:
    return 123  # Returns int, not str
'''
        valid, error = validate_function(
            code, "Hello world", "bad_func", mode="text"
        )

        assert valid is False
        assert "must return str" in error

    def test_validate_function_text_mode_catches_runtime_error(self):
        """Test validation catches runtime errors in text mode."""
        code = '''
def crash_func(text: str) -> str:
    raise ValueError("Intentional error")
'''
        valid, error = validate_function(
            code, "Hello world", "crash_func", mode="text"
        )

        assert valid is False
        assert "Runtime error" in error

    def test_validate_function_empty_text_passes(self):
        """Test validation passes for empty text input."""
        code = '''
def some_func(text: str) -> str:
    return text
'''
        valid, error = validate_function(
            code, "", "some_func", mode="text"
        )

        assert valid is True


# =============================================================================
# Schema Tests
# =============================================================================


class TestSchemaSkippedForTextMode:
    """Tests that schema inference is skipped for text mode."""

    def test_schema_empty_for_text_mode(self, tmp_path):
        """Test that _schema_str is empty for text mode."""
        test_file = tmp_path / "test.txt"
        test_file.write_text("Some text content here.")

        mock_llm = MockLLM([TEXT_RESPONSE_CLEAN])
        cleaner = DataCleaner(
            llm_backend=mock_llm,
            file_path=str(test_file),
            mode="text",
            chunk_size=4000,  # Use character count for text mode
        )
        cleaner.run()

        assert cleaner._schema_str == ""

    def test_prompt_has_no_schema_for_text_mode(self, tmp_path):
        """Test that prompt doesn't include schema for text mode."""
        test_file = tmp_path / "test.txt"
        test_file.write_text("Some text content here.")

        mock_llm = MockLLM([TEXT_RESPONSE_CLEAN])
        cleaner = DataCleaner(
            llm_backend=mock_llm,
            file_path=str(test_file),
            mode="text",
            chunk_size=4000,  # Use character count for text mode
        )
        cleaner.run()

        # Check the prompt that was sent to the LLM
        assert len(mock_llm.calls) == 1
        prompt = mock_llm.calls[0]
        assert "=== DATA SCHEMA ===" not in prompt


# =============================================================================
# Integration Tests
# =============================================================================


class TestTextModeIntegration:
    """End-to-end tests for text mode."""

    def test_text_mode_generates_function(self, tmp_path):
        """Test that text mode can generate cleaning functions."""
        test_file = tmp_path / "test.txt"
        test_file.write_text("This  has   extra   spaces.")

        mock_llm = MockLLM([TEXT_RESPONSE_WITH_FUNCTION, TEXT_RESPONSE_CLEAN])

        cleaner = DataCleaner(
            llm_backend=mock_llm,
            file_path=str(test_file),
            mode="text",
            chunk_size=4000,  # Use character count for text mode
            instructions="Fix spacing issues",
        )
        cleaner.run()

        assert len(cleaner.functions) == 1
        assert cleaner.functions[0]["name"] == "normalize_whitespace"

    def test_text_mode_function_has_correct_signature(self, tmp_path):
        """Test that generated functions have text signature."""
        test_file = tmp_path / "test.txt"
        test_file.write_text("Test content.")

        mock_llm = MockLLM([TEXT_RESPONSE_WITH_FUNCTION, TEXT_RESPONSE_CLEAN])

        cleaner = DataCleaner(
            llm_backend=mock_llm,
            file_path=str(test_file),
            mode="text",
            chunk_size=4000,  # Use character count for text mode
        )
        cleaner.run()

        # Check the function code has text signature
        func_code = cleaner.functions[0]["code"]
        assert "def normalize_whitespace(text: str) -> str:" in func_code

    def test_chunk_overlap_parameter(self, tmp_path):
        """Test that chunk_overlap parameter is accepted."""
        test_file = tmp_path / "test.txt"
        test_file.write_text("A" * 1000)

        mock_llm = MockLLM([TEXT_RESPONSE_CLEAN])

        # Should not raise error
        cleaner = DataCleaner(
            llm_backend=mock_llm,
            file_path=str(test_file),
            mode="text",
            chunk_size=4000,  # Use character count for text mode
            chunk_overlap=100,
        )
        cleaner.run()

        assert cleaner.chunk_overlap == 100

    def test_text_mode_md_file(self, tmp_path):
        """Test that .md files work in text mode."""
        test_file = tmp_path / "test.md"
        test_file.write_text("# Heading\n\nSome markdown content.")

        mock_llm = MockLLM([TEXT_RESPONSE_CLEAN])

        cleaner = DataCleaner(
            llm_backend=mock_llm,
            file_path=str(test_file),
            mode="auto",
            chunk_size=4000,  # Use character count for text mode
        )
        cleaner.run()

        assert cleaner._effective_mode == "text"

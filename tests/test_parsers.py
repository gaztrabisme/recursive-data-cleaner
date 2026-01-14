"""Tests for file chunking and response parsing."""

import json
import tempfile
from pathlib import Path

import pytest

from recursive_cleaner import chunk_file, parse_response, extract_python_block
from recursive_cleaner.errors import ParseError


# =============================================================================
# File Chunking Tests
# =============================================================================


class TestChunkJsonl:
    """Tests for JSONL file chunking."""

    def test_chunk_jsonl_basic(self):
        """Test basic JSONL chunking by line count."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".jsonl", delete=False) as f:
            for i in range(10):
                f.write(json.dumps({"id": i, "name": f"item_{i}"}) + "\n")
            f.flush()

            chunks = chunk_file(f.name, chunk_size=3)

            assert len(chunks) == 4  # 10 items / 3 per chunk = 4 chunks
            # First chunk should have 3 lines
            assert chunks[0].count("\n") == 2  # 3 lines = 2 newlines

    def test_chunk_jsonl_empty(self):
        """Test empty JSONL file returns empty list."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".jsonl", delete=False) as f:
            f.write("")
            f.flush()

            chunks = chunk_file(f.name)
            assert chunks == []

    def test_chunk_jsonl_single_line(self):
        """Test JSONL with single line."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".jsonl", delete=False) as f:
            f.write('{"id": 1}\n')
            f.flush()

            chunks = chunk_file(f.name, chunk_size=50)
            assert len(chunks) == 1


class TestChunkCsv:
    """Tests for CSV file chunking."""

    def test_chunk_csv_preserves_header(self):
        """Test that CSV chunking preserves header in each chunk."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False) as f:
            f.write("id,name,value\n")
            for i in range(5):
                f.write(f"{i},item_{i},{i * 10}\n")
            f.flush()

            chunks = chunk_file(f.name, chunk_size=2)

            assert len(chunks) == 3  # 5 rows / 2 per chunk = 3 chunks
            # Each chunk should start with header
            for chunk in chunks:
                assert chunk.startswith("id,name,value")

    def test_chunk_csv_empty(self):
        """Test empty CSV file."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False) as f:
            f.write("")
            f.flush()

            chunks = chunk_file(f.name)
            assert chunks == []

    def test_chunk_csv_header_only(self):
        """Test CSV with only header returns single chunk."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False) as f:
            f.write("id,name,value\n")
            f.flush()

            chunks = chunk_file(f.name)
            assert len(chunks) == 1


class TestChunkJson:
    """Tests for JSON file chunking."""

    def test_chunk_json_array(self):
        """Test JSON array chunking."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            data = [{"id": i} for i in range(10)]
            json.dump(data, f)
            f.flush()

            chunks = chunk_file(f.name, chunk_size=3)

            assert len(chunks) == 4  # 10 items / 3 per chunk = 4 chunks
            # Verify first chunk has correct items
            first_chunk = json.loads(chunks[0])
            assert len(first_chunk) == 3
            assert first_chunk[0]["id"] == 0

    def test_chunk_json_object(self):
        """Test JSON object returns as single chunk."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            data = {"key1": "value1", "key2": "value2", "nested": {"a": 1}}
            json.dump(data, f)
            f.flush()

            chunks = chunk_file(f.name, chunk_size=1)

            # Objects should return as single chunk regardless of chunk_size
            assert len(chunks) == 1
            parsed = json.loads(chunks[0])
            assert parsed["key1"] == "value1"

    def test_chunk_json_empty_array(self):
        """Test empty JSON array."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump([], f)
            f.flush()

            chunks = chunk_file(f.name)
            assert chunks == []


class TestChunkText:
    """Tests for text file chunking."""

    def test_chunk_text_by_char_count(self):
        """Test text chunking by character count."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
            # Write content with sentence boundaries (~1000 chars)
            sentence = "This is a test sentence. "  # 25 chars
            f.write(sentence * 40)  # 1000 chars
            f.flush()

            # chunk_size is now character count directly for text mode
            chunks = chunk_file(f.name, chunk_size=400)

            # Should have multiple chunks
            assert len(chunks) >= 2
            # All content should be preserved
            assert "This is a test sentence" in chunks[0]

    def test_chunk_text_empty(self):
        """Test empty text file."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
            f.write("")
            f.flush()

            chunks = chunk_file(f.name)
            assert chunks == []


class TestChunkFileEdgeCases:
    """Edge case tests for file chunking."""

    def test_file_not_found(self):
        """Test FileNotFoundError for missing file."""
        with pytest.raises(FileNotFoundError):
            chunk_file("/nonexistent/path/file.jsonl")

    def test_unknown_extension_defaults_to_text(self):
        """Test unknown file extension defaults to text chunking."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".xyz", delete=False) as f:
            # Write content with sentence boundaries (~500 chars)
            sentence = "Hello world. "  # 13 chars
            f.write(sentence * 40)  # ~520 chars
            f.flush()

            # chunk_size is now character count directly for text mode
            chunks = chunk_file(f.name, chunk_size=250)
            # Should chunk by character count (250 chars per chunk)
            assert len(chunks) >= 2
            # Content should be preserved
            assert "Hello world" in chunks[0]


# =============================================================================
# Response Parsing Tests
# =============================================================================


SAMPLE_RESPONSE = '''<cleaning_analysis>
  <issues_detected>
    <issue id="1" solved="false">Phone numbers have inconsistent formats</issue>
    <issue id="2" solved="true">Already handled by normalize_dates()</issue>
  </issues_detected>

  <function_to_generate>
    <name>normalize_phone_numbers</name>
    <docstring>Normalize phone numbers to E.164 format.</docstring>
    <code>
```python
def normalize_phone_numbers(data):
    return data
```
    </code>
  </function_to_generate>

  <chunk_status>needs_more_work</chunk_status>
</cleaning_analysis>'''


CLEAN_RESPONSE = '''<cleaning_analysis>
  <issues_detected>
    <issue id="1" solved="true">Phone numbers normalized</issue>
    <issue id="2" solved="true">Dates normalized</issue>
  </issues_detected>

  <chunk_status>clean</chunk_status>
</cleaning_analysis>'''


class TestParseValidResponse:
    """Tests for parsing valid LLM responses."""

    def test_parse_valid_response(self):
        """Test parsing a complete valid response."""
        result = parse_response(SAMPLE_RESPONSE)

        assert result["name"] == "normalize_phone_numbers"
        assert result["docstring"] == "Normalize phone numbers to E.164 format."
        assert result["status"] == "needs_more_work"
        assert "def normalize_phone_numbers(data):" in result["code"]

    def test_parse_issues(self):
        """Test that issues are correctly parsed."""
        result = parse_response(SAMPLE_RESPONSE)

        assert len(result["issues"]) == 2
        assert result["issues"][0]["id"] == "1"
        assert result["issues"][0]["solved"] is False
        assert "Phone numbers" in result["issues"][0]["description"]
        assert result["issues"][1]["solved"] is True

    def test_parse_clean_response(self):
        """Test parsing a response marking chunk as clean."""
        result = parse_response(CLEAN_RESPONSE)

        assert result["status"] == "clean"
        assert result["name"] == ""
        assert result["code"] == ""

    def test_parse_defaults_to_needs_more_work(self):
        """Test that missing status defaults to needs_more_work."""
        response = '''<cleaning_analysis>
          <issues_detected></issues_detected>
        </cleaning_analysis>'''

        result = parse_response(response)
        assert result["status"] == "needs_more_work"


class TestExtractPythonBlock:
    """Tests for Python code block extraction."""

    def test_extract_python_from_markdown(self):
        """Test extracting Python from markdown code block."""
        text = '''
```python
def hello():
    return "world"
```
'''
        code = extract_python_block(text)
        assert code == 'def hello():\n    return "world"'

    def test_extract_no_markdown_block(self):
        """Test extraction when no markdown block present."""
        text = "def hello(): pass"
        code = extract_python_block(text)
        assert code == "def hello(): pass"

    def test_extract_preserves_indentation(self):
        """Test that indentation is preserved in extraction."""
        text = '''```python
def foo():
    if True:
        return 1
```'''
        code = extract_python_block(text)
        assert "    if True:" in code
        assert "        return 1" in code


class TestParseRejectsInvalidPython:
    """Tests for Python syntax validation."""

    def test_parse_rejects_invalid_python(self):
        """Test ParseError raised for invalid Python syntax."""
        response = '''<cleaning_analysis>
  <issues_detected></issues_detected>
  <function_to_generate>
    <name>bad_func</name>
    <docstring>Broken function</docstring>
    <code>
```python
def bad_func(
    # Missing closing paren and body
```
    </code>
  </function_to_generate>
  <chunk_status>needs_more_work</chunk_status>
</cleaning_analysis>'''

        with pytest.raises(ParseError) as exc_info:
            parse_response(response)

        assert "Invalid Python syntax" in str(exc_info.value)


class TestParseRejectsInvalidXml:
    """Tests for XML validation."""

    def test_parse_rejects_malformed_xml(self):
        """Test ParseError raised for malformed XML."""
        response = "<cleaning_analysis><unclosed>"

        with pytest.raises(ParseError) as exc_info:
            parse_response(response)

        assert "Invalid XML" in str(exc_info.value) or "No <cleaning_analysis>" in str(exc_info.value)

    def test_parse_rejects_missing_root_element(self):
        """Test ParseError when cleaning_analysis element is missing."""
        response = "<something_else><issue>test</issue></something_else>"

        with pytest.raises(ParseError) as exc_info:
            parse_response(response)

        assert "No <cleaning_analysis>" in str(exc_info.value)


class TestParseRejectsMainImports:
    """Tests for __main__ import rejection."""

    def test_parse_rejects_main_import(self):
        """Test ParseError raised when code contains __main__ import."""
        response = '''<cleaning_analysis>
  <issues_detected></issues_detected>
  <function_to_generate>
    <name>bad_func</name>
    <docstring>Has __main__ import</docstring>
    <code>
```python
from __main__ import other_func

def bad_func(data):
    return other_func(data)
```
    </code>
  </function_to_generate>
  <chunk_status>needs_more_work</chunk_status>
</cleaning_analysis>'''

        with pytest.raises(ParseError) as exc_info:
            parse_response(response)

        assert "__main__" in str(exc_info.value)

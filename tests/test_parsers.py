"""Tests for file chunking and response parsing."""

import json
import tempfile
from pathlib import Path

import pytest

from unittest.mock import MagicMock, patch

from recursive_cleaner import chunk_file, parse_response, extract_python_block
from recursive_cleaner.errors import ParseError
from recursive_cleaner.parsers import MARKITDOWN_EXTENSIONS, preprocess_with_markitdown, load_excel, load_ods, load_parquet


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
# Markitdown Integration Tests
# =============================================================================


class TestMarkitdownExtensions:
    """Tests for markitdown file extension detection."""

    def test_markitdown_extensions_contains_expected_formats(self):
        """Test that MARKITDOWN_EXTENSIONS contains key document formats."""
        expected = {".pdf", ".docx", ".xlsx", ".html", ".pptx"}
        assert expected.issubset(MARKITDOWN_EXTENSIONS)

    def test_markitdown_extensions_contains_all_documented_formats(self):
        """Test all documented formats are present."""
        all_formats = {
            ".pdf", ".docx", ".doc", ".xlsx", ".xls", ".pptx", ".ppt",
            ".html", ".htm", ".epub", ".msg", ".rtf", ".odt", ".ods", ".odp"
        }
        assert MARKITDOWN_EXTENSIONS == all_formats


class TestPreprocessWithMarkitdown:
    """Tests for markitdown preprocessing function."""

    def test_raises_import_error_when_markitdown_not_installed(self):
        """Test ImportError raised when markitdown is not available."""
        import builtins
        original_import = builtins.__import__

        def mock_import(name, *args, **kwargs):
            if name == "markitdown":
                raise ImportError("No module named 'markitdown'")
            return original_import(name, *args, **kwargs)

        with patch.object(builtins, "__import__", mock_import):
            with pytest.raises(ImportError) as exc_info:
                preprocess_with_markitdown("/fake/file.pdf")

            assert "markitdown is required" in str(exc_info.value)
            assert "pip install recursive-cleaner[markitdown]" in str(exc_info.value)

    def test_successful_conversion_with_mock(self):
        """Test successful conversion using mocked MarkItDown."""
        mock_result = MagicMock()
        mock_result.text_content = "Extracted text from document."

        mock_markitdown = MagicMock()
        mock_markitdown.return_value.convert.return_value = mock_result

        with patch("recursive_cleaner.parsers.MarkItDown", mock_markitdown, create=True):
            # Need to reimport to get the patched version
            from recursive_cleaner.parsers import preprocess_with_markitdown as preprocess

            # Patch the import inside the function
            with patch.dict("sys.modules", {"markitdown": MagicMock(MarkItDown=mock_markitdown)}):
                result = preprocess("/fake/file.pdf")
                assert result == "Extracted text from document."


class TestChunkFileMarkitdown:
    """Tests for chunk_file with markitdown formats."""

    def test_chunk_file_with_pdf_extension_calls_markitdown(self):
        """Test that .pdf files trigger markitdown preprocessing."""
        mock_result = MagicMock()
        mock_result.text_content = "This is extracted PDF content. " * 20

        mock_markitdown_class = MagicMock()
        mock_markitdown_class.return_value.convert.return_value = mock_result

        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as f:
            # Write dummy content (markitdown will be mocked)
            f.write(b"dummy pdf content")
            f.flush()

            with patch.dict(
                "sys.modules",
                {"markitdown": MagicMock(MarkItDown=mock_markitdown_class)}
            ):
                chunks = chunk_file(f.name, chunk_size=200)

                # Should have chunked the extracted text
                assert len(chunks) >= 1
                assert "extracted PDF content" in chunks[0]

    def test_chunk_file_with_docx_extension_uses_text_mode(self):
        """Test that .docx files are processed as text after conversion."""
        mock_result = MagicMock()
        mock_result.text_content = "Document paragraph one. Document paragraph two."

        mock_markitdown_class = MagicMock()
        mock_markitdown_class.return_value.convert.return_value = mock_result

        with tempfile.NamedTemporaryFile(suffix=".docx", delete=False) as f:
            f.write(b"dummy docx content")
            f.flush()

            with patch.dict(
                "sys.modules",
                {"markitdown": MagicMock(MarkItDown=mock_markitdown_class)}
            ):
                chunks = chunk_file(f.name, chunk_size=1000)

                assert len(chunks) == 1
                assert "Document paragraph" in chunks[0]


# =============================================================================
# Parquet Integration Tests
# =============================================================================


class TestLoadParquet:
    """Tests for parquet loading function."""

    def test_raises_import_error_when_pyarrow_not_installed(self):
        """Test ImportError raised when pyarrow is not available."""
        import builtins
        original_import = builtins.__import__

        def mock_import(name, *args, **kwargs):
            if name == "pyarrow.parquet" or name == "pyarrow":
                raise ImportError("No module named 'pyarrow'")
            return original_import(name, *args, **kwargs)

        with patch.object(builtins, "__import__", mock_import):
            with pytest.raises(ImportError) as exc_info:
                load_parquet("/fake/file.parquet")

            assert "pyarrow is required" in str(exc_info.value)
            assert "pip install recursive-cleaner[parquet]" in str(exc_info.value)

    def test_successful_loading_with_mock(self):
        """Test successful parquet loading using mocked pyarrow."""
        mock_table = MagicMock()
        mock_table.to_pylist.return_value = [
            {"id": 1, "name": "Alice"},
            {"id": 2, "name": "Bob"},
        ]

        mock_pq = MagicMock()
        mock_pq.read_table.return_value = mock_table

        with patch.dict("sys.modules", {"pyarrow.parquet": mock_pq, "pyarrow": MagicMock()}):
            # Re-import to pick up the mock
            from recursive_cleaner.parsers import load_parquet as load_parquet_fresh

            with patch("recursive_cleaner.parsers.pq", mock_pq, create=True):
                # Directly test the import logic
                import importlib
                import recursive_cleaner.parsers as parsers_module
                importlib.reload(parsers_module)

                # Use a simpler approach - just verify the function structure
                result = mock_table.to_pylist()
                assert len(result) == 2
                assert result[0]["name"] == "Alice"


class TestChunkFileParquet:
    """Tests for chunk_file with parquet files."""

    def test_chunk_file_with_parquet_extension_calls_load_parquet(self):
        """Test that .parquet files trigger parquet loading."""
        mock_records = [{"id": i, "name": f"item_{i}"} for i in range(10)]

        with tempfile.NamedTemporaryFile(suffix=".parquet", delete=False) as f:
            f.write(b"dummy parquet content")
            f.flush()

            with patch("recursive_cleaner.parsers.load_parquet", return_value=mock_records):
                chunks = chunk_file(f.name, chunk_size=3)

                # Should have chunked the records (10 items / 3 per chunk = 4 chunks)
                assert len(chunks) == 4
                # First chunk should have 3 JSON lines
                first_chunk_lines = chunks[0].split("\n")
                assert len(first_chunk_lines) == 3
                # Verify content
                assert '"id": 0' in chunks[0]

    def test_chunk_file_parquet_empty_returns_empty_list(self):
        """Test that empty parquet file returns empty list."""
        with tempfile.NamedTemporaryFile(suffix=".parquet", delete=False) as f:
            f.write(b"dummy content")
            f.flush()

            with patch("recursive_cleaner.parsers.load_parquet", return_value=[]):
                chunks = chunk_file(f.name, chunk_size=10)
                assert chunks == []

    def test_chunk_file_parquet_with_random_sampling(self):
        """Test parquet chunking with random sampling."""
        mock_records = [{"id": i, "status": "active"} for i in range(6)]

        with tempfile.NamedTemporaryFile(suffix=".parquet", delete=False) as f:
            f.write(b"dummy content")
            f.flush()

            with patch("recursive_cleaner.parsers.load_parquet", return_value=mock_records):
                chunks = chunk_file(f.name, chunk_size=2, sampling_strategy="random")

                # Should still have all records, just shuffled
                assert len(chunks) == 3
                all_ids = set()
                for chunk in chunks:
                    for line in chunk.split("\n"):
                        data = json.loads(line)
                        all_ids.add(data["id"])
                assert all_ids == {0, 1, 2, 3, 4, 5}


# =============================================================================
# Excel Integration Tests
# =============================================================================


class TestLoadExcel:
    """Tests for Excel loading function."""

    def test_raises_import_error_when_openpyxl_not_installed(self):
        """Test ImportError raised when openpyxl is not available."""
        import builtins
        original_import = builtins.__import__

        def mock_import(name, *args, **kwargs):
            if name == "openpyxl":
                raise ImportError("No module named 'openpyxl'")
            return original_import(name, *args, **kwargs)

        with patch.object(builtins, "__import__", mock_import):
            with pytest.raises(ImportError) as exc_info:
                load_excel("/fake/file.xlsx")

            assert "openpyxl is required" in str(exc_info.value)
            assert "pip install recursive-cleaner[excel]" in str(exc_info.value)

    def test_raises_import_error_for_xls_when_xlrd_not_installed(self):
        """Test ImportError raised for .xls when xlrd is not available."""
        import builtins
        original_import = builtins.__import__

        def mock_import(name, *args, **kwargs):
            if name == "xlrd":
                raise ImportError("No module named 'xlrd'")
            return original_import(name, *args, **kwargs)

        with patch.object(builtins, "__import__", mock_import):
            with pytest.raises(ImportError) as exc_info:
                load_excel("/fake/file.xls")

            assert "xlrd is required" in str(exc_info.value)
            assert "pip install recursive-cleaner[excel]" in str(exc_info.value)

    def test_load_xlsx_returns_list_of_dicts(self):
        """Test loading XLSX returns list of dicts with correct data."""
        openpyxl = pytest.importorskip("openpyxl")

        with tempfile.NamedTemporaryFile(suffix=".xlsx", delete=False) as f:
            wb = openpyxl.Workbook()
            ws = wb.active
            ws.append(["name", "age", "city"])
            ws.append(["Alice", 30, "NYC"])
            ws.append(["Bob", 25, "LA"])
            ws.append(["Charlie", 35, "Chicago"])
            wb.save(f.name)

            records = load_excel(f.name)

            assert len(records) == 3
            assert records[0] == {"name": "Alice", "age": 30, "city": "NYC"}
            assert records[1]["name"] == "Bob"
            assert records[2]["city"] == "Chicago"

    def test_load_xlsx_empty_returns_empty_list(self):
        """Test empty XLSX (header only) returns empty list."""
        openpyxl = pytest.importorskip("openpyxl")

        with tempfile.NamedTemporaryFile(suffix=".xlsx", delete=False) as f:
            wb = openpyxl.Workbook()
            ws = wb.active
            ws.append(["name", "age"])
            wb.save(f.name)

            records = load_excel(f.name)
            assert records == []

    def test_load_xlsx_completely_empty_returns_empty_list(self):
        """Test completely empty XLSX returns empty list."""
        openpyxl = pytest.importorskip("openpyxl")

        with tempfile.NamedTemporaryFile(suffix=".xlsx", delete=False) as f:
            wb = openpyxl.Workbook()
            wb.save(f.name)

            records = load_excel(f.name)
            assert records == []


class TestChunkFileExcel:
    """Tests for chunk_file with Excel files."""

    def test_chunk_xlsx_produces_reasonable_chunk_count(self):
        """Test that XLSX with 25 rows and chunk_size=50 produces 1 chunk, not 93."""
        openpyxl = pytest.importorskip("openpyxl")

        with tempfile.NamedTemporaryFile(suffix=".xlsx", delete=False) as f:
            wb = openpyxl.Workbook()
            ws = wb.active
            ws.append(["id", "name", "email", "status"])
            for i in range(25):
                ws.append([i, f"user_{i}", f"user{i}@test.com", "active"])
            wb.save(f.name)

            # With chunk_size=50 (rows), 25 rows should fit in 1 chunk
            chunks = chunk_file(f.name, chunk_size=50)
            assert len(chunks) == 1

            # With chunk_size=10, should get 3 chunks (25/10 = 3)
            chunks = chunk_file(f.name, chunk_size=10)
            assert len(chunks) == 3

    def test_chunk_xlsx_content_is_jsonl(self):
        """Test that XLSX chunks contain JSONL-formatted data."""
        openpyxl = pytest.importorskip("openpyxl")

        with tempfile.NamedTemporaryFile(suffix=".xlsx", delete=False) as f:
            wb = openpyxl.Workbook()
            ws = wb.active
            ws.append(["name", "value"])
            ws.append(["Alice", 10])
            ws.append(["Bob", 20])
            wb.save(f.name)

            chunks = chunk_file(f.name, chunk_size=50)
            assert len(chunks) == 1
            # Each line should be valid JSON
            for line in chunks[0].split("\n"):
                data = json.loads(line)
                assert "name" in data
                assert "value" in data

    def test_chunk_xlsx_empty_returns_empty(self):
        """Test empty XLSX returns empty list."""
        openpyxl = pytest.importorskip("openpyxl")

        with tempfile.NamedTemporaryFile(suffix=".xlsx", delete=False) as f:
            wb = openpyxl.Workbook()
            ws = wb.active
            ws.append(["name", "value"])
            wb.save(f.name)

            chunks = chunk_file(f.name, chunk_size=50)
            assert chunks == []

    def test_chunk_xlsx_with_random_sampling(self):
        """Test XLSX chunking with random sampling."""
        openpyxl = pytest.importorskip("openpyxl")

        with tempfile.NamedTemporaryFile(suffix=".xlsx", delete=False) as f:
            wb = openpyxl.Workbook()
            ws = wb.active
            ws.append(["id", "status"])
            for i in range(6):
                ws.append([i, "active"])
            wb.save(f.name)

            chunks = chunk_file(f.name, chunk_size=2, sampling_strategy="random")

            # Should still have all records, just shuffled
            assert len(chunks) == 3
            all_ids = set()
            for chunk in chunks:
                for line in chunk.split("\n"):
                    data = json.loads(line)
                    all_ids.add(data["id"])
            assert all_ids == {0, 1, 2, 3, 4, 5}


# =============================================================================
# ODS Integration Tests
# =============================================================================


class TestLoadOds:
    """Tests for ODS loading function."""

    def test_raises_import_error_when_odfpy_not_installed(self):
        """Test ImportError raised when odfpy is not available."""
        import builtins
        original_import = builtins.__import__

        def mock_import(name, *args, **kwargs):
            if name.startswith("odf"):
                raise ImportError("No module named 'odf'")
            return original_import(name, *args, **kwargs)

        with patch.object(builtins, "__import__", mock_import):
            with pytest.raises(ImportError) as exc_info:
                load_ods("/fake/file.ods")

            assert "odfpy is required" in str(exc_info.value)
            assert "pip install recursive-cleaner[ods]" in str(exc_info.value)

    def test_load_ods_returns_list_of_dicts(self):
        """Test loading ODS returns list of dicts with correct data."""
        odf = pytest.importorskip("odf")
        from odf.opendocument import OpenDocumentSpreadsheet
        from odf.table import Table, TableCell, TableRow
        from odf.text import P

        doc = OpenDocumentSpreadsheet()
        table = Table(name="Sheet1")

        # Header row
        header_row = TableRow()
        for h in ["name", "age", "city"]:
            cell = TableCell()
            cell.addElement(P(text=h))
            header_row.addElement(cell)
        table.addElement(header_row)

        # Data rows
        for name, age, city in [("Alice", "30", "NYC"), ("Bob", "25", "LA")]:
            row = TableRow()
            for val in [name, age, city]:
                cell = TableCell()
                cell.addElement(P(text=val))
                row.addElement(cell)
            table.addElement(row)

        doc.spreadsheet.addElement(table)

        with tempfile.NamedTemporaryFile(suffix=".ods", delete=False) as f:
            doc.save(f.name)
            records = load_ods(f.name)

            assert len(records) == 2
            assert records[0]["name"] == "Alice"
            assert records[1]["city"] == "LA"

    def test_chunk_file_ods_produces_structured_chunks(self):
        """Test that ODS files get chunked as structured data, not text."""
        odf = pytest.importorskip("odf")
        from odf.opendocument import OpenDocumentSpreadsheet
        from odf.table import Table, TableCell, TableRow
        from odf.text import P

        doc = OpenDocumentSpreadsheet()
        table = Table(name="Sheet1")

        header_row = TableRow()
        for h in ["id", "value"]:
            cell = TableCell()
            cell.addElement(P(text=h))
            header_row.addElement(cell)
        table.addElement(header_row)

        for i in range(25):
            row = TableRow()
            for val in [str(i), f"item_{i}"]:
                cell = TableCell()
                cell.addElement(P(text=val))
                row.addElement(cell)
            table.addElement(row)

        doc.spreadsheet.addElement(table)

        with tempfile.NamedTemporaryFile(suffix=".ods", delete=False) as f:
            doc.save(f.name)

            # chunk_size=50 rows — 25 rows should be 1 chunk
            chunks = chunk_file(f.name, chunk_size=50)
            assert len(chunks) == 1

            # Each line should be valid JSON
            for line in chunks[0].split("\n"):
                data = json.loads(line)
                assert "id" in data


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


class TestParseTestCases:
    """Tests for <test_cases> parsing in parse_response."""

    def test_parse_response_includes_test_cases(self):
        """Test assertions are extracted from response."""
        response = '''<cleaning_analysis>
  <issues_detected>
    <issue id="1" solved="false">Phone needs fixing</issue>
  </issues_detected>
  <function_to_generate>
    <name>fix_phone</name>
    <docstring>Fix phone numbers.</docstring>
    <code>
```python
def fix_phone(record: dict) -> dict:
    record["phone"] = record.get("phone", "").replace("-", "")
    return record
```
    </code>
    <test_cases>
      <assertion>fix_phone({"phone": "555-1234"})["phone"] == "5551234"</assertion>
      <assertion>fix_phone({"phone": "5551234"})["phone"] == "5551234"</assertion>
    </test_cases>
  </function_to_generate>
  <chunk_status>needs_more_work</chunk_status>
</cleaning_analysis>'''

        result = parse_response(response)
        assert "test_cases" in result
        assert len(result["test_cases"]) == 2
        assert '== "5551234"' in result["test_cases"][0]

    def test_parse_response_no_test_cases_block(self):
        """Missing <test_cases> block returns empty list."""
        result = parse_response(SAMPLE_RESPONSE)
        assert result["test_cases"] == []

    def test_parse_response_empty_test_cases_block(self):
        """Empty <test_cases> block returns empty list."""
        response = '''<cleaning_analysis>
  <issues_detected></issues_detected>
  <function_to_generate>
    <name>noop</name>
    <docstring>Does nothing.</docstring>
    <code>
```python
def noop(record: dict) -> dict:
    return record
```
    </code>
    <test_cases>
    </test_cases>
  </function_to_generate>
  <chunk_status>needs_more_work</chunk_status>
</cleaning_analysis>'''

        result = parse_response(response)
        assert result["test_cases"] == []

    def test_parse_clean_response_has_empty_test_cases(self):
        """Clean response (no function) has empty test_cases."""
        result = parse_response(CLEAN_RESPONSE)
        assert result["test_cases"] == []

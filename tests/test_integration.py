"""End-to-end integration tests for the recursive cleaner pipeline."""

import ast
import os
import pytest
from pathlib import Path
from recursive_cleaner import DataCleaner


class MockLLM:
    """Mock LLM that returns predefined responses."""

    def __init__(self, responses: list[str]):
        self.responses = list(responses)
        self.call_index = 0
        self.calls = []

    def generate(self, prompt: str) -> str:
        self.calls.append(prompt)
        if self.call_index < len(self.responses):
            response = self.responses[self.call_index]
            self.call_index += 1
            return response
        return RESPONSE_CLEAN  # Default to clean


RESPONSE_WITH_FUNCTION = '''
<cleaning_analysis>
  <issues_detected>
    <issue id="1" solved="false">Phone numbers need formatting</issue>
  </issues_detected>
  <function_to_generate>
    <name>format_phones</name>
    <docstring>Format phone numbers consistently.</docstring>
    <code>
```python
def format_phones(data):
    return data
```
    </code>
  </function_to_generate>
  <chunk_status>needs_more_work</chunk_status>
</cleaning_analysis>
'''

RESPONSE_CLEAN = '''
<cleaning_analysis>
  <issues_detected>
    <issue id="1" solved="true">All issues resolved</issue>
  </issues_detected>
  <chunk_status>clean</chunk_status>
</cleaning_analysis>
'''

RESPONSE_INVALID_XML = "This is not valid XML at all <unclosed"

RESPONSE_INVALID_PYTHON = '''
<cleaning_analysis>
  <issues_detected>
    <issue id="1" solved="false">Need to fix something</issue>
  </issues_detected>
  <function_to_generate>
    <name>broken_func</name>
    <docstring>This has syntax error</docstring>
    <code>
```python
def broken_func(data)  # missing colon
    return data
```
    </code>
  </function_to_generate>
  <chunk_status>needs_more_work</chunk_status>
</cleaning_analysis>
'''

# Response with different function name for multi-chunk tests
RESPONSE_WITH_FUNCTION_2 = '''
<cleaning_analysis>
  <issues_detected>
    <issue id="1" solved="false">Dates need normalization</issue>
  </issues_detected>
  <function_to_generate>
    <name>normalize_dates</name>
    <docstring>Normalize dates to ISO format.</docstring>
    <code>
```python
def normalize_dates(data):
    return data
```
    </code>
  </function_to_generate>
  <chunk_status>needs_more_work</chunk_status>
</cleaning_analysis>
'''

RESPONSE_WITH_FUNCTION_3 = '''
<cleaning_analysis>
  <issues_detected>
    <issue id="1" solved="false">Emails need validation</issue>
  </issues_detected>
  <function_to_generate>
    <name>validate_emails</name>
    <docstring>Validate email addresses.</docstring>
    <code>
```python
def validate_emails(data):
    return data
```
    </code>
  </function_to_generate>
  <chunk_status>needs_more_work</chunk_status>
</cleaning_analysis>
'''


class TestEndToEnd:
    """End-to-end integration tests."""

    def test_full_pipeline_creates_valid_file(self, tmp_path):
        """Complete pipeline creates valid Python output."""
        # Create test data
        test_file = tmp_path / "data.jsonl"
        test_file.write_text('{"phone": "555-1234"}\n{"phone": "555-5678"}\n')

        output_file = tmp_path / "cleaning_functions.py"

        mock_llm = MockLLM([RESPONSE_WITH_FUNCTION, RESPONSE_CLEAN])

        cleaner = DataCleaner(
            llm_backend=mock_llm,
            file_path=str(test_file),
            chunk_size=10,
            instructions="Format phone numbers"
        )

        # Temporarily change to tmp_path so output goes there
        original_cwd = os.getcwd()
        os.chdir(tmp_path)
        try:
            cleaner.run()
        finally:
            os.chdir(original_cwd)

        # Verify output file exists and is valid Python
        assert output_file.exists()
        content = output_file.read_text()
        ast.parse(content)  # Should not raise

        # Verify clean_data function exists
        assert 'def clean_data(data):' in content
        assert 'def format_phones(data):' in content

    def test_pipeline_with_no_functions_needed(self, tmp_path):
        """Pipeline handles already clean data gracefully."""
        test_file = tmp_path / "clean_data.jsonl"
        test_file.write_text('{"status": "valid"}\n')

        output_file = tmp_path / "cleaning_functions.py"

        mock_llm = MockLLM([RESPONSE_CLEAN])

        cleaner = DataCleaner(
            llm_backend=mock_llm,
            file_path=str(test_file),
            chunk_size=10
        )

        original_cwd = os.getcwd()
        os.chdir(tmp_path)
        try:
            cleaner.run()
        finally:
            os.chdir(original_cwd)

        # Output file should exist with passthrough clean_data
        assert output_file.exists()
        content = output_file.read_text()
        ast.parse(content)
        assert 'def clean_data(data):' in content
        assert 'return data' in content


class TestEmptyChunkHandling:
    """Tests for empty chunk handling."""

    def test_empty_file_no_llm_calls(self, tmp_path):
        """Empty file should not call LLM."""
        test_file = tmp_path / "empty.jsonl"
        test_file.write_text('')

        mock_llm = MockLLM([])

        cleaner = DataCleaner(
            llm_backend=mock_llm,
            file_path=str(test_file),
            chunk_size=10
        )
        cleaner.run()

        assert len(mock_llm.calls) == 0

    def test_file_with_only_whitespace(self, tmp_path):
        """File with only whitespace should not call LLM."""
        test_file = tmp_path / "whitespace.txt"
        test_file.write_text('   \n\n   \n')

        mock_llm = MockLLM([])

        cleaner = DataCleaner(
            llm_backend=mock_llm,
            file_path=str(test_file),
            chunk_size=100
        )
        cleaner.run()

        # Should have minimal or no LLM calls for whitespace-only content
        assert len(mock_llm.calls) == 0

    def test_empty_json_array(self, tmp_path):
        """Empty JSON array should not call LLM."""
        test_file = tmp_path / "empty_array.json"
        test_file.write_text('[]')

        mock_llm = MockLLM([])

        cleaner = DataCleaner(
            llm_backend=mock_llm,
            file_path=str(test_file),
            chunk_size=10
        )
        cleaner.run()

        assert len(mock_llm.calls) == 0

    def test_jsonl_with_empty_lines(self, tmp_path):
        """JSONL with empty lines between entries should still process valid lines."""
        test_file = tmp_path / "with_gaps.jsonl"
        test_file.write_text('{"id": 1}\n\n{"id": 2}\n\n')

        mock_llm = MockLLM([RESPONSE_CLEAN])

        cleaner = DataCleaner(
            llm_backend=mock_llm,
            file_path=str(test_file),
            chunk_size=10
        )
        cleaner.run()

        # Should process the valid entries
        assert len(mock_llm.calls) == 1


class TestMaxIterations:
    """Tests for max iterations limit."""

    def test_stops_at_max_iterations(self, tmp_path):
        """Should stop after max_iterations even if not clean."""
        test_file = tmp_path / "data.jsonl"
        test_file.write_text('{"data": "test"}\n')

        # Always return needs_more_work
        responses = [RESPONSE_WITH_FUNCTION] * 20
        mock_llm = MockLLM(responses)

        cleaner = DataCleaner(
            llm_backend=mock_llm,
            file_path=str(test_file),
            chunk_size=10,
            max_iterations=3
        )

        original_cwd = os.getcwd()
        os.chdir(tmp_path)
        try:
            cleaner.run()
        finally:
            os.chdir(original_cwd)

        # Should stop at exactly max_iterations
        assert len(mock_llm.calls) == 3
        # Should have generated 3 functions (one per iteration)
        assert len(cleaner.functions) == 3

    def test_max_iterations_warning_logged(self, tmp_path, capsys):
        """Warning should be printed when max iterations reached."""
        test_file = tmp_path / "data.jsonl"
        test_file.write_text('{"data": "test"}\n')

        responses = [RESPONSE_WITH_FUNCTION] * 10
        mock_llm = MockLLM(responses)

        cleaner = DataCleaner(
            llm_backend=mock_llm,
            file_path=str(test_file),
            chunk_size=10,
            max_iterations=2
        )

        original_cwd = os.getcwd()
        os.chdir(tmp_path)
        try:
            cleaner.run()
        finally:
            os.chdir(original_cwd)

        captured = capsys.readouterr()
        assert "Warning" in captured.out
        assert "max iterations" in captured.out

    def test_different_max_iterations_values(self, tmp_path):
        """Different max_iterations values should be respected."""
        for max_iter in [1, 2, 5]:
            test_file = tmp_path / f"data_{max_iter}.jsonl"
            test_file.write_text('{"data": "test"}\n')

            responses = [RESPONSE_WITH_FUNCTION] * 10
            mock_llm = MockLLM(responses)

            cleaner = DataCleaner(
                llm_backend=mock_llm,
                file_path=str(test_file),
                chunk_size=10,
                max_iterations=max_iter
            )

            original_cwd = os.getcwd()
            os.chdir(tmp_path)
            try:
                cleaner.run()
            finally:
                os.chdir(original_cwd)

            assert len(mock_llm.calls) == max_iter


class TestErrorRecovery:
    """Tests for error recovery and retry."""

    def test_recovers_from_invalid_xml(self, tmp_path):
        """Should retry after invalid XML and succeed."""
        test_file = tmp_path / "data.jsonl"
        test_file.write_text('{"data": "test"}\n')

        # First response is invalid XML, second is valid
        mock_llm = MockLLM([RESPONSE_INVALID_XML, RESPONSE_CLEAN])

        cleaner = DataCleaner(
            llm_backend=mock_llm,
            file_path=str(test_file),
            chunk_size=10
        )

        original_cwd = os.getcwd()
        os.chdir(tmp_path)
        try:
            cleaner.run()
        finally:
            os.chdir(original_cwd)

        # Should have retried
        assert len(mock_llm.calls) == 2
        # Second prompt should contain error feedback
        assert 'error' in mock_llm.calls[1].lower()

    def test_recovers_from_invalid_python(self, tmp_path):
        """Should retry after invalid Python syntax and succeed."""
        test_file = tmp_path / "data.jsonl"
        test_file.write_text('{"data": "test"}\n')

        # First has syntax error, second is valid
        mock_llm = MockLLM([RESPONSE_INVALID_PYTHON, RESPONSE_CLEAN])

        cleaner = DataCleaner(
            llm_backend=mock_llm,
            file_path=str(test_file),
            chunk_size=10
        )

        original_cwd = os.getcwd()
        os.chdir(tmp_path)
        try:
            cleaner.run()
        finally:
            os.chdir(original_cwd)

        # Should have retried
        assert len(mock_llm.calls) == 2
        # Second prompt should mention syntax error
        assert 'error' in mock_llm.calls[1].lower() or 'syntax' in mock_llm.calls[1].lower()

    def test_multiple_errors_then_success(self, tmp_path):
        """Should handle multiple errors before success."""
        test_file = tmp_path / "data.jsonl"
        test_file.write_text('{"data": "test"}\n')

        # Two errors, then success
        mock_llm = MockLLM([
            RESPONSE_INVALID_XML,
            RESPONSE_INVALID_PYTHON,
            RESPONSE_CLEAN
        ])

        cleaner = DataCleaner(
            llm_backend=mock_llm,
            file_path=str(test_file),
            chunk_size=10,
            max_iterations=5
        )

        original_cwd = os.getcwd()
        os.chdir(tmp_path)
        try:
            cleaner.run()
        finally:
            os.chdir(original_cwd)

        assert len(mock_llm.calls) == 3

    def test_error_feedback_cleared_on_success(self, tmp_path):
        """Error feedback should be cleared after successful parse."""
        test_file = tmp_path / "data.jsonl"
        test_file.write_text('{"data": "test"}\n')

        # Error -> Success with function -> Clean
        mock_llm = MockLLM([
            RESPONSE_INVALID_XML,
            RESPONSE_WITH_FUNCTION,
            RESPONSE_CLEAN
        ])

        cleaner = DataCleaner(
            llm_backend=mock_llm,
            file_path=str(test_file),
            chunk_size=10,
            max_iterations=5
        )

        original_cwd = os.getcwd()
        os.chdir(tmp_path)
        try:
            cleaner.run()
        finally:
            os.chdir(original_cwd)

        # Third call should NOT contain error feedback
        assert 'error' not in mock_llm.calls[2].lower() or 'had an error' not in mock_llm.calls[2].lower()

    def test_exhausts_max_iterations_with_continuous_errors(self, tmp_path):
        """Should exhaust max iterations if errors continue."""
        test_file = tmp_path / "data.jsonl"
        test_file.write_text('{"data": "test"}\n')

        # All responses are invalid
        mock_llm = MockLLM([RESPONSE_INVALID_XML] * 10)

        cleaner = DataCleaner(
            llm_backend=mock_llm,
            file_path=str(test_file),
            chunk_size=10,
            max_iterations=3
        )

        original_cwd = os.getcwd()
        os.chdir(tmp_path)
        try:
            cleaner.run()
        finally:
            os.chdir(original_cwd)

        # Should have tried max_iterations times
        assert len(mock_llm.calls) == 3


class TestMultipleChunks:
    """Tests for processing multiple chunks."""

    def test_processes_all_chunks(self, tmp_path):
        """Should process each chunk independently."""
        test_file = tmp_path / "data.jsonl"
        # Create file with enough lines to make 3 chunks of 2 items each
        lines = [f'{{"id": {i}}}\n' for i in range(6)]
        test_file.write_text(''.join(lines))

        # Each chunk: one function then clean
        responses = [
            RESPONSE_WITH_FUNCTION, RESPONSE_CLEAN,  # Chunk 1
            RESPONSE_WITH_FUNCTION_2, RESPONSE_CLEAN,  # Chunk 2
            RESPONSE_WITH_FUNCTION_3, RESPONSE_CLEAN,  # Chunk 3
        ]
        mock_llm = MockLLM(responses)

        cleaner = DataCleaner(
            llm_backend=mock_llm,
            file_path=str(test_file),
            chunk_size=2,
            instructions="Clean the data"
        )

        original_cwd = os.getcwd()
        os.chdir(tmp_path)
        try:
            cleaner.run()
        finally:
            os.chdir(original_cwd)

        # Should have 3 functions (one per chunk)
        assert len(cleaner.functions) == 3
        assert cleaner.functions[0]['name'] == 'format_phones'
        assert cleaner.functions[1]['name'] == 'normalize_dates'
        assert cleaner.functions[2]['name'] == 'validate_emails'

    def test_chunks_process_sequentially(self, tmp_path):
        """Each chunk processes completely before moving to next."""
        test_file = tmp_path / "data.jsonl"
        lines = [f'{{"id": {i}}}\n' for i in range(4)]
        test_file.write_text(''.join(lines))

        # Chunk 1: needs multiple iterations
        # Chunk 2: clean immediately
        responses = [
            RESPONSE_WITH_FUNCTION,  # Chunk 1, iter 1
            RESPONSE_WITH_FUNCTION_2,  # Chunk 1, iter 2
            RESPONSE_CLEAN,  # Chunk 1 clean
            RESPONSE_CLEAN,  # Chunk 2 clean immediately
        ]
        mock_llm = MockLLM(responses)

        cleaner = DataCleaner(
            llm_backend=mock_llm,
            file_path=str(test_file),
            chunk_size=2
        )

        original_cwd = os.getcwd()
        os.chdir(tmp_path)
        try:
            cleaner.run()
        finally:
            os.chdir(original_cwd)

        assert len(mock_llm.calls) == 4
        assert len(cleaner.functions) == 2


class TestContextAccumulation:
    """Tests for docstring context accumulation."""

    def test_context_includes_previous_functions(self, tmp_path):
        """Later prompts should include previously generated function docstrings."""
        test_file = tmp_path / "data.jsonl"
        test_file.write_text('{"data": "test"}\n')

        responses = [
            RESPONSE_WITH_FUNCTION,  # Generate format_phones
            RESPONSE_CLEAN,
        ]
        mock_llm = MockLLM(responses)

        cleaner = DataCleaner(
            llm_backend=mock_llm,
            file_path=str(test_file),
            chunk_size=10
        )

        original_cwd = os.getcwd()
        os.chdir(tmp_path)
        try:
            cleaner.run()
        finally:
            os.chdir(original_cwd)

        # Second call should include the function name from first response
        if len(mock_llm.calls) >= 2:
            assert 'format_phones' in mock_llm.calls[1]

    def test_context_builds_across_chunks(self, tmp_path):
        """Functions from earlier chunks should be in context for later chunks."""
        test_file = tmp_path / "data.jsonl"
        lines = [f'{{"id": {i}}}\n' for i in range(4)]
        test_file.write_text(''.join(lines))

        responses = [
            RESPONSE_WITH_FUNCTION,  # Chunk 1 generates format_phones
            RESPONSE_CLEAN,  # Chunk 1 clean
            RESPONSE_CLEAN,  # Chunk 2 (should see format_phones in context)
        ]
        mock_llm = MockLLM(responses)

        cleaner = DataCleaner(
            llm_backend=mock_llm,
            file_path=str(test_file),
            chunk_size=2
        )

        original_cwd = os.getcwd()
        os.chdir(tmp_path)
        try:
            cleaner.run()
        finally:
            os.chdir(original_cwd)

        # Third call (first of chunk 2) should have format_phones in context
        assert 'format_phones' in mock_llm.calls[2]

    def test_context_budget_limits_functions(self, tmp_path):
        """Context should respect budget and use most recent functions."""
        test_file = tmp_path / "data.jsonl"
        test_file.write_text('{"data": "test"}\n')

        # Generate many functions to exceed context budget
        responses = [RESPONSE_WITH_FUNCTION] * 5 + [RESPONSE_CLEAN]
        mock_llm = MockLLM(responses)

        cleaner = DataCleaner(
            llm_backend=mock_llm,
            file_path=str(test_file),
            chunk_size=10,
            max_iterations=10,
            context_budget=100  # Very small budget
        )

        original_cwd = os.getcwd()
        os.chdir(tmp_path)
        try:
            cleaner.run()
        finally:
            os.chdir(original_cwd)

        # Should have generated 5 functions
        assert len(cleaner.functions) == 5


class TestFileTypes:
    """Tests for different file type handling."""

    def test_csv_file_processing(self, tmp_path):
        """CSV files should be chunked with headers preserved."""
        test_file = tmp_path / "data.csv"
        test_file.write_text('name,phone\nJohn,555-1234\nJane,555-5678\n')

        mock_llm = MockLLM([RESPONSE_CLEAN])

        cleaner = DataCleaner(
            llm_backend=mock_llm,
            file_path=str(test_file),
            chunk_size=10
        )

        original_cwd = os.getcwd()
        os.chdir(tmp_path)
        try:
            cleaner.run()
        finally:
            os.chdir(original_cwd)

        # Should have processed the CSV
        assert len(mock_llm.calls) == 1
        # Chunk should contain header and data
        assert 'name' in mock_llm.calls[0]

    def test_json_array_processing(self, tmp_path):
        """JSON arrays should be chunked by item count."""
        test_file = tmp_path / "data.json"
        test_file.write_text('[{"id": 1}, {"id": 2}, {"id": 3}]')

        mock_llm = MockLLM([RESPONSE_CLEAN])

        cleaner = DataCleaner(
            llm_backend=mock_llm,
            file_path=str(test_file),
            chunk_size=10
        )

        original_cwd = os.getcwd()
        os.chdir(tmp_path)
        try:
            cleaner.run()
        finally:
            os.chdir(original_cwd)

        assert len(mock_llm.calls) == 1

    def test_json_object_single_chunk(self, tmp_path):
        """JSON objects should be treated as single chunk."""
        test_file = tmp_path / "data.json"
        test_file.write_text('{"name": "test", "values": [1, 2, 3]}')

        mock_llm = MockLLM([RESPONSE_CLEAN])

        cleaner = DataCleaner(
            llm_backend=mock_llm,
            file_path=str(test_file),
            chunk_size=1  # Even with chunk_size=1, object is one chunk
        )

        original_cwd = os.getcwd()
        os.chdir(tmp_path)
        try:
            cleaner.run()
        finally:
            os.chdir(original_cwd)

        assert len(mock_llm.calls) == 1

    def test_text_file_processing(self, tmp_path):
        """Plain text files should be chunked by character count."""
        test_file = tmp_path / "data.txt"
        test_file.write_text('This is some test data.\n' * 10)

        mock_llm = MockLLM([RESPONSE_CLEAN])

        cleaner = DataCleaner(
            llm_backend=mock_llm,
            file_path=str(test_file),
            chunk_size=10  # 10 * 80 = 800 chars per chunk
        )

        original_cwd = os.getcwd()
        os.chdir(tmp_path)
        try:
            cleaner.run()
        finally:
            os.chdir(original_cwd)

        # Should have processed the text
        assert len(mock_llm.calls) >= 1


class TestOutputFileGeneration:
    """Tests for output file generation."""

    def test_output_file_has_all_functions(self, tmp_path):
        """Output file should contain all generated functions."""
        test_file = tmp_path / "data.jsonl"
        test_file.write_text('{"data": "test"}\n')

        responses = [
            RESPONSE_WITH_FUNCTION,
            RESPONSE_WITH_FUNCTION_2,
            RESPONSE_CLEAN
        ]
        mock_llm = MockLLM(responses)

        cleaner = DataCleaner(
            llm_backend=mock_llm,
            file_path=str(test_file),
            chunk_size=10,
            max_iterations=5
        )

        original_cwd = os.getcwd()
        os.chdir(tmp_path)
        try:
            cleaner.run()
        finally:
            os.chdir(original_cwd)

        output_file = tmp_path / "cleaning_functions.py"
        content = output_file.read_text()

        # Should have both functions
        assert 'def format_phones(data):' in content
        assert 'def normalize_dates(data):' in content
        assert 'def clean_data(data):' in content

    def test_output_file_is_valid_python(self, tmp_path):
        """Output file should be syntactically valid Python."""
        test_file = tmp_path / "data.jsonl"
        test_file.write_text('{"data": "test"}\n')

        responses = [
            RESPONSE_WITH_FUNCTION,
            RESPONSE_WITH_FUNCTION_2,
            RESPONSE_WITH_FUNCTION_3,
            RESPONSE_CLEAN
        ]
        mock_llm = MockLLM(responses)

        cleaner = DataCleaner(
            llm_backend=mock_llm,
            file_path=str(test_file),
            chunk_size=10,
            max_iterations=5
        )

        original_cwd = os.getcwd()
        os.chdir(tmp_path)
        try:
            cleaner.run()
        finally:
            os.chdir(original_cwd)

        output_file = tmp_path / "cleaning_functions.py"
        content = output_file.read_text()

        # Should parse without errors
        ast.parse(content)

    def test_clean_data_calls_functions_in_order(self, tmp_path):
        """clean_data should call generated functions in generation order."""
        test_file = tmp_path / "data.jsonl"
        test_file.write_text('{"data": "test"}\n')

        responses = [
            RESPONSE_WITH_FUNCTION,
            RESPONSE_WITH_FUNCTION_2,
            RESPONSE_CLEAN
        ]
        mock_llm = MockLLM(responses)

        cleaner = DataCleaner(
            llm_backend=mock_llm,
            file_path=str(test_file),
            chunk_size=10,
            max_iterations=5
        )

        original_cwd = os.getcwd()
        os.chdir(tmp_path)
        try:
            cleaner.run()
        finally:
            os.chdir(original_cwd)

        output_file = tmp_path / "cleaning_functions.py"
        content = output_file.read_text()

        # format_phones should be called before normalize_dates
        format_phones_pos = content.find('format_phones(data)')
        normalize_dates_pos = content.find('normalize_dates(data)')

        # Both should exist and format_phones should come first in clean_data
        assert format_phones_pos > 0
        assert normalize_dates_pos > 0


class TestEdgeCases:
    """Additional edge case tests."""

    def test_file_not_found_raises_error(self, tmp_path):
        """Non-existent file should raise FileNotFoundError."""
        mock_llm = MockLLM([])

        cleaner = DataCleaner(
            llm_backend=mock_llm,
            file_path=str(tmp_path / "nonexistent.jsonl"),
            chunk_size=10
        )

        with pytest.raises(FileNotFoundError):
            cleaner.run()

    def test_handles_unicode_content(self, tmp_path):
        """Should handle files with unicode content."""
        test_file = tmp_path / "unicode.jsonl"
        test_file.write_text('{"name": "cafe"}\n{"emoji": "test"}\n', encoding='utf-8')

        mock_llm = MockLLM([RESPONSE_CLEAN])

        cleaner = DataCleaner(
            llm_backend=mock_llm,
            file_path=str(test_file),
            chunk_size=10
        )

        original_cwd = os.getcwd()
        os.chdir(tmp_path)
        try:
            cleaner.run()
        finally:
            os.chdir(original_cwd)

        # Should process without errors
        assert len(mock_llm.calls) == 1

    def test_very_large_chunk_size(self, tmp_path):
        """Large chunk size should still work correctly."""
        test_file = tmp_path / "data.jsonl"
        test_file.write_text('{"id": 1}\n{"id": 2}\n')

        mock_llm = MockLLM([RESPONSE_CLEAN])

        cleaner = DataCleaner(
            llm_backend=mock_llm,
            file_path=str(test_file),
            chunk_size=10000  # Much larger than file
        )

        original_cwd = os.getcwd()
        os.chdir(tmp_path)
        try:
            cleaner.run()
        finally:
            os.chdir(original_cwd)

        # Should still work, all data in one chunk
        assert len(mock_llm.calls) == 1

    def test_chunk_size_one(self, tmp_path):
        """Chunk size of 1 should process items individually."""
        test_file = tmp_path / "data.jsonl"
        test_file.write_text('{"id": 1}\n{"id": 2}\n{"id": 3}\n')

        mock_llm = MockLLM([RESPONSE_CLEAN] * 3)

        cleaner = DataCleaner(
            llm_backend=mock_llm,
            file_path=str(test_file),
            chunk_size=1
        )

        original_cwd = os.getcwd()
        os.chdir(tmp_path)
        try:
            cleaner.run()
        finally:
            os.chdir(original_cwd)

        # Should have 3 chunks
        assert len(mock_llm.calls) == 3

    def test_empty_instructions(self, tmp_path):
        """Empty instructions should still work."""
        test_file = tmp_path / "data.jsonl"
        test_file.write_text('{"data": "test"}\n')

        mock_llm = MockLLM([RESPONSE_CLEAN])

        cleaner = DataCleaner(
            llm_backend=mock_llm,
            file_path=str(test_file),
            chunk_size=10,
            instructions=""  # Empty instructions
        )

        original_cwd = os.getcwd()
        os.chdir(tmp_path)
        try:
            cleaner.run()
        finally:
            os.chdir(original_cwd)

        assert len(mock_llm.calls) == 1

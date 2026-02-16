"""Tests for the core cleaner pipeline."""

import pytest
from recursive_cleaner import DataCleaner, build_prompt


class MockLLM:
    """Mock LLM that returns predefined responses."""

    def __init__(self, responses: list[str]):
        self.responses = iter(responses)
        self.calls = []

    def generate(self, prompt: str) -> str:
        self.calls.append(prompt)
        return next(self.responses)


# Sample valid XML responses
RESPONSE_WITH_FUNCTION = '''
<cleaning_analysis>
  <issues_detected>
    <issue id="1" solved="false">Phone numbers have inconsistent formats</issue>
  </issues_detected>
  <function_to_generate>
    <name>normalize_phones</name>
    <docstring>Normalize phone numbers to consistent format.</docstring>
    <code>
```python
def normalize_phones(data):
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
    <issue id="1" solved="true">Phone numbers - handled by normalize_phones</issue>
  </issues_detected>
  <chunk_status>clean</chunk_status>
</cleaning_analysis>
'''


def test_build_prompt_includes_all_parts():
    """Prompt includes instructions, context, and chunk."""
    result = build_prompt(
        instructions="Fix phone numbers",
        context="## existing_func\nDoes something",
        chunk='{"phone": "555-1234"}'
    )
    assert "Fix phone numbers" in result
    assert "## existing_func" in result
    assert '{"phone": "555-1234"}' in result


def test_data_cleaner_generates_function(tmp_path):
    """DataCleaner generates functions from LLM responses."""
    # Create test file
    test_file = tmp_path / "test.jsonl"
    test_file.write_text('{"phone": "555-1234"}\n')

    mock_llm = MockLLM([RESPONSE_WITH_FUNCTION, RESPONSE_CLEAN])

    cleaner = DataCleaner(
        llm_backend=mock_llm,
        file_path=str(test_file),
        chunk_size=10,
        instructions="Fix phone numbers"
    )
    cleaner.run()

    assert len(cleaner.functions) == 1
    assert cleaner.functions[0]["name"] == "normalize_phones"


def test_data_cleaner_stops_when_clean(tmp_path):
    """DataCleaner stops iterating when chunk is clean."""
    test_file = tmp_path / "test.jsonl"
    test_file.write_text('{"data": "ok"}\n')

    mock_llm = MockLLM([RESPONSE_CLEAN])

    cleaner = DataCleaner(
        llm_backend=mock_llm,
        file_path=str(test_file),
        chunk_size=10
    )
    cleaner.run()

    assert len(mock_llm.calls) == 1  # Only one call needed
    assert len(cleaner.functions) == 0


def test_data_cleaner_retries_on_parse_error(tmp_path):
    """DataCleaner retries with error feedback on ParseError."""
    test_file = tmp_path / "test.jsonl"
    test_file.write_text('{"data": "test"}\n')

    # First response is invalid, second is valid
    mock_llm = MockLLM(["not valid xml at all", RESPONSE_CLEAN])

    cleaner = DataCleaner(
        llm_backend=mock_llm,
        file_path=str(test_file),
        chunk_size=10
    )
    cleaner.run()

    # Should have retried
    assert len(mock_llm.calls) == 2
    # Second call should include error feedback
    assert "error" in mock_llm.calls[1].lower()


def test_data_cleaner_respects_max_iterations(tmp_path):
    """DataCleaner stops after max_iterations."""
    test_file = tmp_path / "test.jsonl"
    test_file.write_text('{"data": "test"}\n')

    # Always return needs_more_work
    responses = [RESPONSE_WITH_FUNCTION] * 10
    mock_llm = MockLLM(responses)

    cleaner = DataCleaner(
        llm_backend=mock_llm,
        file_path=str(test_file),
        chunk_size=10,
        max_iterations=3
    )
    cleaner.run()

    # Should stop at max_iterations
    assert len(mock_llm.calls) == 3


def test_detect_mode_returns_structured_for_xlsx(tmp_path):
    """DataCleaner._detect_mode() returns 'structured' for .xlsx files."""
    test_file = tmp_path / "test.xlsx"
    test_file.write_bytes(b"dummy")

    cleaner = DataCleaner(
        llm_backend=MockLLM([]),
        file_path=str(test_file),
    )
    assert cleaner._detect_mode() == "structured"


def test_detect_mode_returns_structured_for_xls(tmp_path):
    """DataCleaner._detect_mode() returns 'structured' for .xls files."""
    test_file = tmp_path / "test.xls"
    test_file.write_bytes(b"dummy")

    cleaner = DataCleaner(
        llm_backend=MockLLM([]),
        file_path=str(test_file),
    )
    assert cleaner._detect_mode() == "structured"


def test_detect_mode_returns_structured_for_ods(tmp_path):
    """DataCleaner._detect_mode() returns 'structured' for .ods files."""
    test_file = tmp_path / "test.ods"
    test_file.write_bytes(b"dummy")

    cleaner = DataCleaner(
        llm_backend=MockLLM([]),
        file_path=str(test_file),
    )
    assert cleaner._detect_mode() == "structured"


def test_is_known_extension_includes_xlsx(tmp_path):
    """DataCleaner._is_known_extension() returns True for .xlsx."""
    test_file = tmp_path / "test.xlsx"
    test_file.write_bytes(b"dummy")

    cleaner = DataCleaner(
        llm_backend=MockLLM([]),
        file_path=str(test_file),
    )
    assert cleaner._is_known_extension() is True


def test_data_cleaner_empty_file(tmp_path):
    """DataCleaner handles empty files gracefully."""
    test_file = tmp_path / "test.jsonl"
    test_file.write_text('')

    mock_llm = MockLLM([])

    cleaner = DataCleaner(
        llm_backend=mock_llm,
        file_path=str(test_file),
        chunk_size=10
    )
    cleaner.run()

    assert len(mock_llm.calls) == 0
    assert len(cleaner.functions) == 0


def test_adaptive_iteration_budget_stops_early(tmp_path):
    """Chunk processing stops after 2 consecutive fruitless iterations."""
    test_file = tmp_path / "test.jsonl"
    test_file.write_text('{"a": 1}\n')

    # needs_more_work but no code — fruitless iteration
    response_no_code = '''
<cleaning_analysis>
  <issues_detected>
    <issue id="1" solved="false">Something needs fixing</issue>
  </issues_detected>
  <chunk_status>needs_more_work</chunk_status>
</cleaning_analysis>
'''

    # Provide 5 responses (max_iterations=5) but expect only 2 to be consumed
    mock_llm = MockLLM([response_no_code] * 5)

    cleaner = DataCleaner(
        llm_backend=mock_llm,
        file_path=str(test_file),
        chunk_size=10,
        max_iterations=5,
    )
    cleaner.run()

    # Should have stopped after 2 fruitless iterations, not burned all 5
    assert len(mock_llm.calls) == 2
    assert len(cleaner.functions) == 0


def test_adaptive_budget_resets_on_success(tmp_path):
    """Fruitless counter resets when a function is accepted."""
    test_file = tmp_path / "test.jsonl"
    test_file.write_text('{"phone": "555-1234", "status": "actve"}\n')

    response_no_code_1 = '''
<cleaning_analysis>
  <issues_detected>
    <issue id="1" solved="false">Something vague</issue>
  </issues_detected>
  <chunk_status>needs_more_work</chunk_status>
</cleaning_analysis>
'''

    response_phone = '''
<cleaning_analysis>
  <issues_detected>
    <issue id="1" solved="false">Phone needs normalization</issue>
  </issues_detected>
  <function_to_generate>
    <name>fix_phone</name>
    <docstring>Normalize phone numbers.</docstring>
    <code>
```python
def fix_phone(record: dict) -> dict:
    record["phone"] = record["phone"].replace("-", "")
    return record
```
    </code>
  </function_to_generate>
  <chunk_status>needs_more_work</chunk_status>
</cleaning_analysis>
'''

    response_no_code_2 = '''
<cleaning_analysis>
  <issues_detected>
    <issue id="2" solved="false">Status has typos</issue>
  </issues_detected>
  <chunk_status>needs_more_work</chunk_status>
</cleaning_analysis>
'''

    response_clean = '''
<cleaning_analysis>
  <issues_detected>
    <issue id="1" solved="true">All clean</issue>
  </issues_detected>
  <chunk_status>clean</chunk_status>
</cleaning_analysis>
'''

    # Iteration 1: no code (fruitless=1)
    # Iteration 2: phone function accepted (fruitless=0)
    # Iteration 3: no code (fruitless=1)
    # Iteration 4: no code (fruitless=2) → break
    # Iteration 5: never reached
    mock_llm = MockLLM([
        response_no_code_1,
        response_phone,
        response_no_code_2,
        response_no_code_2,
        response_clean,  # should not be consumed
    ])

    cleaner = DataCleaner(
        llm_backend=mock_llm,
        file_path=str(test_file),
        chunk_size=10,
        max_iterations=5,
        validate_runtime=True,
    )
    cleaner.run()

    # 4 calls consumed (not 5)
    assert len(mock_llm.calls) == 4
    # Phone function was accepted
    assert len(cleaner.functions) == 1
    assert cleaner.functions[0]["name"] == "fix_phone"

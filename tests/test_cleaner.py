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

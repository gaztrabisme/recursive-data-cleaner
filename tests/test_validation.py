"""Tests for runtime validation of generated functions."""

import pytest
from recursive_cleaner import DataCleaner, validate_function, extract_sample_data


class MockLLM:
    """Mock LLM that returns predefined responses."""

    def __init__(self, responses: list[str]):
        self.responses = iter(responses)
        self.calls = []

    def generate(self, prompt: str) -> str:
        self.calls.append(prompt)
        return next(self.responses)


# Test validate_function directly

def test_validate_function_accepts_working_code():
    """Function that works on sample data is accepted."""
    code = '''
def process_data(data):
    return data.get("name", "unknown")
'''
    sample_data = [{"name": "Alice"}, {"name": "Bob"}]
    valid, error = validate_function(code, sample_data, "process_data")
    assert valid is True
    assert error is None


def test_validate_function_rejects_key_error():
    """Function with KeyError on nonexistent key is rejected."""
    code = '''
def bad_function(data):
    return data["nonexistent_key"]
'''
    sample_data = [{"name": "Alice"}]
    valid, error = validate_function(code, sample_data, "bad_function")
    assert valid is False
    assert "KeyError" in error


def test_validate_function_rejects_type_error():
    """Function with TypeError is rejected."""
    code = '''
def type_error_func(data):
    return len(data["name"]) + data["name"]  # int + str
'''
    sample_data = [{"name": "Alice"}]
    valid, error = validate_function(code, sample_data, "type_error_func")
    assert valid is False
    assert "TypeError" in error


def test_validate_function_rejects_attribute_error():
    """Function with AttributeError is rejected."""
    code = '''
def attr_error_func(data):
    return data["name"].nonexistent_method()
'''
    sample_data = [{"name": "Alice"}]
    valid, error = validate_function(code, sample_data, "attr_error_func")
    assert valid is False
    assert "AttributeError" in error


def test_validate_function_handles_empty_sample():
    """Empty sample data returns success (nothing to validate against)."""
    code = '''
def some_func(data):
    return data["will_fail"]
'''
    valid, error = validate_function(code, [], "some_func")
    assert valid is True
    assert error is None


def test_validate_function_missing_function_name():
    """Returns error if function name not found in code."""
    code = '''
def actual_name(data):
    return data
'''
    valid, error = validate_function(code, [{"a": 1}], "wrong_name")
    assert valid is False
    assert "not found" in error.lower()


def test_validate_function_syntax_error_in_code():
    """Returns error if code has syntax error."""
    code = '''
def broken_func(data
    return data
'''
    valid, error = validate_function(code, [{"a": 1}], "broken_func")
    assert valid is False
    assert "compilation failed" in error.lower() or "SyntaxError" in error


# Test extract_sample_data

def test_extract_sample_data_jsonl():
    """Extracts JSON objects from JSONL chunk."""
    chunk = '{"name": "Alice"}\n{"name": "Bob"}\n{"name": "Carol"}\n{"name": "Dave"}'
    samples = extract_sample_data(chunk)
    assert len(samples) == 3  # max_samples default is 3
    assert samples[0]["name"] == "Alice"
    assert samples[2]["name"] == "Carol"


def test_extract_sample_data_handles_invalid_lines():
    """Skips invalid JSON lines."""
    chunk = '{"valid": true}\nnot json\n{"also_valid": true}'
    samples = extract_sample_data(chunk)
    assert len(samples) == 2
    assert samples[0]["valid"] is True
    assert samples[1]["also_valid"] is True


def test_extract_sample_data_empty_chunk():
    """Returns empty list for empty chunk."""
    samples = extract_sample_data("")
    assert samples == []


# Test integration with DataCleaner

RESPONSE_WITH_BAD_FUNCTION = '''
<cleaning_analysis>
  <issues_detected>
    <issue id="1" solved="false">Data needs processing</issue>
  </issues_detected>
  <function_to_generate>
    <name>bad_processor</name>
    <docstring>Tries to access nonexistent key.</docstring>
    <code>
```python
def bad_processor(data):
    return data["nonexistent_field"]
```
    </code>
  </function_to_generate>
  <chunk_status>needs_more_work</chunk_status>
</cleaning_analysis>
'''

RESPONSE_WITH_GOOD_FUNCTION = '''
<cleaning_analysis>
  <issues_detected>
    <issue id="1" solved="false">Data needs processing</issue>
  </issues_detected>
  <function_to_generate>
    <name>good_processor</name>
    <docstring>Safely processes data.</docstring>
    <code>
```python
def good_processor(data):
    return data.get("name", "unknown")
```
    </code>
  </function_to_generate>
  <chunk_status>needs_more_work</chunk_status>
</cleaning_analysis>
'''

RESPONSE_CLEAN = '''
<cleaning_analysis>
  <issues_detected>
    <issue id="1" solved="true">Already handled</issue>
  </issues_detected>
  <chunk_status>clean</chunk_status>
</cleaning_analysis>
'''


def test_cleaner_retries_on_validation_failure(tmp_path):
    """DataCleaner retries with error feedback when validation fails."""
    test_file = tmp_path / "test.jsonl"
    test_file.write_text('{"name": "Alice"}\n{"name": "Bob"}\n')

    # First response fails validation, second succeeds, third marks clean
    mock_llm = MockLLM([RESPONSE_WITH_BAD_FUNCTION, RESPONSE_WITH_GOOD_FUNCTION, RESPONSE_CLEAN])

    cleaner = DataCleaner(
        llm_backend=mock_llm,
        file_path=str(test_file),
        chunk_size=10,
        validate_runtime=True,
    )
    cleaner.run()

    # Should have retried (at least 2 calls)
    assert len(mock_llm.calls) >= 2
    # Second call should include validation error feedback
    assert "validation" in mock_llm.calls[1].lower() or "runtime" in mock_llm.calls[1].lower()
    # Only the good function should be added
    assert len(cleaner.functions) == 1
    assert cleaner.functions[0]["name"] == "good_processor"


def test_cleaner_validation_disabled(tmp_path):
    """With validate_runtime=False, bad functions are accepted."""
    test_file = tmp_path / "test.jsonl"
    test_file.write_text('{"name": "Alice"}\n')

    mock_llm = MockLLM([RESPONSE_WITH_BAD_FUNCTION, RESPONSE_CLEAN])

    cleaner = DataCleaner(
        llm_backend=mock_llm,
        file_path=str(test_file),
        chunk_size=10,
        validate_runtime=False,
    )
    cleaner.run()

    # Bad function should be accepted since validation is disabled
    assert len(cleaner.functions) == 1
    assert cleaner.functions[0]["name"] == "bad_processor"

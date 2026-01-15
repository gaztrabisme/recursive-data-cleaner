"""Tests for validation holdout splitting."""

import pytest
from recursive_cleaner import DataCleaner
from recursive_cleaner.validation import split_holdout, extract_sample_data


class MockLLM:
    """Mock LLM that returns predefined responses."""

    def __init__(self, responses: list[str]):
        self.responses = iter(responses)
        self.calls = []

    def generate(self, prompt: str) -> str:
        self.calls.append(prompt)
        return next(self.responses)


# Test split_holdout function - Structured mode

def test_split_holdout_structured_basic():
    """Basic structured mode split with 20% holdout."""
    chunk = '{"a":1}\n{"b":2}\n{"c":3}\n{"d":4}\n{"e":5}'
    gen, holdout = split_holdout(chunk, 0.2, mode="structured")
    # 5 records * 0.2 = 1 holdout, so 4 gen + 1 holdout
    assert gen.count("\n") == 3  # 4 lines = 3 newlines
    assert '{"e":5}' in holdout
    assert '{"a":1}' in gen


def test_split_holdout_structured_larger_ratio():
    """Structured mode with 40% holdout."""
    chunk = '{"a":1}\n{"b":2}\n{"c":3}\n{"d":4}\n{"e":5}\n{"f":6}\n{"g":7}\n{"h":8}\n{"i":9}\n{"j":10}'
    gen, holdout = split_holdout(chunk, 0.4, mode="structured")
    # 10 records * 0.4 = 4 holdout, so 6 gen + 4 holdout
    gen_lines = [ln for ln in gen.split("\n") if ln.strip()]
    holdout_lines = [ln for ln in holdout.split("\n") if ln.strip()]
    assert len(gen_lines) == 6
    assert len(holdout_lines) == 4


def test_split_holdout_structured_zero_ratio():
    """Zero holdout ratio returns entire chunk as generation."""
    chunk = '{"a":1}\n{"b":2}\n{"c":3}'
    gen, holdout = split_holdout(chunk, 0.0, mode="structured")
    assert gen == chunk
    assert holdout == ""


def test_split_holdout_structured_minimum_one_record():
    """Minimum holdout is 1 record even if ratio would give 0."""
    chunk = '{"a":1}\n{"b":2}'
    gen, holdout = split_holdout(chunk, 0.1, mode="structured")  # 2 * 0.1 = 0, but min is 1
    gen_lines = [ln for ln in gen.split("\n") if ln.strip()]
    holdout_lines = [ln for ln in holdout.split("\n") if ln.strip()]
    assert len(gen_lines) == 1
    assert len(holdout_lines) == 1


def test_split_holdout_structured_empty_chunk():
    """Empty chunk returns original."""
    gen, holdout = split_holdout("", 0.2, mode="structured")
    assert gen == ""
    assert holdout == ""


def test_split_holdout_structured_single_record():
    """Single record chunk returns all to generation when possible."""
    chunk = '{"a":1}'
    gen, holdout = split_holdout(chunk, 0.2, mode="structured")
    # With only 1 record, holdout_count = max(1, int(1*0.2)) = max(1,0) = 1
    # split_idx = 1 - 1 = 0, so gen is empty, holdout is entire chunk
    gen_lines = [ln for ln in gen.split("\n") if ln.strip()]
    holdout_lines = [ln for ln in holdout.split("\n") if ln.strip()]
    assert len(holdout_lines) == 1


# Test split_holdout function - Text mode

def test_split_holdout_text_basic():
    """Basic text mode split at sentence boundary."""
    chunk = "First sentence. Second sentence. Third sentence. Fourth sentence. Fifth sentence."
    gen, holdout = split_holdout(chunk, 0.2, mode="text")
    # 5 sentences * 0.2 = 1 holdout
    assert "First sentence" in gen
    assert "Fifth sentence" in holdout
    assert "Fifth sentence" not in gen


def test_split_holdout_text_larger_ratio():
    """Text mode with 40% holdout."""
    chunk = "One. Two. Three. Four. Five. Six. Seven. Eight. Nine. Ten."
    gen, holdout = split_holdout(chunk, 0.4, mode="text")
    # 10 sentences * 0.4 = 4 holdout
    assert "One" in gen
    assert "Six" in gen
    assert "Seven" in holdout


def test_split_holdout_text_zero_ratio():
    """Zero holdout ratio returns entire text as generation."""
    chunk = "First sentence. Second sentence."
    gen, holdout = split_holdout(chunk, 0.0, mode="text")
    assert gen == chunk
    assert holdout == ""


def test_split_holdout_text_single_sentence():
    """Single sentence returns original (can't split)."""
    chunk = "Just one sentence without period"
    gen, holdout = split_holdout(chunk, 0.2, mode="text")
    assert gen == chunk
    assert holdout == ""


def test_split_holdout_text_question_marks():
    """Text mode handles question marks as sentence boundaries."""
    chunk = "Is this first? Is this second? Is this third? Is this fourth? Is this fifth?"
    gen, holdout = split_holdout(chunk, 0.2, mode="text")
    assert "Is this first" in gen
    assert "Is this fifth" in holdout


def test_split_holdout_text_exclamation_marks():
    """Text mode handles exclamation marks as sentence boundaries."""
    chunk = "Wow first! Amazing second! Great third! Super fourth! Final fifth!"
    gen, holdout = split_holdout(chunk, 0.2, mode="text")
    assert "Wow first" in gen
    assert "Final fifth" in holdout


# Test integration with DataCleaner

RESPONSE_CLEAN = '''
<cleaning_analysis>
  <issues_detected>
    <issue id="1" solved="true">Data is already clean</issue>
  </issues_detected>
  <chunk_status>clean</chunk_status>
</cleaning_analysis>
'''

RESPONSE_WITH_FUNCTION = '''
<cleaning_analysis>
  <issues_detected>
    <issue id="1" solved="false">Data needs processing</issue>
  </issues_detected>
  <function_to_generate>
    <name>process_data</name>
    <docstring>Processes the data safely.</docstring>
    <code>
```python
def process_data(data):
    return data.get("name", "unknown")
```
    </code>
  </function_to_generate>
  <chunk_status>needs_more_work</chunk_status>
</cleaning_analysis>
'''


def test_cleaner_holdout_enabled_by_default(tmp_path):
    """DataCleaner has holdout_ratio=0.2 by default."""
    test_file = tmp_path / "test.jsonl"
    test_file.write_text('{"name": "Alice"}\n')

    mock_llm = MockLLM([RESPONSE_CLEAN])

    cleaner = DataCleaner(
        llm_backend=mock_llm,
        file_path=str(test_file),
        chunk_size=10,
    )

    assert cleaner.holdout_ratio == 0.2


def test_cleaner_holdout_disabled_with_zero_ratio(tmp_path):
    """DataCleaner with holdout_ratio=0 uses entire chunk for generation."""
    test_file = tmp_path / "test.jsonl"
    # Create enough records to see the difference
    test_file.write_text('{"a":1}\n{"b":2}\n{"c":3}\n{"d":4}\n{"e":5}\n')

    mock_llm = MockLLM([RESPONSE_CLEAN])

    cleaner = DataCleaner(
        llm_backend=mock_llm,
        file_path=str(test_file),
        chunk_size=10,
        holdout_ratio=0.0,
    )
    cleaner.run()

    # All records should be in the prompt
    assert '{"e":5}' in mock_llm.calls[0]


def test_cleaner_holdout_separates_generation_from_validation(tmp_path):
    """With holdout enabled, LLM sees only generation portion."""
    test_file = tmp_path / "test.jsonl"
    # 5 records, 20% holdout = 1 record held out
    test_file.write_text('{"a":1}\n{"b":2}\n{"c":3}\n{"d":4}\n{"e":5}\n')

    mock_llm = MockLLM([RESPONSE_CLEAN])

    cleaner = DataCleaner(
        llm_backend=mock_llm,
        file_path=str(test_file),
        chunk_size=10,
        holdout_ratio=0.2,
        validate_runtime=True,
    )
    cleaner.run()

    # Last record should NOT be in the prompt (held out)
    assert '{"e":5}' not in mock_llm.calls[0]
    # First records should be in the prompt
    assert '{"a":1}' in mock_llm.calls[0]


def test_cleaner_holdout_disabled_when_validation_off(tmp_path):
    """Holdout is disabled when validate_runtime=False."""
    test_file = tmp_path / "test.jsonl"
    test_file.write_text('{"a":1}\n{"b":2}\n{"c":3}\n{"d":4}\n{"e":5}\n')

    mock_llm = MockLLM([RESPONSE_CLEAN])

    cleaner = DataCleaner(
        llm_backend=mock_llm,
        file_path=str(test_file),
        chunk_size=10,
        holdout_ratio=0.2,
        validate_runtime=False,
    )
    cleaner.run()

    # All records should be in the prompt since validation is disabled
    assert '{"e":5}' in mock_llm.calls[0]


def test_cleaner_holdout_validation_uses_holdout_data(tmp_path):
    """Validation runs on holdout data, not generation data."""
    test_file = tmp_path / "test.jsonl"
    # Records where only the holdout has a specific key
    test_file.write_text('{"name":"A"}\n{"name":"B"}\n{"name":"C"}\n{"name":"D"}\n{"special":"E"}\n')

    # Function that accesses "special" key - should fail on holdout
    response_with_special_access = '''
<cleaning_analysis>
  <issues_detected>
    <issue id="1" solved="false">Need to access special</issue>
  </issues_detected>
  <function_to_generate>
    <name>get_special</name>
    <docstring>Gets the special field.</docstring>
    <code>
```python
def get_special(data):
    return data["special"]
```
    </code>
  </function_to_generate>
  <chunk_status>needs_more_work</chunk_status>
</cleaning_analysis>
'''

    mock_llm = MockLLM([response_with_special_access, RESPONSE_CLEAN])

    cleaner = DataCleaner(
        llm_backend=mock_llm,
        file_path=str(test_file),
        chunk_size=10,
        holdout_ratio=0.2,  # Holdout contains {"special":"E"}
        validate_runtime=True,
    )
    cleaner.run()

    # The function should be accepted because holdout has the "special" key
    assert len(cleaner.functions) == 1
    assert cleaner.functions[0]["name"] == "get_special"


def test_cleaner_holdout_text_mode(tmp_path):
    """Holdout works in text mode splitting at sentence boundaries."""
    test_file = tmp_path / "test.txt"
    test_file.write_text("First sentence. Second sentence. Third sentence. Fourth sentence. Fifth sentence.")

    mock_llm = MockLLM([RESPONSE_CLEAN])

    cleaner = DataCleaner(
        llm_backend=mock_llm,
        file_path=str(test_file),
        chunk_size=1000,  # Large enough to fit all in one chunk
        mode="text",
        holdout_ratio=0.2,
        validate_runtime=True,
    )
    cleaner.run()

    # Last sentence should not be in prompt
    assert "Fifth sentence" not in mock_llm.calls[0]
    assert "First sentence" in mock_llm.calls[0]

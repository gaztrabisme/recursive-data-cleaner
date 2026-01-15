"""Tests for dry run mode."""

import pytest
from pathlib import Path

from recursive_cleaner import DataCleaner


RESPONSE_WITH_ISSUES = '''
<cleaning_analysis>
  <issues_detected>
    <issue id="1" solved="false">Phone numbers are inconsistent</issue>
    <issue id="2" solved="false">Dates in wrong format</issue>
  </issues_detected>
  <function_to_generate>
    <name>fix_phones</name>
    <docstring>Fix phone numbers.</docstring>
    <code>
```python
def fix_phones(data):
    return data
```
    </code>
  </function_to_generate>
  <chunk_status>needs_more_work</chunk_status>
</cleaning_analysis>
'''

CLEAN_RESPONSE = '''
<cleaning_analysis>
  <issues_detected>
    <issue id="1" solved="true">Already clean</issue>
  </issues_detected>
  <chunk_status>clean</chunk_status>
</cleaning_analysis>
'''


class MockLLM:
    """Mock LLM that returns predefined responses."""

    def __init__(self, responses: list[str]):
        self.responses = iter(responses)
        self.call_count = 0

    def generate(self, prompt: str) -> str:
        self.call_count += 1
        return next(self.responses)


def test_dry_run_no_output_file(tmp_path):
    """Dry run doesn't create output file."""
    test_file = tmp_path / "test.jsonl"
    test_file.write_text('{"a": 1}\n')
    output_file = Path("cleaning_functions.py")

    # Remove output file if it exists
    if output_file.exists():
        output_file.unlink()

    mock_llm = MockLLM([RESPONSE_WITH_ISSUES])
    cleaner = DataCleaner(
        llm_backend=mock_llm,
        file_path=str(test_file),
        chunk_size=10,
        dry_run=True,
        report_path=None,
    )
    cleaner.run()

    # No output file should be created
    assert not output_file.exists()


def test_dry_run_no_functions_stored(tmp_path):
    """Dry run doesn't store functions."""
    test_file = tmp_path / "test.jsonl"
    test_file.write_text('{"a": 1}\n')

    mock_llm = MockLLM([RESPONSE_WITH_ISSUES])
    cleaner = DataCleaner(
        llm_backend=mock_llm,
        file_path=str(test_file),
        chunk_size=10,
        dry_run=True,
    )
    cleaner.run()

    # No functions should be stored
    assert len(cleaner.functions) == 0


def test_dry_run_emits_issues_detected(tmp_path):
    """Dry run emits issues_detected event."""
    test_file = tmp_path / "test.jsonl"
    test_file.write_text('{"a": 1}\n')

    events = []

    def track_events(e):
        events.append(e)

    mock_llm = MockLLM([RESPONSE_WITH_ISSUES])
    cleaner = DataCleaner(
        llm_backend=mock_llm,
        file_path=str(test_file),
        chunk_size=10,
        dry_run=True,
        on_progress=track_events,
    )
    cleaner.run()

    # Find issues_detected event
    issues_events = [e for e in events if e["type"] == "issues_detected"]
    assert len(issues_events) == 1
    assert "issues" in issues_events[0]
    assert len(issues_events[0]["issues"]) == 2


def test_dry_run_emits_dry_run_complete(tmp_path):
    """Dry run emits dry_run_complete event."""
    test_file = tmp_path / "test.jsonl"
    test_file.write_text('{"a": 1}\n')

    events = []

    def track_events(e):
        events.append(e)

    mock_llm = MockLLM([RESPONSE_WITH_ISSUES])
    cleaner = DataCleaner(
        llm_backend=mock_llm,
        file_path=str(test_file),
        chunk_size=10,
        dry_run=True,
        on_progress=track_events,
    )
    cleaner.run()

    # Find dry_run_complete event
    complete_events = [e for e in events if e["type"] == "dry_run_complete"]
    assert len(complete_events) == 1
    assert "latency_stats" in complete_events[0]


def test_dry_run_processes_all_chunks(tmp_path):
    """Dry run processes all chunks."""
    test_file = tmp_path / "test.jsonl"
    # Create file with multiple chunks worth of data
    test_file.write_text('{"a": 1}\n{"a": 2}\n{"a": 3}\n{"a": 4}\n')

    events = []

    def track_events(e):
        events.append(e)

    # Provide responses for 2 chunks
    mock_llm = MockLLM([RESPONSE_WITH_ISSUES, CLEAN_RESPONSE])
    cleaner = DataCleaner(
        llm_backend=mock_llm,
        file_path=str(test_file),
        chunk_size=2,  # 2 items per chunk = 2 chunks
        dry_run=True,
        on_progress=track_events,
    )
    cleaner.run()

    # Should have 2 chunk_start events
    chunk_starts = [e for e in events if e["type"] == "chunk_start"]
    assert len(chunk_starts) == 2


def test_dry_run_one_llm_call_per_chunk(tmp_path):
    """Dry run makes exactly one LLM call per chunk."""
    test_file = tmp_path / "test.jsonl"
    test_file.write_text('{"a": 1}\n{"a": 2}\n')

    mock_llm = MockLLM([RESPONSE_WITH_ISSUES])
    cleaner = DataCleaner(
        llm_backend=mock_llm,
        file_path=str(test_file),
        chunk_size=10,
        dry_run=True,
    )
    cleaner.run()

    # Should have exactly 1 LLM call (not multiple iterations)
    assert mock_llm.call_count == 1


def test_non_dry_run_writes_output(tmp_path):
    """Non-dry run still writes output file."""
    test_file = tmp_path / "test.jsonl"
    test_file.write_text('{"a": 1}\n')
    output_file = tmp_path / "clean.py"

    # Need responses for function generation + clean
    mock_llm = MockLLM([RESPONSE_WITH_ISSUES, CLEAN_RESPONSE])
    cleaner = DataCleaner(
        llm_backend=mock_llm,
        file_path=str(test_file),
        chunk_size=10,
        dry_run=False,
        report_path=None,
    )

    # Change working directory to tmp_path for output
    import os
    original_cwd = os.getcwd()
    try:
        os.chdir(tmp_path)
        cleaner.run()
        assert Path("cleaning_functions.py").exists()
    finally:
        os.chdir(original_cwd)

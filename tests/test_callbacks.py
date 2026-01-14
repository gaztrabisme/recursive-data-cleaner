"""Tests for progress callback functionality."""

import tempfile
import os

import pytest

from recursive_cleaner.cleaner import DataCleaner


class MockBackend:
    """Mock LLM backend that returns clean status immediately."""

    def generate(self, prompt: str) -> str:
        return """
<cleaning_analysis>
  <issues_detected>
    <issue id="1" solved="true">No issues found</issue>
  </issues_detected>
  <chunk_status>clean</chunk_status>
</cleaning_analysis>
"""


class MockBackendWithFunction:
    """Mock LLM backend that generates one function then marks clean."""

    def __init__(self):
        self.call_count = 0

    def generate(self, prompt: str) -> str:
        self.call_count += 1
        if self.call_count == 1:
            return """
<cleaning_analysis>
  <issues_detected>
    <issue id="1" solved="false">Phone numbers need normalization</issue>
  </issues_detected>
  <function_to_generate>
    <name>normalize_phone</name>
    <docstring>Normalize phone numbers.</docstring>
    <code>
```python
def normalize_phone(data):
    return data
```
    </code>
  </function_to_generate>
  <chunk_status>needs_more_work</chunk_status>
</cleaning_analysis>
"""
        return """
<cleaning_analysis>
  <issues_detected>
    <issue id="1" solved="true">Phone numbers normalized</issue>
  </issues_detected>
  <chunk_status>clean</chunk_status>
</cleaning_analysis>
"""


@pytest.fixture
def temp_jsonl_file():
    """Create a temporary JSONL file for testing."""
    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".jsonl", delete=False
    ) as f:
        f.write('{"name": "Alice"}\n')
        f.write('{"name": "Bob"}\n')
        temp_path = f.name
    yield temp_path
    os.unlink(temp_path)


def test_callback_receives_correct_event_sequence(temp_jsonl_file):
    """Test callback receives events in correct order."""
    events = []

    def callback(event):
        events.append(event["type"])

    cleaner = DataCleaner(
        llm_backend=MockBackend(),
        file_path=temp_jsonl_file,
        chunk_size=10,
        on_progress=callback,
    )
    cleaner.run()

    # Should have: chunk_start, iteration, chunk_done, complete
    assert "chunk_start" in events
    assert "iteration" in events
    assert "chunk_done" in events
    assert "complete" in events
    # chunk_start should come before chunk_done
    assert events.index("chunk_start") < events.index("chunk_done")


def test_callback_receives_correct_chunk_info(temp_jsonl_file):
    """Test callback receives correct chunk_index and total_chunks."""
    events = []

    def callback(event):
        events.append(event)

    cleaner = DataCleaner(
        llm_backend=MockBackend(),
        file_path=temp_jsonl_file,
        chunk_size=10,
        on_progress=callback,
    )
    cleaner.run()

    # All events should have chunk_index and total_chunks
    for event in events:
        assert "chunk_index" in event
        assert "total_chunks" in event
        assert event["total_chunks"] == 1  # Small file = 1 chunk
        assert event["chunk_index"] == 0


def test_function_generated_includes_function_name(temp_jsonl_file):
    """Test function_generated event includes function_name."""
    events = []

    def callback(event):
        events.append(event)

    cleaner = DataCleaner(
        llm_backend=MockBackendWithFunction(),
        file_path=temp_jsonl_file,
        chunk_size=10,
        on_progress=callback,
    )
    cleaner.run()

    # Find function_generated event
    func_events = [e for e in events if e["type"] == "function_generated"]
    assert len(func_events) == 1
    assert func_events[0]["function_name"] == "normalize_phone"


def test_callback_exception_does_not_crash_pipeline(temp_jsonl_file, capsys):
    """Test that callback exceptions are caught and logged."""

    def bad_callback(event):
        raise ValueError("Callback error!")

    cleaner = DataCleaner(
        llm_backend=MockBackend(),
        file_path=temp_jsonl_file,
        chunk_size=10,
        on_progress=bad_callback,
    )
    # Should not raise
    cleaner.run()

    # Check warning was printed
    captured = capsys.readouterr()
    assert "callback error" in captured.out.lower()


def test_no_callback_works_silently(temp_jsonl_file):
    """Test on_progress=None works without errors."""
    cleaner = DataCleaner(
        llm_backend=MockBackend(),
        file_path=temp_jsonl_file,
        chunk_size=10,
        on_progress=None,
    )
    # Should not raise
    cleaner.run()
    assert len(cleaner.functions) == 0  # Clean on first try


def test_iteration_event_includes_iteration_number(temp_jsonl_file):
    """Test iteration event includes the iteration number."""
    events = []

    def callback(event):
        events.append(event)

    cleaner = DataCleaner(
        llm_backend=MockBackendWithFunction(),
        file_path=temp_jsonl_file,
        chunk_size=10,
        on_progress=callback,
    )
    cleaner.run()

    # Find iteration events
    iter_events = [e for e in events if e["type"] == "iteration"]
    assert len(iter_events) >= 1
    # First iteration should be 0
    assert iter_events[0]["iteration"] == 0

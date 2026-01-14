"""Tests for incremental saves and resume functionality."""

import json
import os
import tempfile

import pytest

from recursive_cleaner.cleaner import DataCleaner, STATE_VERSION


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
        f.write('{"name": "Alice", "phone": "555-1234"}\n')
        f.write('{"name": "Bob", "phone": "555-5678"}\n')
        temp_path = f.name
    yield temp_path
    os.unlink(temp_path)


@pytest.fixture
def temp_multi_chunk_file():
    """Create a temporary JSONL file with multiple chunks."""
    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".jsonl", delete=False
    ) as f:
        # Write 10 records to ensure multiple chunks with chunk_size=3
        for i in range(10):
            f.write(f'{{"id": {i}, "name": "Person{i}"}}\n')
        temp_path = f.name
    yield temp_path
    os.unlink(temp_path)


@pytest.fixture
def temp_state_file():
    """Create a temporary state file path."""
    fd, temp_path = tempfile.mkstemp(suffix=".json")
    os.close(fd)
    os.unlink(temp_path)  # Remove so tests can create it
    yield temp_path
    if os.path.exists(temp_path):
        os.unlink(temp_path)
    if os.path.exists(temp_path + ".tmp"):
        os.unlink(temp_path + ".tmp")


def test_state_file_created_after_processing(temp_jsonl_file, temp_state_file):
    """Test that state file is created after processing."""
    cleaner = DataCleaner(
        llm_backend=MockBackend(),
        file_path=temp_jsonl_file,
        chunk_size=10,
        state_file=temp_state_file,
    )
    cleaner.run()

    assert os.path.exists(temp_state_file)


def test_state_file_contains_expected_structure(temp_jsonl_file, temp_state_file):
    """Test that state file contains expected structure."""
    cleaner = DataCleaner(
        llm_backend=MockBackend(),
        file_path=temp_jsonl_file,
        chunk_size=10,
        instructions="Test instructions",
        state_file=temp_state_file,
    )
    cleaner.run()

    with open(temp_state_file) as f:
        state = json.load(f)

    assert state["version"] == STATE_VERSION
    assert state["file_path"] == temp_jsonl_file
    assert state["instructions"] == "Test instructions"
    assert state["chunk_size"] == 10
    assert "last_completed_chunk" in state
    assert "total_chunks" in state
    assert "functions" in state
    assert "timestamp" in state
    assert isinstance(state["functions"], list)


def test_resume_skips_completed_chunks(temp_multi_chunk_file, temp_state_file, capsys):
    """Test that resume skips already completed chunks."""
    # First run: process 2 chunks then simulate interruption
    backend1 = MockBackend()
    cleaner1 = DataCleaner(
        llm_backend=backend1,
        file_path=temp_multi_chunk_file,
        chunk_size=3,
        state_file=temp_state_file,
    )
    # Manually run first two chunks
    chunks = cleaner1._load_state()  # Returns False (no state yet)
    from recursive_cleaner.parsers import chunk_file
    from recursive_cleaner.schema import infer_schema, format_schema_for_prompt

    all_chunks = chunk_file(temp_multi_chunk_file, 3)
    schema = infer_schema(temp_multi_chunk_file, 10)
    cleaner1._schema_str = format_schema_for_prompt(schema)
    cleaner1._total_chunks = len(all_chunks)

    # Process only first 2 chunks
    for i in range(2):
        cleaner1._process_chunk(all_chunks[i], i)
        cleaner1._last_completed_chunk = i
        cleaner1._save_state()

    # Resume with new cleaner
    backend2 = MockBackend()
    cleaner2 = DataCleaner(
        llm_backend=backend2,
        file_path=temp_multi_chunk_file,
        chunk_size=3,
        state_file=temp_state_file,
    )
    cleaner2.run()

    captured = capsys.readouterr()
    # Should show skipping messages for first 2 chunks
    assert "Skipping chunk 1" in captured.out
    assert "Skipping chunk 2" in captured.out


def test_interrupted_run_plus_resume_produces_same_functions(
    temp_multi_chunk_file, temp_state_file
):
    """Test that interrupted run + resume preserves functions from first run."""
    # Interrupted run: only first chunk
    backend1 = MockBackendWithFunction()
    cleaner1 = DataCleaner(
        llm_backend=backend1,
        file_path=temp_multi_chunk_file,
        chunk_size=5,
        state_file=temp_state_file,
    )
    from recursive_cleaner.parsers import chunk_file
    from recursive_cleaner.schema import infer_schema, format_schema_for_prompt

    all_chunks = chunk_file(temp_multi_chunk_file, 5)
    schema = infer_schema(temp_multi_chunk_file, 10)
    cleaner1._schema_str = format_schema_for_prompt(schema)
    cleaner1._total_chunks = len(all_chunks)

    # Process only first chunk
    cleaner1._process_chunk(all_chunks[0], 0)
    cleaner1._last_completed_chunk = 0
    cleaner1._save_state()

    # Verify state was saved with the function
    with open(temp_state_file) as f:
        saved_state = json.load(f)
    assert len(saved_state["functions"]) == 1
    assert saved_state["functions"][0]["name"] == "normalize_phone"

    # Resume for second chunk
    cleaner2 = DataCleaner(
        llm_backend=MockBackend(),  # Use clean backend for remaining chunks
        file_path=temp_multi_chunk_file,
        chunk_size=5,
        state_file=temp_state_file,
    )
    cleaner2.run()

    # Should have preserved the function from first run
    assert len(cleaner2.functions) == 1
    assert cleaner2.functions[0]["name"] == "normalize_phone"


def test_invalid_state_file_raises_clear_error(temp_jsonl_file, temp_state_file):
    """Test that invalid state file raises clear error."""
    # Write invalid JSON
    with open(temp_state_file, "w") as f:
        f.write("{ invalid json content")

    cleaner = DataCleaner(
        llm_backend=MockBackend(),
        file_path=temp_jsonl_file,
        chunk_size=10,
        state_file=temp_state_file,
    )

    with pytest.raises(ValueError) as excinfo:
        cleaner.run()

    assert "Invalid state file JSON" in str(excinfo.value)


def test_mismatched_file_path_raises_error(temp_jsonl_file, temp_state_file):
    """Test that mismatched file_path raises error."""
    # Create state file with different file_path
    state = {
        "version": STATE_VERSION,
        "file_path": "/different/path/data.jsonl",
        "instructions": "",
        "chunk_size": 10,
        "last_completed_chunk": 0,
        "total_chunks": 1,
        "functions": [],
        "timestamp": "2025-01-14T12:00:00Z",
    }
    with open(temp_state_file, "w") as f:
        json.dump(state, f)

    cleaner = DataCleaner(
        llm_backend=MockBackend(),
        file_path=temp_jsonl_file,
        chunk_size=10,
        state_file=temp_state_file,
    )

    with pytest.raises(ValueError) as excinfo:
        cleaner.run()

    assert "file_path mismatch" in str(excinfo.value).lower()


def test_resume_classmethod_loads_state(temp_jsonl_file, temp_state_file):
    """Test that resume classmethod correctly loads state."""
    # Create initial state
    state = {
        "version": STATE_VERSION,
        "file_path": temp_jsonl_file,
        "instructions": "Original instructions",
        "chunk_size": 10,
        "last_completed_chunk": 0,
        "total_chunks": 1,
        "functions": [
            {"name": "test_func", "docstring": "Test docstring", "code": "def test_func(data): pass"}
        ],
        "timestamp": "2025-01-14T12:00:00Z",
    }
    with open(temp_state_file, "w") as f:
        json.dump(state, f)

    cleaner = DataCleaner.resume(temp_state_file, MockBackend())

    assert cleaner.file_path == temp_jsonl_file
    assert cleaner.instructions == "Original instructions"
    assert cleaner.chunk_size == 10
    assert len(cleaner.functions) == 1
    assert cleaner.functions[0]["name"] == "test_func"
    assert cleaner._last_completed_chunk == 0


def test_resume_nonexistent_file_raises_error():
    """Test that resume with nonexistent file raises FileNotFoundError."""
    with pytest.raises(FileNotFoundError):
        DataCleaner.resume("/nonexistent/state.json", MockBackend())


def test_resume_invalid_json_raises_error(temp_state_file):
    """Test that resume with invalid JSON raises ValueError."""
    with open(temp_state_file, "w") as f:
        f.write("not valid json")

    with pytest.raises(ValueError) as excinfo:
        DataCleaner.resume(temp_state_file, MockBackend())

    assert "Invalid state file JSON" in str(excinfo.value)


def test_no_state_file_works_normally(temp_jsonl_file):
    """Test that state_file=None works without creating any state file."""
    cleaner = DataCleaner(
        llm_backend=MockBackend(),
        file_path=temp_jsonl_file,
        chunk_size=10,
        state_file=None,
    )
    cleaner.run()

    # Should complete without error
    assert len(cleaner.functions) == 0


def test_state_file_updated_after_each_chunk(temp_multi_chunk_file, temp_state_file):
    """Test that state file is updated after each chunk completes."""
    cleaner = DataCleaner(
        llm_backend=MockBackend(),
        file_path=temp_multi_chunk_file,
        chunk_size=3,  # Should create multiple chunks
        state_file=temp_state_file,
    )
    cleaner.run()

    with open(temp_state_file) as f:
        state = json.load(f)

    # Should have completed all chunks
    assert state["last_completed_chunk"] == state["total_chunks"] - 1
    # total_chunks should be > 1 for this test to be meaningful
    assert state["total_chunks"] > 1

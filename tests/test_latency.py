"""Tests for latency metrics tracking."""

import time

import pytest

from recursive_cleaner import DataCleaner


class MockLLMWithDelay:
    """Mock LLM that introduces a controlled delay."""

    def __init__(self, delay_ms: float, responses: list[str]):
        self.delay_ms = delay_ms
        self.responses = iter(responses)
        self.call_count = 0

    def generate(self, prompt: str) -> str:
        self.call_count += 1
        time.sleep(self.delay_ms / 1000)
        return next(self.responses)


CLEAN_RESPONSE = '''
<cleaning_analysis>
  <issues_detected>
    <issue id="1" solved="true">Already clean</issue>
  </issues_detected>
  <chunk_status>clean</chunk_status>
</cleaning_analysis>
'''

FUNCTION_THEN_CLEAN = [
    '''
<cleaning_analysis>
  <issues_detected>
    <issue id="1" solved="false">Needs fixing</issue>
  </issues_detected>
  <function_to_generate>
    <name>fix_data</name>
    <docstring>Fixes the data.</docstring>
    <code>
```python
def fix_data(data):
    return data
```
    </code>
  </function_to_generate>
  <chunk_status>needs_more_work</chunk_status>
</cleaning_analysis>
''',
    CLEAN_RESPONSE,
]


def test_latency_stats_initialized(tmp_path):
    """Latency stats are initialized to correct defaults."""
    test_file = tmp_path / "test.jsonl"
    test_file.write_text('{"a": 1}\n')

    mock_llm = MockLLMWithDelay(0, [CLEAN_RESPONSE])
    cleaner = DataCleaner(
        llm_backend=mock_llm,
        file_path=str(test_file),
        chunk_size=10,
    )

    assert cleaner._latency_stats["call_count"] == 0
    assert cleaner._latency_stats["total_ms"] == 0.0
    assert cleaner._latency_stats["min_ms"] == float("inf")
    assert cleaner._latency_stats["max_ms"] == 0.0


def test_latency_tracked_on_llm_call(tmp_path):
    """Latency is tracked for each LLM call."""
    test_file = tmp_path / "test.jsonl"
    test_file.write_text('{"a": 1}\n')

    # 50ms delay per call
    mock_llm = MockLLMWithDelay(50, [CLEAN_RESPONSE])
    cleaner = DataCleaner(
        llm_backend=mock_llm,
        file_path=str(test_file),
        chunk_size=10,
    )
    cleaner.run()

    stats = cleaner._latency_stats
    assert stats["call_count"] == 1
    assert stats["total_ms"] >= 50  # At least 50ms
    assert stats["min_ms"] >= 50
    assert stats["max_ms"] >= 50


def test_latency_min_max_tracked_across_calls(tmp_path):
    """Min and max latency tracked correctly across multiple calls."""
    test_file = tmp_path / "test.jsonl"
    test_file.write_text('{"a": 1}\n{"a": 2}\n')

    # Two LLM calls (function + clean)
    mock_llm = MockLLMWithDelay(20, FUNCTION_THEN_CLEAN)
    cleaner = DataCleaner(
        llm_backend=mock_llm,
        file_path=str(test_file),
        chunk_size=10,
    )
    cleaner.run()

    stats = cleaner._latency_stats
    assert stats["call_count"] == 2
    assert stats["total_ms"] >= 40  # At least 2 * 20ms
    assert stats["min_ms"] >= 20
    assert stats["max_ms"] >= 20


def test_llm_call_event_emitted(tmp_path):
    """llm_call event is emitted with latency_ms."""
    test_file = tmp_path / "test.jsonl"
    test_file.write_text('{"a": 1}\n')

    events = []

    def track_events(e):
        events.append(e)

    mock_llm = MockLLMWithDelay(10, [CLEAN_RESPONSE])
    cleaner = DataCleaner(
        llm_backend=mock_llm,
        file_path=str(test_file),
        chunk_size=10,
        on_progress=track_events,
    )
    cleaner.run()

    llm_events = [e for e in events if e["type"] == "llm_call"]
    assert len(llm_events) == 1
    assert "latency_ms" in llm_events[0]
    assert llm_events[0]["latency_ms"] >= 10


def test_complete_event_includes_latency_stats(tmp_path):
    """Complete event includes latency_stats summary."""
    test_file = tmp_path / "test.jsonl"
    test_file.write_text('{"a": 1}\n')

    events = []

    def track_events(e):
        events.append(e)

    mock_llm = MockLLMWithDelay(10, [CLEAN_RESPONSE])
    cleaner = DataCleaner(
        llm_backend=mock_llm,
        file_path=str(test_file),
        chunk_size=10,
        on_progress=track_events,
    )
    cleaner.run()

    complete_events = [e for e in events if e["type"] == "complete"]
    assert len(complete_events) == 1

    stats = complete_events[0]["latency_stats"]
    assert "call_count" in stats
    assert "total_ms" in stats
    assert "min_ms" in stats
    assert "max_ms" in stats
    assert "avg_ms" in stats
    assert stats["call_count"] == 1


def test_latency_avg_calculated_correctly(tmp_path):
    """Average latency is calculated correctly."""
    test_file = tmp_path / "test.jsonl"
    test_file.write_text('{"a": 1}\n')

    mock_llm = MockLLMWithDelay(30, FUNCTION_THEN_CLEAN)
    cleaner = DataCleaner(
        llm_backend=mock_llm,
        file_path=str(test_file),
        chunk_size=10,
    )
    cleaner.run()

    summary = cleaner._get_latency_summary()
    assert summary["call_count"] == 2
    # Avg should be close to 30ms (each call is ~30ms)
    assert summary["avg_ms"] >= 30


def test_latency_summary_zero_calls():
    """Latency summary handles zero calls gracefully."""
    test_file = "/nonexistent"  # Won't be used

    class DummyLLM:
        def generate(self, prompt: str) -> str:
            return ""

    cleaner = DataCleaner(
        llm_backend=DummyLLM(),
        file_path=test_file,
        chunk_size=10,
    )

    summary = cleaner._get_latency_summary()
    assert summary["call_count"] == 0
    assert summary["avg_ms"] == 0.0
    assert summary["min_ms"] == 0.0

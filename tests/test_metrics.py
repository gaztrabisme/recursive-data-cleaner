"""Tests for quality metrics functionality."""

import pytest
from recursive_cleaner import DataCleaner, QualityMetrics, compare_quality, measure_quality
from recursive_cleaner.metrics import load_structured_data


class MockLLM:
    """Mock LLM that returns predefined responses."""

    def __init__(self, responses: list[str]):
        self.responses = iter(responses)
        self.calls = []

    def generate(self, prompt: str) -> str:
        self.calls.append(prompt)
        return next(self.responses)


# Test measure_quality function

def test_measure_quality_counts_nulls():
    """measure_quality correctly counts null values."""
    data = [
        {"name": "Alice", "age": 30},
        {"name": None, "age": 25},
        {"name": "Bob", "age": None},
        {"name": None, "age": None},
    ]
    metrics = measure_quality(data)
    assert metrics.null_count == 4


def test_measure_quality_counts_empty_strings():
    """measure_quality correctly counts empty strings."""
    data = [
        {"name": "Alice", "email": "alice@test.com"},
        {"name": "", "email": ""},
        {"name": "Bob", "email": ""},
    ]
    metrics = measure_quality(data)
    assert metrics.empty_string_count == 3


def test_measure_quality_tracks_unique_values_per_field():
    """measure_quality tracks unique values for each field."""
    data = [
        {"status": "active", "type": "A"},
        {"status": "pending", "type": "B"},
        {"status": "active", "type": "A"},  # duplicates
        {"status": "churned", "type": "C"},
    ]
    metrics = measure_quality(data)
    assert metrics.unique_values["status"] == 3  # active, pending, churned
    assert metrics.unique_values["type"] == 3  # A, B, C


def test_measure_quality_total_records():
    """measure_quality tracks total record count."""
    data = [{"a": 1}, {"a": 2}, {"a": 3}]
    metrics = measure_quality(data)
    assert metrics.total_records == 3


def test_measure_quality_empty_data():
    """measure_quality handles empty data list."""
    metrics = measure_quality([])
    assert metrics.null_count == 0
    assert metrics.empty_string_count == 0
    assert metrics.unique_values == {}
    assert metrics.total_records == 0


def test_measure_quality_all_nulls():
    """measure_quality handles data with all null values."""
    data = [
        {"a": None, "b": None},
        {"a": None, "b": None},
    ]
    metrics = measure_quality(data)
    assert metrics.null_count == 4
    assert metrics.total_records == 2


def test_measure_quality_handles_complex_values():
    """measure_quality handles nested dicts and lists in values."""
    data = [
        {"config": {"nested": "value"}, "tags": ["a", "b"]},
        {"config": {"nested": "value"}, "tags": ["c", "d"]},  # same config
        {"config": {"other": "data"}, "tags": ["a", "b"]},  # same tags
    ]
    metrics = measure_quality(data)
    # Should count unique JSON representations
    assert metrics.unique_values["config"] == 2  # two distinct configs
    assert metrics.unique_values["tags"] == 2  # two distinct tag lists


def test_measure_quality_timestamp_set():
    """measure_quality sets a timestamp."""
    metrics = measure_quality([{"a": 1}])
    assert metrics.timestamp is not None
    assert len(metrics.timestamp) > 0


# Test compare_quality function

def test_compare_quality_computes_null_reduction():
    """compare_quality computes null reduction percentage."""
    before = QualityMetrics(null_count=100, empty_string_count=0, total_records=50)
    after = QualityMetrics(null_count=20, empty_string_count=0, total_records=50)
    result = compare_quality(before, after)
    assert result["null_count_before"] == 100
    assert result["null_count_after"] == 20
    assert result["null_reduction_pct"] == 80.0


def test_compare_quality_computes_empty_string_reduction():
    """compare_quality computes empty string reduction percentage."""
    before = QualityMetrics(null_count=0, empty_string_count=50, total_records=50)
    after = QualityMetrics(null_count=0, empty_string_count=10, total_records=50)
    result = compare_quality(before, after)
    assert result["empty_string_before"] == 50
    assert result["empty_string_after"] == 10
    assert result["empty_string_reduction_pct"] == 80.0


def test_compare_quality_handles_zero_before():
    """compare_quality handles zero initial counts (no division by zero)."""
    before = QualityMetrics(null_count=0, empty_string_count=0, total_records=50)
    after = QualityMetrics(null_count=5, empty_string_count=3, total_records=50)
    result = compare_quality(before, after)
    assert result["null_reduction_pct"] == 0.0
    assert result["empty_string_reduction_pct"] == 0.0


def test_compare_quality_tracks_unique_value_changes():
    """compare_quality tracks unique value changes per field."""
    before = QualityMetrics(
        null_count=0,
        empty_string_count=0,
        unique_values={"status": 10, "type": 5},
        total_records=100,
    )
    after = QualityMetrics(
        null_count=0,
        empty_string_count=0,
        unique_values={"status": 3, "type": 5, "new_field": 2},
        total_records=100,
    )
    result = compare_quality(before, after)
    assert result["unique_values_by_field"]["status"] == {"before": 10, "after": 3}
    assert result["unique_values_by_field"]["type"] == {"before": 5, "after": 5}
    assert result["unique_values_by_field"]["new_field"] == {"before": 0, "after": 2}


# Test load_structured_data function

def test_load_structured_data_jsonl(tmp_path):
    """load_structured_data loads JSONL files correctly."""
    test_file = tmp_path / "test.jsonl"
    test_file.write_text('{"name": "Alice"}\n{"name": "Bob"}\n')
    data = load_structured_data(str(test_file))
    assert len(data) == 2
    assert data[0]["name"] == "Alice"
    assert data[1]["name"] == "Bob"


def test_load_structured_data_json_array(tmp_path):
    """load_structured_data loads JSON array files correctly."""
    test_file = tmp_path / "test.json"
    test_file.write_text('[{"name": "Alice"}, {"name": "Bob"}]')
    data = load_structured_data(str(test_file))
    assert len(data) == 2
    assert data[0]["name"] == "Alice"


def test_load_structured_data_json_object(tmp_path):
    """load_structured_data loads JSON object as single-item list."""
    test_file = tmp_path / "test.json"
    test_file.write_text('{"name": "Alice", "age": 30}')
    data = load_structured_data(str(test_file))
    assert len(data) == 1
    assert data[0]["name"] == "Alice"


def test_load_structured_data_unsupported_format(tmp_path):
    """load_structured_data returns empty list for unsupported formats."""
    test_file = tmp_path / "test.txt"
    test_file.write_text("This is plain text")
    data = load_structured_data(str(test_file))
    assert data == []


# Test DataCleaner integration with track_metrics

RESPONSE_CLEAN = '''
<cleaning_analysis>
  <issues_detected>
    <issue id="1" solved="true">All clean</issue>
  </issues_detected>
  <chunk_status>clean</chunk_status>
</cleaning_analysis>
'''


def test_cleaner_track_metrics_populates_metrics_before(tmp_path):
    """DataCleaner with track_metrics=True populates metrics_before."""
    test_file = tmp_path / "test.jsonl"
    test_file.write_text('{"name": "Alice", "age": null}\n{"name": "", "age": 30}\n')

    mock_llm = MockLLM([RESPONSE_CLEAN])
    cleaner = DataCleaner(
        llm_backend=mock_llm,
        file_path=str(test_file),
        chunk_size=10,
        track_metrics=True,
        validate_runtime=False,
    )
    cleaner.run()

    assert cleaner.metrics_before is not None
    assert cleaner.metrics_before.null_count == 1  # age: null
    assert cleaner.metrics_before.empty_string_count == 1  # name: ""
    assert cleaner.metrics_before.total_records == 2


def test_cleaner_track_metrics_false_no_metrics(tmp_path):
    """DataCleaner with track_metrics=False does not populate metrics."""
    test_file = tmp_path / "test.jsonl"
    test_file.write_text('{"name": "Alice"}\n')

    mock_llm = MockLLM([RESPONSE_CLEAN])
    cleaner = DataCleaner(
        llm_backend=mock_llm,
        file_path=str(test_file),
        chunk_size=10,
        track_metrics=False,
        validate_runtime=False,
    )
    cleaner.run()

    assert cleaner.metrics_before is None
    assert cleaner.metrics_after is None


def test_get_improvement_report_returns_none_when_not_tracking(tmp_path):
    """get_improvement_report returns None when track_metrics=False."""
    test_file = tmp_path / "test.jsonl"
    test_file.write_text('{"name": "Alice"}\n')

    mock_llm = MockLLM([RESPONSE_CLEAN])
    cleaner = DataCleaner(
        llm_backend=mock_llm,
        file_path=str(test_file),
        chunk_size=10,
        track_metrics=False,
        validate_runtime=False,
    )
    cleaner.run()

    assert cleaner.get_improvement_report() is None


def test_get_improvement_report_returns_partial_when_no_after(tmp_path):
    """get_improvement_report returns partial report when metrics_after is None."""
    test_file = tmp_path / "test.jsonl"
    test_file.write_text('{"name": null}\n{"name": ""}\n')

    mock_llm = MockLLM([RESPONSE_CLEAN])
    cleaner = DataCleaner(
        llm_backend=mock_llm,
        file_path=str(test_file),
        chunk_size=10,
        track_metrics=True,
        validate_runtime=False,
    )
    cleaner.run()

    report = cleaner.get_improvement_report()
    assert report is not None
    assert report["status"] == "incomplete"
    assert report["metrics_before"]["null_count"] == 1
    assert report["metrics_before"]["empty_string_count"] == 1
    assert report["metrics_after"] is None


def test_get_improvement_report_with_both_metrics(tmp_path):
    """get_improvement_report returns full comparison when both metrics exist."""
    test_file = tmp_path / "test.jsonl"
    test_file.write_text('{"name": "Alice"}\n')

    mock_llm = MockLLM([RESPONSE_CLEAN])
    cleaner = DataCleaner(
        llm_backend=mock_llm,
        file_path=str(test_file),
        chunk_size=10,
        track_metrics=True,
        validate_runtime=False,
    )
    cleaner.run()

    # Manually set metrics_after to simulate post-cleaning measurement
    cleaner.metrics_after = QualityMetrics(
        null_count=0,
        empty_string_count=0,
        unique_values={"name": 1},
        total_records=1,
    )

    report = cleaner.get_improvement_report()
    assert report is not None
    assert "null_count_before" in report
    assert "null_count_after" in report
    assert "null_reduction_pct" in report


def test_cleaner_text_mode_no_metrics(tmp_path):
    """DataCleaner in text mode does not track metrics (structured only)."""
    test_file = tmp_path / "test.txt"
    test_file.write_text("This is plain text content.")

    mock_llm = MockLLM([RESPONSE_CLEAN])
    cleaner = DataCleaner(
        llm_backend=mock_llm,
        file_path=str(test_file),
        chunk_size=1000,
        track_metrics=True,  # Even with True, text mode shouldn't measure
        validate_runtime=False,
        mode="text",
    )
    cleaner.run()

    # Text mode should not populate metrics
    assert cleaner.metrics_before is None

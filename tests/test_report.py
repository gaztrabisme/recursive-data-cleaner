"""Tests for cleaning report generation."""

import pytest

from recursive_cleaner import DataCleaner
from recursive_cleaner.report import generate_report, write_report


def test_generate_report_basic():
    """Generate report with basic info."""
    report = generate_report(
        file_path="test.jsonl",
        total_chunks=5,
        functions=[],
    )

    assert "# Data Cleaning Report" in report
    assert "test.jsonl" in report
    assert "Chunks processed**: 5" in report
    assert "Functions generated**: 0" in report


def test_generate_report_with_functions():
    """Generate report with function list."""
    functions = [
        {"name": "fix_phones", "docstring": "Normalize phone numbers to E.164."},
        {"name": "fix_dates", "docstring": "Convert dates to ISO 8601 format."},
    ]

    report = generate_report(
        file_path="data.jsonl",
        total_chunks=10,
        functions=functions,
    )

    assert "## Functions Generated" in report
    assert "`fix_phones`" in report
    assert "Normalize phone numbers" in report
    assert "`fix_dates`" in report
    assert "ISO 8601" in report


def test_generate_report_with_latency():
    """Generate report with latency stats."""
    report = generate_report(
        file_path="data.jsonl",
        total_chunks=3,
        functions=[],
        latency_stats={
            "call_count": 5,
            "total_ms": 1500.0,
            "avg_ms": 300.0,
        },
    )

    assert "Total LLM time**: 1500ms" in report
    assert "LLM calls**: 5" in report


def test_generate_report_with_quality_metrics():
    """Generate report with before/after quality metrics."""
    report = generate_report(
        file_path="data.jsonl",
        total_chunks=3,
        functions=[],
        quality_before={"null_count": 100, "empty_string_count": 50},
        quality_after={"null_count": 10, "empty_string_count": 0},
    )

    assert "## Quality Metrics" in report
    assert "Null values" in report
    assert "| 100 |" in report
    assert "| 10 |" in report
    assert "-90%" in report  # 100 -> 10 is -90%
    assert "-100%" in report  # 50 -> 0 is -100%


def test_generate_report_handles_multiline_docstring():
    """First line of docstring used in table."""
    functions = [
        {
            "name": "complex_func",
            "docstring": "First line summary.\n\nMore details here.\nAnd more.",
        },
    ]

    report = generate_report(
        file_path="data.jsonl",
        total_chunks=1,
        functions=functions,
    )

    assert "First line summary." in report
    assert "More details here" not in report


def test_generate_report_escapes_pipe_in_docstring():
    """Pipe characters in docstring are escaped for markdown table."""
    functions = [
        {
            "name": "func_with_pipe",
            "docstring": "Handle values like a|b|c.",
        },
    ]

    report = generate_report(
        file_path="data.jsonl",
        total_chunks=1,
        functions=functions,
    )

    # Pipe should be escaped
    assert "a\\|b\\|c" in report


def test_write_report_creates_file(tmp_path):
    """write_report creates markdown file."""
    report_path = tmp_path / "report.md"

    write_report(
        report_path=str(report_path),
        file_path="test.jsonl",
        total_chunks=3,
        functions=[{"name": "f1", "docstring": "Does stuff"}],
    )

    assert report_path.exists()
    content = report_path.read_text()
    assert "# Data Cleaning Report" in content
    assert "f1" in content


def test_cleaner_writes_report(tmp_path):
    """DataCleaner writes report when report_path set."""
    test_file = tmp_path / "test.jsonl"
    test_file.write_text('{"a": 1}\n')
    report_file = tmp_path / "custom_report.md"

    class MockLLM:
        def generate(self, prompt: str) -> str:
            return '''
<cleaning_analysis>
  <issues_detected>
    <issue id="1" solved="true">Clean</issue>
  </issues_detected>
  <chunk_status>clean</chunk_status>
</cleaning_analysis>
'''

    cleaner = DataCleaner(
        llm_backend=MockLLM(),
        file_path=str(test_file),
        chunk_size=10,
        report_path=str(report_file),
    )
    cleaner.run()

    assert report_file.exists()
    content = report_file.read_text()
    assert "test.jsonl" in content


def test_cleaner_no_report_when_none(tmp_path):
    """DataCleaner doesn't write report when report_path is None."""
    test_file = tmp_path / "test.jsonl"
    test_file.write_text('{"a": 1}\n')

    class MockLLM:
        def generate(self, prompt: str) -> str:
            return '''
<cleaning_analysis>
  <issues_detected>
    <issue id="1" solved="true">Clean</issue>
  </issues_detected>
  <chunk_status>clean</chunk_status>
</cleaning_analysis>
'''

    cleaner = DataCleaner(
        llm_backend=MockLLM(),
        file_path=str(test_file),
        chunk_size=10,
        report_path=None,
    )
    cleaner.run()

    # Default report file should not exist
    assert not (tmp_path / "cleaning_report.md").exists()

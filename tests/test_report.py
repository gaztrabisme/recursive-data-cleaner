"""Tests for cleaning report generation."""

import pytest

from recursive_cleaner import DataCleaner
from recursive_cleaner.report import capture_transformations, generate_report, write_report


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


# Tests for capture_transformations


def test_capture_transformations_returns_changed_records():
    """capture_transformations returns before/after for changed records."""
    code = '''
def fix_phone(record):
    record["phone"] = record.get("phone", "").replace("-", "")
    return record
'''
    sample = [{"phone": "555-1234"}, {"phone": "555-5678"}]
    examples = capture_transformations(code, "fix_phone", sample)
    assert len(examples) == 2
    assert examples[0]["before"] == {"phone": "555-1234"}
    assert examples[0]["after"] == {"phone": "5551234"}


def test_capture_transformations_skips_unchanged_records():
    """capture_transformations omits records that don't change."""
    code = '''
def fix_typo(record):
    if record.get("status") == "actve":
        record["status"] = "active"
    return record
'''
    sample = [{"status": "active"}, {"status": "actve"}, {"status": "pending"}]
    examples = capture_transformations(code, "fix_typo", sample)
    assert len(examples) == 1
    assert examples[0]["before"]["status"] == "actve"
    assert examples[0]["after"]["status"] == "active"


def test_capture_transformations_respects_max_examples():
    """capture_transformations limits to max_examples."""
    code = '''
def add_flag(record):
    record["_flag"] = True
    return record
'''
    sample = [{"id": i} for i in range(10)]
    examples = capture_transformations(code, "add_flag", sample, max_examples=3)
    assert len(examples) == 3


def test_capture_transformations_empty_sample():
    """capture_transformations returns empty list for empty sample."""
    examples = capture_transformations("def f(r): return r", "f", [])
    assert examples == []


def test_capture_transformations_bad_code():
    """capture_transformations returns empty list for unparseable code."""
    examples = capture_transformations("def broken(", "broken", [{"a": 1}])
    assert examples == []


def test_capture_transformations_wrong_name():
    """capture_transformations returns empty list for wrong function name."""
    examples = capture_transformations("def real(r): return r", "wrong", [{"a": 1}])
    assert examples == []


# Tests for report rendering with samples


def test_generate_report_with_samples():
    """generate_report renders sample transformations."""
    functions = [
        {
            "name": "fix_phones",
            "docstring": "Normalize phone numbers.",
            "samples": [
                {"before": {"phone": "555-1234"}, "after": {"phone": "5551234"}},
            ],
        },
    ]
    report = generate_report(
        file_path="data.jsonl",
        total_chunks=1,
        functions=functions,
    )
    assert "### Sample Transformations" in report
    assert "**`fix_phones`**" in report
    assert "`phone`" in report
    assert "'555-1234'" in report
    assert "'5551234'" in report


def test_generate_report_no_samples_no_section():
    """generate_report omits sample section when no samples exist."""
    functions = [
        {"name": "f1", "docstring": "Does stuff"},
    ]
    report = generate_report(
        file_path="data.jsonl",
        total_chunks=1,
        functions=functions,
    )
    assert "### Sample Transformations" not in report


def test_generate_report_shows_only_changed_fields():
    """generate_report only shows fields that changed."""
    functions = [
        {
            "name": "fix_status",
            "docstring": "Fix status typos.",
            "samples": [
                {
                    "before": {"name": "Alice", "status": "actve"},
                    "after": {"name": "Alice", "status": "active"},
                },
            ],
        },
    ]
    report = generate_report(
        file_path="data.jsonl",
        total_chunks=1,
        functions=functions,
    )
    assert "`status`" in report
    assert "`name`" not in report.split("Sample Transformations")[1]


def test_generate_report_shows_new_fields():
    """generate_report shows fields added by the function."""
    functions = [
        {
            "name": "add_flag",
            "docstring": "Add processing flag.",
            "samples": [
                {
                    "before": {"id": 1},
                    "after": {"id": 1, "_processed": True},
                },
            ],
        },
    ]
    report = generate_report(
        file_path="data.jsonl",
        total_chunks=1,
        functions=functions,
    )
    assert "`_processed`" in report
    assert "None" in report  # before value is None (key didn't exist)
    assert "True" in report  # after value


# Integration: cleaner captures samples


def test_cleaner_captures_samples_in_functions(tmp_path):
    """DataCleaner captures before/after samples when accepting functions."""
    test_file = tmp_path / "test.jsonl"
    test_file.write_text('{"phone": "555-1234"}\n{"phone": "555-5678"}\n')

    class MockLLM:
        def __init__(self):
            self.call_count = 0

        def generate(self, prompt: str) -> str:
            self.call_count += 1
            if self.call_count == 1:
                return '''
<cleaning_analysis>
  <issues_detected>
    <issue id="1" solved="false">Phones need normalization</issue>
  </issues_detected>
  <function_to_generate>
    <name>fix_phones</name>
    <docstring>Remove dashes from phone numbers.</docstring>
    <code>
```python
def fix_phones(record):
    phone = record.get("phone", "")
    if isinstance(phone, str):
        record["phone"] = phone.replace("-", "")
    return record
```
    </code>
  </function_to_generate>
  <chunk_status>needs_more_work</chunk_status>
</cleaning_analysis>
'''
            return '''
<cleaning_analysis>
  <issues_detected>
    <issue id="1" solved="true">Phones normalized</issue>
  </issues_detected>
  <chunk_status>clean</chunk_status>
</cleaning_analysis>
'''

    cleaner = DataCleaner(
        llm_backend=MockLLM(),
        file_path=str(test_file),
        chunk_size=10,
    )
    cleaner.run()

    assert len(cleaner.functions) == 1
    samples = cleaner.functions[0].get("samples", [])
    assert len(samples) >= 1
    assert samples[0]["before"]["phone"] == "555-1234"
    assert samples[0]["after"]["phone"] == "5551234"

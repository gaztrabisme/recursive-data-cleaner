"""Tests for the eval harness (benchmarks/eval/run_eval.py)."""

import copy
import json
import sys
from pathlib import Path

import pytest

# Make benchmarks/eval importable
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "benchmarks" / "eval"))
from run_eval import (
    check_assertion,
    extract_numeric,
    format_markdown_report,
    load_data,
    load_golden,
    model_slug,
    run_eval,
)

# --- Tiny inline dataset and cleaning function ---

SAMPLE_DATA = [
    {"id": 1, "name": "Alice", "phone": "(415) 555-1234", "status": "actve", "weight": "11.5 lbs"},
    {"id": 2, "name": "Bob", "phone": "+14155551234", "status": "active", "weight": "5.20 kg"},
    {"id": 3, "name": " Carol ", "phone": "4155551234", "status": "ACTIVE", "weight": "5200 g"},
]


def trivial_clean(record):
    """A trivial cleaning function for testing."""
    r = copy.deepcopy(record)
    r["name"] = " ".join(r["name"].split())
    r["status"] = r["status"].lower().replace("actve", "active")
    digits = "".join(c for c in r["phone"] if c.isdigit())
    if len(digits) == 10:
        r["phone"] = f"+1{digits}"
    w = r["weight"]
    if "lbs" in w:
        val = float(w.replace("lbs", "").strip())
        r["weight"] = f"{val * 0.453592:.2f} kg"
    elif w.endswith("g") and "kg" not in w:
        val = float(w.replace("g", "").strip())
        r["weight"] = f"{val / 1000:.2f} kg"
    return r


# --- check_assertion ---


class TestCheckAssertion:
    def test_exact_match_pass(self):
        assert check_assertion("active", "active") is True

    def test_exact_match_fail(self):
        assert check_assertion("actve", "active") is False

    def test_exact_match_list(self):
        assert check_assertion(["a", "b"], ["a", "b"]) is True

    def test_exact_match_null(self):
        assert check_assertion(None, None) is True

    def test_numeric_close_pass(self):
        assert check_assertion("5.22 kg", "5.22 kg", "numeric_close") is True

    def test_numeric_close_within_tolerance(self):
        assert check_assertion("5.216 kg", "5.22 kg", "numeric_close") is True

    def test_numeric_close_fail(self):
        assert check_assertion("6.00 kg", "5.22 kg", "numeric_close") is False

    def test_numeric_close_pure_numbers(self):
        assert check_assertion(1234.56, "1234.56", "numeric_close") is True

    def test_contains_pass(self):
        assert check_assertion("New signup from Facebook campaign", "Facebook", "contains") is True

    def test_contains_fail(self):
        assert check_assertion("some text", "missing", "contains") is False


# --- extract_numeric ---


class TestExtractNumeric:
    def test_int(self):
        assert extract_numeric(42) == 42.0

    def test_float(self):
        assert extract_numeric(3.14) == 3.14

    def test_string_number(self):
        assert extract_numeric("5.22") == 5.22

    def test_string_with_suffix(self):
        assert extract_numeric("5.22 kg") == 5.22

    def test_string_with_prefix(self):
        assert extract_numeric("$1234.56") == 1234.56

    def test_non_numeric(self):
        assert extract_numeric("hello") is None

    def test_none(self):
        assert extract_numeric(None) is None


# --- run_eval ---


class TestRunEval:
    def test_exact_match_pass(self):
        assertions = [
            {"record_index": 0, "field": "phone", "expected": "+14155551234", "issue_type": "phone_format"},
        ]
        results = run_eval(SAMPLE_DATA, trivial_clean, assertions)
        assert results["passed"] == 1
        assert results["total"] == 1
        assert len(results["failures"]) == 0

    def test_exact_match_fail(self):
        assertions = [
            {"record_index": 0, "field": "status", "expected": "pending", "issue_type": "enum_typo"},
        ]
        results = run_eval(SAMPLE_DATA, trivial_clean, assertions)
        assert results["passed"] == 0
        assert results["failures"][0]["actual"] == "active"

    def test_numeric_close_match(self):
        assertions = [
            {"record_index": 0, "field": "weight", "expected": "5.22 kg", "issue_type": "weight_unit", "match_mode": "numeric_close"},
        ]
        results = run_eval(SAMPLE_DATA, trivial_clean, assertions)
        # 11.5 * 0.453592 = 5.216308 -> "5.22 kg"
        assert results["passed"] == 1

    def test_numeric_close_fail(self):
        assertions = [
            {"record_index": 0, "field": "weight", "expected": "10.00 kg", "issue_type": "weight_unit", "match_mode": "numeric_close"},
        ]
        results = run_eval(SAMPLE_DATA, trivial_clean, assertions)
        assert results["passed"] == 0

    def test_aggregate_by_issue_type(self):
        assertions = [
            {"record_index": 0, "field": "phone", "expected": "+14155551234", "issue_type": "phone_format"},
            {"record_index": 1, "field": "phone", "expected": "+14155551234", "issue_type": "phone_format"},
            {"record_index": 0, "field": "status", "expected": "active", "issue_type": "enum_typo"},
        ]
        results = run_eval(SAMPLE_DATA, trivial_clean, assertions)
        assert results["by_issue_type"]["phone_format"]["total"] == 2
        assert results["by_issue_type"]["phone_format"]["passed"] == 2
        assert results["by_issue_type"]["enum_typo"]["total"] == 1
        assert results["by_issue_type"]["enum_typo"]["passed"] == 1

    def test_aggregate_by_field(self):
        assertions = [
            {"record_index": 0, "field": "phone", "expected": "+14155551234", "issue_type": "phone_format"},
            {"record_index": 0, "field": "status", "expected": "active", "issue_type": "enum_typo"},
        ]
        results = run_eval(SAMPLE_DATA, trivial_clean, assertions)
        assert results["by_field"]["phone"]["total"] == 1
        assert results["by_field"]["phone"]["passed"] == 1
        assert results["by_field"]["status"]["total"] == 1
        assert results["by_field"]["status"]["passed"] == 1

    def test_missing_record_index(self):
        assertions = [
            {"record_index": 99, "field": "phone", "expected": "+14155551234", "issue_type": "phone_format"},
        ]
        results = run_eval(SAMPLE_DATA, trivial_clean, assertions)
        assert results["passed"] == 0
        assert len(results["failures"]) == 1
        assert "out of range" in results["failures"][0].get("error", "")

    def test_missing_field(self):
        assertions = [
            {"record_index": 0, "field": "nonexistent", "expected": "foo", "issue_type": "test"},
        ]
        results = run_eval(SAMPLE_DATA, trivial_clean, assertions)
        assert results["passed"] == 0
        assert "not found" in results["failures"][0].get("error", "")

    def test_already_clean_assertion(self):
        """Values that are already correct should still pass."""
        assertions = [
            {"record_index": 1, "field": "phone", "expected": "+14155551234", "issue_type": "phone_format"},
            {"record_index": 1, "field": "status", "expected": "active", "issue_type": "enum_typo"},
        ]
        results = run_eval(SAMPLE_DATA, trivial_clean, assertions)
        assert results["passed"] == 2
        assert len(results["failures"]) == 0


# --- File loading ---


class TestLoadFiles:
    def test_load_data(self, tmp_path):
        data_file = tmp_path / "data.jsonl"
        data_file.write_text('{"a": 1}\n{"a": 2}\n')
        data = load_data(str(data_file))
        assert len(data) == 2
        assert data[0]["a"] == 1

    def test_load_golden(self, tmp_path):
        golden_file = tmp_path / "golden.jsonl"
        golden_file.write_text(
            '{"record_index": 0, "field": "a", "expected": 1, "issue_type": "test"}\n'
        )
        assertions = load_golden(str(golden_file))
        assert len(assertions) == 1
        assert assertions[0]["field"] == "a"


# --- Helpers ---


class TestModelSlug:
    def test_standard_name(self):
        assert model_slug("path/to/cleaning_functions_Qwen3-14B.py") == "Qwen3-14B"

    def test_plain_name(self):
        assert model_slug("cleaning_functions.py") == "cleaning_functions"


class TestMarkdownReport:
    def test_report_contains_score(self):
        results = {
            "total": 10,
            "passed": 7,
            "score_pct": 70.0,
            "by_issue_type": {"test": {"total": 10, "passed": 7, "score_pct": 70.0}},
            "by_field": {"field1": {"total": 10, "passed": 7, "score_pct": 70.0}},
            "failures": [],
        }
        report = format_markdown_report("test-model", results)
        assert "70.0%" in report
        assert "test-model" in report

    def test_report_includes_failures(self):
        results = {
            "total": 1,
            "passed": 0,
            "score_pct": 0.0,
            "by_issue_type": {"test": {"total": 1, "passed": 0, "score_pct": 0.0}},
            "by_field": {"f": {"total": 1, "passed": 0, "score_pct": 0.0}},
            "failures": [
                {"record_index": 0, "field": "f", "expected": "a", "actual": "b", "issue_type": "test"},
            ],
        }
        report = format_markdown_report("model", results)
        assert "Failures" in report
        assert "expected `a`" in report

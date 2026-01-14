import pytest
from recursive_cleaner import build_context


def test_build_context_empty():
    """Empty function list returns placeholder."""
    result = build_context([])
    assert result == "(No functions generated yet)"


def test_build_context_single_function():
    """Single function is included."""
    functions = [{"name": "clean_dates", "docstring": "Normalizes dates to ISO 8601."}]
    result = build_context(functions)
    assert "## clean_dates" in result
    assert "Normalizes dates to ISO 8601." in result


def test_build_context_multiple_functions():
    """Multiple functions included in order."""
    functions = [
        {"name": "func_a", "docstring": "Does A"},
        {"name": "func_b", "docstring": "Does B"},
        {"name": "func_c", "docstring": "Does C"},
    ]
    result = build_context(functions)
    assert "## func_a" in result
    assert "## func_b" in result
    assert "## func_c" in result
    # Check order - func_a should come before func_b
    assert result.index("func_a") < result.index("func_b")
    assert result.index("func_b") < result.index("func_c")


def test_build_context_respects_budget():
    """Functions are evicted when over budget."""
    functions = [{"name": f"func_{i}", "docstring": "x" * 500} for i in range(20)]
    result = build_context(functions, max_chars=2000)
    assert len(result) <= 2000


def test_build_context_keeps_most_recent():
    """FIFO eviction keeps most recent functions."""
    functions = [{"name": f"func_{i}", "docstring": "x" * 500} for i in range(20)]
    result = build_context(functions, max_chars=2000)
    # Most recent (func_19) should be included
    assert "func_19" in result
    # Oldest (func_0) should be evicted
    assert "func_0" not in result


def test_build_context_exact_budget():
    """Handles edge case where functions exactly fit budget."""
    functions = [
        {"name": "a", "docstring": "test"},
        {"name": "b", "docstring": "test"},
    ]
    # Each entry is "## a\ntest\n\n" = 12 chars, "## b\ntest\n\n" = 12 chars = 24 total
    result = build_context(functions, max_chars=24)
    assert "## a" in result
    assert "## b" in result


def test_build_context_budget_too_small():
    """When budget is too small for any function, returns placeholder."""
    functions = [{"name": "long_function_name", "docstring": "A" * 100}]
    result = build_context(functions, max_chars=10)
    assert result == "(No functions generated yet)"

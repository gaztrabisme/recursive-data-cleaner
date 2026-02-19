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


# --- Relevance-filtered context tests ---


def test_relevance_prefers_matching_functions():
    """Relevant functions are included over recent irrelevant ones under budget pressure."""
    # Old function about phones, newer filler functions, chunk mentions phones
    functions = [
        {"name": "normalize_phone_numbers", "docstring": "Normalize phone numbers to E.164 format."},
        *[{"name": f"filler_{i}", "docstring": "Handles unrelated filler processing."} for i in range(10)],
    ]
    chunk = '{"phone": "555-1234", "name": "Alice"}'
    # Budget only fits ~3 functions
    result = build_context(functions, max_chars=300, chunk=chunk)
    # The phone function should be included despite being oldest
    assert "normalize_phone_numbers" in result


def test_relevance_preserves_generation_order():
    """Selected functions appear in their original generation order, not relevance order."""
    functions = [
        {"name": "normalize_dates", "docstring": "Fix date formats to ISO 8601."},
        {"name": "clean_emails", "docstring": "Validate and lowercase email addresses."},
        {"name": "fix_phone_numbers", "docstring": "Normalize phone numbers."},
    ]
    chunk = '{"phone": "555-1234", "date": "2024-01-01", "email": "test@example.com"}'
    result = build_context(functions, max_chars=8000, chunk=chunk)
    # All included, and in generation order
    assert result.index("normalize_dates") < result.index("clean_emails")
    assert result.index("clean_emails") < result.index("fix_phone_numbers")


def test_relevance_fallback_to_fifo_without_chunk():
    """Without chunk parameter, behavior is identical to FIFO."""
    functions = [{"name": f"func_{i}", "docstring": "x" * 500} for i in range(20)]
    result_no_chunk = build_context(functions, max_chars=2000)
    result_empty_chunk = build_context(functions, max_chars=2000, chunk="")
    assert result_no_chunk == result_empty_chunk
    # Most recent kept, oldest evicted (FIFO)
    assert "func_19" in result_no_chunk
    assert "func_0" not in result_no_chunk


def test_relevance_skips_irrelevant_to_fit_relevant():
    """Under budget pressure, irrelevant functions are dropped to make room for relevant ones."""
    functions = [
        {"name": "normalize_dates", "docstring": "Fix date formats to ISO 8601."},
        {"name": "unrelated_alpha", "docstring": "Handles alpha channel processing for images."},
        {"name": "unrelated_beta", "docstring": "Handles beta coefficient calculations."},
        {"name": "fix_phone_numbers", "docstring": "Normalize phone numbers to E.164."},
    ]
    # Chunk only mentions dates and phones
    chunk = '{"phone": "555-1234", "date": "Jan 1 2024"}'
    # Budget fits exactly the 2 relevant functions (~107 chars) but not a third (~165)
    result = build_context(functions, max_chars=120, chunk=chunk)
    assert "normalize_dates" in result
    assert "fix_phone_numbers" in result
    assert "unrelated_alpha" not in result
    assert "unrelated_beta" not in result


def test_relevance_with_text_mode_chunk():
    """Relevance works with prose text chunks, not just structured data."""
    functions = [
        {"name": "normalize_dates", "docstring": "Convert dates to ISO 8601 format."},
        {"name": "fix_currency", "docstring": "Standardize currency amounts to USD decimal."},
        {"name": "clean_whitespace", "docstring": "Remove extra whitespace and normalize spacing."},
    ]
    chunk = "The invoice dated January 15th shows $1,234.56 in USD currency."
    result = build_context(functions, max_chars=8000, chunk=chunk)
    # Both date and currency functions should be included
    assert "normalize_dates" in result
    assert "fix_currency" in result

"""Tests for dependency resolution."""

import ast
import pytest
from pathlib import Path

from recursive_cleaner.dependencies import detect_calls, resolve_dependencies
from recursive_cleaner.output import write_cleaning_file


class TestDetectCalls:
    """Tests for detect_calls function."""

    def test_detects_simple_call(self):
        """Detect a simple function call."""
        code = """
def func_a(data):
    return func_b(data)
"""
        known = {"func_b", "func_c"}
        calls = detect_calls(code, known)
        assert calls == {"func_b"}

    def test_detects_multiple_calls(self):
        """Detect multiple function calls."""
        code = """
def func_a(data):
    data = func_b(data)
    data = func_c(data)
    return data
"""
        known = {"func_b", "func_c", "func_d"}
        calls = detect_calls(code, known)
        assert calls == {"func_b", "func_c"}

    def test_ignores_unknown_functions(self):
        """Only detect calls to known functions."""
        code = """
def func_a(data):
    data = unknown_func(data)
    return len(data)
"""
        known = {"func_b", "func_c"}
        calls = detect_calls(code, known)
        assert calls == set()

    def test_handles_nested_calls(self):
        """Detect calls nested in expressions."""
        code = """
def func_a(data):
    return [func_b(x) for x in func_c(data)]
"""
        known = {"func_b", "func_c"}
        calls = detect_calls(code, known)
        assert calls == {"func_b", "func_c"}

    def test_handles_method_calls(self):
        """Method calls on objects should not match function names."""
        code = """
def func_a(data):
    obj.func_b(data)
    return func_c(data)
"""
        known = {"func_b", "func_c"}
        calls = detect_calls(code, known)
        # func_b is a method call, not a function call
        assert calls == {"func_c"}

    def test_handles_invalid_syntax(self):
        """Return empty set for invalid Python code."""
        code = "def broken( return"
        known = {"func_a"}
        calls = detect_calls(code, known)
        assert calls == set()

    def test_empty_known_functions(self):
        """Empty known functions returns empty set."""
        code = """
def func_a(data):
    return func_b(data)
"""
        calls = detect_calls(code, set())
        assert calls == set()


class TestResolveDependencies:
    """Tests for resolve_dependencies function."""

    def test_simple_chain(self):
        """A calls B: B should come before A."""
        functions = [
            {"name": "func_a", "docstring": "A", "code": "def func_a(d): return func_b(d)"},
            {"name": "func_b", "docstring": "B", "code": "def func_b(d): return d"},
        ]
        result = resolve_dependencies(functions)
        names = [f["name"] for f in result]
        assert names.index("func_b") < names.index("func_a")

    def test_diamond_dependencies(self):
        """A calls B,C; B,C call D: D first, then B,C, then A."""
        functions = [
            {"name": "func_a", "docstring": "A", "code": "def func_a(d): return func_b(func_c(d))"},
            {"name": "func_b", "docstring": "B", "code": "def func_b(d): return func_d(d)"},
            {"name": "func_c", "docstring": "C", "code": "def func_c(d): return func_d(d)"},
            {"name": "func_d", "docstring": "D", "code": "def func_d(d): return d"},
        ]
        result = resolve_dependencies(functions)
        names = [f["name"] for f in result]

        # D must come before B, C, and A
        assert names.index("func_d") < names.index("func_b")
        assert names.index("func_d") < names.index("func_c")
        assert names.index("func_d") < names.index("func_a")
        # B and C must come before A
        assert names.index("func_b") < names.index("func_a")
        assert names.index("func_c") < names.index("func_a")

    def test_cycle_handling(self):
        """A calls B, B calls A: should not crash, preserve order."""
        functions = [
            {"name": "func_a", "docstring": "A", "code": "def func_a(d): return func_b(d)"},
            {"name": "func_b", "docstring": "B", "code": "def func_b(d): return func_a(d)"},
        ]
        # Should not raise
        result = resolve_dependencies(functions)
        # Both functions should be present
        names = [f["name"] for f in result]
        assert set(names) == {"func_a", "func_b"}

    def test_no_dependencies(self):
        """Functions with no dependencies preserve original order."""
        functions = [
            {"name": "func_a", "docstring": "A", "code": "def func_a(d): return d"},
            {"name": "func_b", "docstring": "B", "code": "def func_b(d): return d"},
            {"name": "func_c", "docstring": "C", "code": "def func_c(d): return d"},
        ]
        result = resolve_dependencies(functions)
        names = [f["name"] for f in result]
        assert names == ["func_a", "func_b", "func_c"]

    def test_empty_list(self):
        """Empty input returns empty list."""
        result = resolve_dependencies([])
        assert result == []

    def test_single_function(self):
        """Single function returns as-is."""
        functions = [{"name": "func_a", "docstring": "A", "code": "def func_a(d): return d"}]
        result = resolve_dependencies(functions)
        assert len(result) == 1
        assert result[0]["name"] == "func_a"

    def test_self_reference(self):
        """Self-recursive function doesn't cause issues."""
        functions = [
            {"name": "factorial", "docstring": "F", "code": "def factorial(n): return n * factorial(n-1) if n > 1 else 1"},
        ]
        result = resolve_dependencies(functions)
        assert len(result) == 1
        assert result[0]["name"] == "factorial"

    def test_preserves_function_data(self):
        """Original function dicts are preserved."""
        functions = [
            {"name": "func_a", "docstring": "Doc A", "code": "def func_a(d): return func_b(d)", "extra": "data"},
            {"name": "func_b", "docstring": "Doc B", "code": "def func_b(d): return d", "other": 123},
        ]
        result = resolve_dependencies(functions)
        # Find each function
        a = next(f for f in result if f["name"] == "func_a")
        b = next(f for f in result if f["name"] == "func_b")
        assert a["docstring"] == "Doc A"
        assert a["extra"] == "data"
        assert b["other"] == 123

    def test_complex_three_level_chain(self):
        """Three-level dependency chain: C -> B -> A."""
        functions = [
            {"name": "level_1", "docstring": "L1", "code": "def level_1(d): return level_2(d)"},
            {"name": "level_2", "docstring": "L2", "code": "def level_2(d): return level_3(d)"},
            {"name": "level_3", "docstring": "L3", "code": "def level_3(d): return d"},
        ]
        result = resolve_dependencies(functions)
        names = [f["name"] for f in result]
        # level_3 first, then level_2, then level_1
        assert names.index("level_3") < names.index("level_2")
        assert names.index("level_2") < names.index("level_1")


class TestOutputIntegration:
    """Tests for integration with output.py."""

    def test_clean_data_uses_resolved_order(self, tmp_path):
        """clean_data() calls functions in dependency-resolved order."""
        functions = [
            {"name": "caller", "docstring": "Calls helper", "code": "def caller(d): return helper(d)"},
            {"name": "helper", "docstring": "Helper function", "code": "def helper(d): return d"},
        ]

        output = tmp_path / "clean.py"
        write_cleaning_file(functions, str(output))

        content = output.read_text()

        # Helper should be called before caller in clean_data
        helper_call = content.find("data = helper(data)")
        caller_call = content.find("data = caller(data)")
        assert helper_call < caller_call, "helper should be called before caller"

        # Verify valid Python
        ast.parse(content)

    def test_diamond_dependency_output(self, tmp_path):
        """Diamond dependency produces correct call order in output."""
        functions = [
            {"name": "top", "docstring": "T", "code": "def top(d): return left(right(d))"},
            {"name": "left", "docstring": "L", "code": "def left(d): return bottom(d)"},
            {"name": "right", "docstring": "R", "code": "def right(d): return bottom(d)"},
            {"name": "bottom", "docstring": "B", "code": "def bottom(d): return d"},
        ]

        output = tmp_path / "clean.py"
        write_cleaning_file(functions, str(output))

        content = output.read_text()

        # Bottom must be called first
        bottom_call = content.find("data = bottom(data)")
        left_call = content.find("data = left(data)")
        right_call = content.find("data = right(data)")
        top_call = content.find("data = top(data)")

        assert bottom_call < left_call
        assert bottom_call < right_call
        assert bottom_call < top_call
        assert left_call < top_call
        assert right_call < top_call

        # Verify valid Python
        ast.parse(content)

    def test_cycle_still_produces_valid_output(self, tmp_path):
        """Circular dependencies still produce valid Python output."""
        functions = [
            {"name": "func_a", "docstring": "A", "code": "def func_a(d): return func_b(d) if d else d"},
            {"name": "func_b", "docstring": "B", "code": "def func_b(d): return func_a(d) if d else d"},
        ]

        output = tmp_path / "clean.py"
        write_cleaning_file(functions, str(output))

        content = output.read_text()

        # Both functions should be present
        assert "def func_a(d):" in content
        assert "def func_b(d):" in content
        assert "def clean_data(data):" in content

        # Verify valid Python
        ast.parse(content)

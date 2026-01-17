"""LLM-generated parser for unknown file formats."""

import ast
import re
from pathlib import Path

from .types import LLMBackend

# Dangerous patterns for parser code (allows 'open' since parsers need file I/O)
_DANGEROUS_IMPORTS = frozenset({
    "os", "subprocess", "sys", "shutil", "socket", "urllib",
    "requests", "httplib", "ftplib", "smtplib", "pickle",
})
_DANGEROUS_CALLS = frozenset({"eval", "exec", "compile", "__import__"})

PARSER_PROMPT = '''You are a data parsing expert. Generate a Python function to parse this file format.

=== SAMPLE (first 4KB) ===
{sample}

=== TASK ===
Generate a function with this EXACT signature:

```python
def parse_file(file_path: str) -> list[dict]:
    """Parse the file into a list of records."""
    # Your implementation
```

RULES:
- Return list of dicts, one dict per logical record
- Use only stdlib (xml.etree, json, re, csv)
- Handle the ENTIRE file, not just this sample
- Be defensive about malformed data
- Include necessary imports inside or before the function
'''


def check_parser_safety(code: str) -> list[str]:
    """Check parser code for dangerous patterns. Returns list of issues."""
    issues = []
    try:
        tree = ast.parse(code)
    except SyntaxError as e:
        return [f"Syntax error: {e}"]

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                module = alias.name.split(".")[0]
                if module in _DANGEROUS_IMPORTS:
                    issues.append(f"Dangerous import: {alias.name}")
        if isinstance(node, ast.ImportFrom):
            if node.module:
                module = node.module.split(".")[0]
                if module in _DANGEROUS_IMPORTS:
                    issues.append(f"Dangerous import: from {node.module}")
        if isinstance(node, ast.Call):
            if isinstance(node.func, ast.Name):
                if node.func.id in _DANGEROUS_CALLS:
                    issues.append(f"Dangerous call: {node.func.id}()")
    return issues


def extract_python_block(text: str) -> str:
    """Extract code from ```python ... ``` block."""
    match = re.search(r"```python\s*(.*?)\s*```", text, re.DOTALL)
    return match.group(1).strip() if match else text.strip()


def generate_parser(llm_backend: LLMBackend, file_path: str) -> callable:
    """
    Generate a parser function for an unknown file format.

    Args:
        llm_backend: LLM backend implementing generate(prompt) -> str
        file_path: Path to the file to parse

    Returns:
        A callable parse_file(file_path) -> list[dict]

    Raises:
        ValueError: If generated code is unsafe, has invalid syntax,
                   or doesn't return list of dicts
    """
    path = Path(file_path)
    with open(path, "r", errors="replace") as f:
        sample = f.read(4096)

    prompt = PARSER_PROMPT.format(sample=sample)
    response = llm_backend.generate(prompt)
    code = extract_python_block(response)

    # Validate syntax
    try:
        ast.parse(code)
    except SyntaxError as e:
        raise ValueError(f"Generated parser has invalid syntax: {e}")

    # Security check
    issues = check_parser_safety(code)
    if issues:
        raise ValueError(f"Generated parser contains dangerous code: {issues}")

    # Execute to get function
    namespace: dict = {}
    exec(code, namespace)

    if "parse_file" not in namespace:
        raise ValueError("Generated code must define 'parse_file' function")

    parser = namespace["parse_file"]

    # Validate on actual file
    result = parser(file_path)
    if not isinstance(result, list):
        raise ValueError(f"Parser must return list, got {type(result).__name__}")
    if result and not isinstance(result[0], dict):
        raise ValueError(
            f"Parser must return list of dicts, got list of {type(result[0]).__name__}"
        )

    return parser

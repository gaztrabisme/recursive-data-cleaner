"""Runtime validation for generated cleaning functions."""

import ast
import json
import re
from typing import Literal

# Modules that could access filesystem, run commands, or exfiltrate data
DANGEROUS_IMPORTS = frozenset({
    "os",
    "subprocess",
    "sys",
    "shutil",
    "pathlib",
    "socket",
    "urllib",
    "requests",
    "httplib",
    "ftplib",
    "smtplib",
    "pickle",
})

# Built-in functions that allow arbitrary code execution
DANGEROUS_CALLS = frozenset({
    "eval",
    "exec",
    "compile",
    "__import__",
    "open",  # Data cleaning functions receive data as args, shouldn't need file I/O
})


def check_code_safety(code: str) -> tuple[bool, str | None]:
    """
    Check if generated code contains dangerous patterns.

    Catches common LLM mistakes like importing os or using eval().
    Not a security sandbox - won't catch obfuscated/adversarial code.

    Args:
        code: Python source code to check

    Returns:
        (True, None) if code appears safe
        (False, error_message) if dangerous pattern detected
    """
    try:
        tree = ast.parse(code)
    except SyntaxError as e:
        return False, f"Syntax error: {e}"

    for node in ast.walk(tree):
        # Check: import os, import subprocess, etc.
        if isinstance(node, ast.Import):
            for alias in node.names:
                module = alias.name.split(".")[0]
                if module in DANGEROUS_IMPORTS:
                    return False, f"Dangerous import: {alias.name}"

        # Check: from os import path, from subprocess import run, etc.
        if isinstance(node, ast.ImportFrom):
            if node.module:
                module = node.module.split(".")[0]
                if module in DANGEROUS_IMPORTS:
                    return False, f"Dangerous import: from {node.module}"

        # Check: eval(...), exec(...), open(...), etc.
        if isinstance(node, ast.Call):
            if isinstance(node.func, ast.Name):
                if node.func.id in DANGEROUS_CALLS:
                    return False, f"Dangerous function call: {node.func.id}()"

    return True, None


def split_holdout(
    chunk: str, holdout_ratio: float, mode: Literal["structured", "text"] = "structured"
) -> tuple[str, str]:
    """
    Split chunk into generation and holdout portions.

    Args:
        chunk: Raw chunk string (JSONL for structured, plain text for text mode)
        holdout_ratio: Fraction to hold out (0.0-0.5)
        mode: "structured" splits by JSONL records, "text" splits at sentence boundary

    Returns:
        (generation_data, holdout_data) - both as strings
    """
    if holdout_ratio <= 0:
        return chunk, ""

    if mode == "structured":
        lines = [ln for ln in chunk.strip().split("\n") if ln.strip()]
        if not lines:
            return chunk, ""
        holdout_count = max(1, int(len(lines) * holdout_ratio))
        split_idx = len(lines) - holdout_count
        return "\n".join(lines[:split_idx]), "\n".join(lines[split_idx:])
    else:
        # Text mode: split at sentence boundary
        sentences = re.split(r"(?<=[.!?])\s+", chunk.strip())
        if len(sentences) <= 1:
            return chunk, ""
        holdout_count = max(1, int(len(sentences) * holdout_ratio))
        split_idx = len(sentences) - holdout_count
        return " ".join(sentences[:split_idx]), " ".join(sentences[split_idx:])


def validate_function(
    code: str,
    sample_data: list[dict] | str,
    function_name: str,
    mode: Literal["structured", "text"] = "structured",
) -> tuple[bool, str | None]:
    """
    Execute generated function on sample data to catch runtime errors.

    Args:
        code: The Python source code of the function
        sample_data: List of data records (structured) or text string (text mode)
        function_name: Name of the function to call
        mode: "structured" for dict records, "text" for string input

    Returns:
        (True, None) if function executes without error
        (False, error_message) if function raises an exception
    """
    # Handle empty data
    if mode == "text":
        if not sample_data or (isinstance(sample_data, str) and not sample_data.strip()):
            return True, None
    else:
        if not sample_data:
            return True, None

    # Create isolated namespace and execute the code
    namespace: dict = {}
    try:
        exec(code, namespace)
    except Exception as e:
        return False, f"Code compilation failed: {type(e).__name__}: {e}"

    # Get the function from namespace
    func = namespace.get(function_name)
    if func is None:
        return False, f"Function '{function_name}' not found in code"

    if mode == "text":
        # Text mode: sample_data is a string
        try:
            result = func(sample_data)
            # Verify function returns a string
            if not isinstance(result, str):
                return False, f"Function must return str, got {type(result).__name__}"
        except Exception as e:
            return False, f"Runtime error on text input: {type(e).__name__}: {e}"
    else:
        # Structured mode: sample_data is list[dict]
        for i, record in enumerate(sample_data):
            try:
                func(record)
            except Exception as e:
                return False, f"Runtime error on sample {i}: {type(e).__name__}: {e}"

    return True, None


def extract_sample_data(
    chunk: str, max_samples: int = 3, mode: Literal["structured", "text"] = "structured"
) -> list[dict] | str:
    """
    Extract sample data from a chunk string.

    Args:
        chunk: Raw chunk string
        max_samples: Maximum number of samples to extract (structured mode only)
        mode: "structured" for JSONL parsing, "text" for raw string

    Returns:
        List of parsed JSON objects (structured) or the chunk string (text)
    """
    if mode == "text":
        # Text mode: return the chunk as-is for validation
        return chunk

    # Structured mode: parse JSONL
    samples = []
    for line in chunk.strip().split("\n"):
        line = line.strip()
        if not line:
            continue
        try:
            obj = json.loads(line)
            if isinstance(obj, dict):
                samples.append(obj)
                if len(samples) >= max_samples:
                    break
        except json.JSONDecodeError:
            continue
    return samples

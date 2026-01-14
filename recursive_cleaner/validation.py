"""Runtime validation for generated cleaning functions."""

import json
from typing import Literal


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

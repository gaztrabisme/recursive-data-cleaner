"""Runtime validation for generated cleaning functions."""

import json


def validate_function(
    code: str,
    sample_data: list[dict],
    function_name: str,
) -> tuple[bool, str | None]:
    """
    Execute generated function on sample data to catch runtime errors.

    Args:
        code: The Python source code of the function
        sample_data: List of data records to test against
        function_name: Name of the function to call

    Returns:
        (True, None) if function executes without error
        (False, error_message) if function raises an exception
    """
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

    # Test the function on each sample record
    for i, record in enumerate(sample_data):
        try:
            func(record)
        except Exception as e:
            return False, f"Runtime error on sample {i}: {type(e).__name__}: {e}"

    return True, None


def extract_sample_data(chunk: str, max_samples: int = 3) -> list[dict]:
    """
    Extract sample data records from a chunk string.

    Args:
        chunk: Raw chunk string (JSONL format expected)
        max_samples: Maximum number of samples to extract

    Returns:
        List of parsed JSON objects (up to max_samples)
    """
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

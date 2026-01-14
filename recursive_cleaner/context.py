"""Context management for docstring registry."""


def build_context(functions: list[dict], max_chars: int = 8000) -> str:
    """
    Build context string from generated functions for LLM prompt.

    Uses FIFO eviction - keeps most recent functions that fit within budget.

    Args:
        functions: List of dicts with 'name' and 'docstring' keys
        max_chars: Maximum character budget for context

    Returns:
        Formatted string of function docstrings, or placeholder if empty
    """
    if not functions:
        return "(No functions generated yet)"

    ctx = ""
    for f in reversed(functions):
        entry = f"## {f['name']}\n{f['docstring']}\n\n"
        if len(ctx) + len(entry) > max_chars:
            break
        ctx = entry + ctx

    return ctx if ctx else "(No functions generated yet)"

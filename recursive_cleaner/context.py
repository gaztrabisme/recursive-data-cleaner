"""Context management for docstring registry."""

import re


def _extract_words(text: str) -> set[str]:
    """Extract lowercase alphabetic tokens (2+ chars) from text."""
    return set(re.findall(r"[a-z]{2,}", text.lower()))


def build_context(functions: list[dict], max_chars: int = 8000, chunk: str = "") -> str:
    """
    Build context string from generated functions for LLM prompt.

    When chunk text is provided, selects functions by relevance (word overlap
    between docstring/name and chunk), displayed in generation order.
    Falls back to FIFO when no chunk is provided.

    Args:
        functions: List of dicts with 'name' and 'docstring' keys
        max_chars: Maximum character budget for context
        chunk: Current data chunk text for relevance scoring

    Returns:
        Formatted string of function docstrings, or placeholder if empty
    """
    if not functions:
        return "(No functions generated yet)"

    if not chunk:
        # FIFO fallback: most recent functions that fit
        ctx = ""
        for f in reversed(functions):
            entry = f"## {f['name']}\n{f['docstring']}\n\n"
            if len(ctx) + len(entry) > max_chars:
                break
            ctx = entry + ctx
        return ctx if ctx else "(No functions generated yet)"

    # Relevance-filtered: score by word overlap, select best, display in order
    chunk_words = _extract_words(chunk)

    scored = []
    for i, f in enumerate(functions):
        name_words = _extract_words(f["name"].replace("_", " "))
        doc_words = _extract_words(f.get("docstring", ""))
        overlap = len((name_words | doc_words) & chunk_words)
        scored.append((overlap, i))

    # Highest relevance first, break ties by most recent (higher index)
    scored.sort(key=lambda x: (x[0], x[1]), reverse=True)

    # Select functions that fit within budget
    selected = set()
    budget_used = 0
    for _, idx in scored:
        f = functions[idx]
        entry_len = len(f"## {f['name']}\n{f['docstring']}\n\n")
        if budget_used + entry_len <= max_chars:
            selected.add(idx)
            budget_used += entry_len

    # Build context in original generation order
    ctx = ""
    for i, f in enumerate(functions):
        if i in selected:
            ctx += f"## {f['name']}\n{f['docstring']}\n\n"

    return ctx if ctx else "(No functions generated yet)"

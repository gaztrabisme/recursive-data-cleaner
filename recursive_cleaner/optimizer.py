"""Function optimization utilities for two-pass consolidation."""

import ast
import re
from collections import Counter, defaultdict
from math import log

from recursive_cleaner.prompt import CONSOLIDATION_TEMPLATE
from recursive_cleaner.response import ConsolidationResult, parse_consolidation_response
from recursive_cleaner.types import LLMBackend


# Common domain words to extract from function names
_DOMAIN_WORDS = frozenset({
    "date", "phone", "email", "name", "address", "money", "status", "id",
    "price", "amount", "time", "url", "zip", "state", "country", "city",
    "number", "code", "format", "text", "string", "value",
})


def extract_tags(docstring: str) -> set[str]:
    """
    Extract tags from a function docstring.

    Args:
        docstring: The function's docstring

    Returns:
        Set of lowercase tag strings, empty set if no tags found

    Example:
        >>> extract_tags("Normalize phones.\\nTags: phone, normalize, format")
        {"phone", "normalize", "format"}
    """
    if not docstring:
        return set()

    # Find the "Tags:" line anywhere in the docstring
    match = re.search(r"^Tags:\s*(.*)$", docstring, re.MULTILINE | re.IGNORECASE)
    if not match:
        return set()

    tags_str = match.group(1).strip()
    if not tags_str:
        return set()

    # Split by comma, strip whitespace, lowercase, filter empty
    tags = {tag.strip().lower() for tag in tags_str.split(",") if tag.strip()}
    return tags


def _calculate_idf(func_tags: list[set[str]], n: int) -> dict[str, float]:
    """
    Calculate IDF scores for all tags.

    Args:
        func_tags: List of tag sets, one per function
        n: Total number of functions

    Returns:
        Dict mapping tag to IDF score
    """
    if n == 0:
        return {}

    # Count how many functions contain each tag
    doc_freq: Counter[str] = Counter()
    for tags in func_tags:
        for tag in tags:
            doc_freq[tag] += 1

    # IDF = log(n / doc_freq) - higher for rarer tags
    return {tag: log(n / freq) for tag, freq in doc_freq.items()}


def _fallback_from_name(name: str) -> str:
    """
    Extract domain word from function name when no tags.

    Args:
        name: Function name like "normalize_phone_format"

    Returns:
        Domain word (e.g., "phone") or "misc" if none found
    """
    # Split on underscores and look for domain words
    parts = name.lower().split("_")
    for part in parts:
        if part in _DOMAIN_WORDS:
            return part
    return "misc"


def _rebalance_groups(
    groups: dict[str, list[dict]],
    min_size: int,
    max_size: int,
) -> dict[str, list[dict]]:
    """
    Merge small groups, split large ones.

    Args:
        groups: Dict mapping tag to list of functions
        min_size: Merge groups smaller than this
        max_size: Split groups larger than this

    Returns:
        Rebalanced groups dict
    """
    result: dict[str, list[dict]] = {}
    orphans: list[dict] = []

    # First pass: separate small groups as orphans, split large ones
    for tag, funcs in groups.items():
        if len(funcs) < min_size:
            orphans.extend(funcs)
        elif len(funcs) > max_size:
            # Split into chunks of max_size
            for i in range(0, len(funcs), max_size):
                chunk = funcs[i : i + max_size]
                suffix = f"_{i // max_size + 1}" if i > 0 else ""
                result[f"{tag}{suffix}"] = chunk
        else:
            result[tag] = funcs

    # Assign orphans to group with most tag overlap (Jaccard similarity)
    if orphans and result:
        for func in orphans:
            func_tags = extract_tags(func.get("docstring", ""))
            best_group = None
            best_score = -1.0

            for group_tag, group_funcs in result.items():
                # Calculate Jaccard similarity with group's tags
                group_tags: set[str] = set()
                for gf in group_funcs:
                    group_tags.update(extract_tags(gf.get("docstring", "")))

                if func_tags and group_tags:
                    intersection = len(func_tags & group_tags)
                    union = len(func_tags | group_tags)
                    score = intersection / union if union > 0 else 0.0
                else:
                    score = 0.0

                if score > best_score:
                    best_score = score
                    best_group = group_tag

            # If no overlap found, assign to first group
            if best_group is None:
                best_group = next(iter(result.keys()))

            result[best_group].append(func)
    elif orphans:
        # No other groups exist, create misc group
        result["misc"] = orphans

    return result


def group_by_salience(
    functions: list[dict],
    min_group: int = 2,
    max_group: int = 40,
) -> dict[str, list[dict]]:
    """
    Group functions by most informative tag (highest IDF).

    Args:
        functions: List of {name, docstring, code} dicts
        min_group: Merge groups smaller than this
        max_group: Split groups larger than this

    Returns:
        Dict mapping primary tag to list of functions
    """
    if not functions:
        return {}

    n = len(functions)

    # Extract tags from all functions
    func_tags = [extract_tags(f.get("docstring", "")) for f in functions]

    # Calculate IDF scores
    idf_scores = _calculate_idf(func_tags, n)

    # Assign each function to its highest-IDF tag
    groups: dict[str, list[dict]] = defaultdict(list)

    for func, tags in zip(functions, func_tags):
        if tags:
            # Find tag with highest IDF
            best_tag = max(tags, key=lambda t: idf_scores.get(t, 0.0))
            groups[best_tag].append(func)
        else:
            # Use fallback from function name
            fallback = _fallback_from_name(func.get("name", ""))
            groups[fallback].append(func)

    # Rebalance groups
    return _rebalance_groups(dict(groups), min_group, max_group)


def format_functions_for_review(functions: list[dict]) -> str:
    """
    Format functions for consolidation prompt.

    Args:
        functions: List of {name, docstring, code} dicts

    Returns:
        Formatted string with all functions
    """
    parts = []
    for i, func in enumerate(functions, 1):
        name = func.get("name", f"function_{i}")
        docstring = func.get("docstring", "")
        code = func.get("code", "")

        part = f"### Function {i}: {name}\n"
        if docstring:
            part += f"Docstring:\n{docstring}\n\n"
        if code:
            part += f"Code:\n```python\n{code}\n```\n"
        parts.append(part)

    return "\n".join(parts)


def consolidate_group(
    functions: list[dict],
    backend: LLMBackend,
) -> tuple[list[dict], ConsolidationResult]:
    """
    Single consolidation pass on a group of functions.

    Args:
        functions: List of {name, docstring, code} dicts to consolidate
        backend: LLM backend for generating consolidation

    Returns:
        Tuple of (new function list, raw ConsolidationResult)
    """
    if not functions:
        return [], ConsolidationResult(
            merged_functions=[],
            kept_unchanged=[],
            assessment=type("Assessment", (), {
                "complete": True,
                "remaining_issues": "none",
                "confidence": "high",
            })(),
        )

    # Build prompt
    formatted = format_functions_for_review(functions)
    prompt = CONSOLIDATION_TEMPLATE.format(
        count=len(functions),
        functions=formatted,
    )

    # Call LLM
    response = backend.generate(prompt)

    # Parse response
    result = parse_consolidation_response(response)

    # Build new function list
    new_functions = []

    # Add merged functions (already validated by parse_consolidation_response)
    for merged in result.merged_functions:
        new_functions.append({
            "name": merged["name"],
            "docstring": merged["docstring"],
            "code": merged["code"],
        })

    # Add kept unchanged functions
    kept_names = set(result.kept_unchanged)
    for func in functions:
        if func.get("name") in kept_names:
            new_functions.append(func)

    return new_functions, result


def consolidate_with_agency(
    functions: list[dict],
    backend: LLMBackend,
    max_rounds: int = 5,
) -> list[dict]:
    """
    Consolidate functions until LLM reports complete.

    The agency loop:
    1. Call consolidate_group()
    2. Check assessment.complete
    3. If False, repeat with result
    4. If True or max_rounds reached, return

    Args:
        functions: List of {name, docstring, code} dicts
        backend: LLM backend for consolidation
        max_rounds: Maximum consolidation rounds (safety cap)

    Returns:
        Consolidated list of functions
    """
    if not functions:
        return []

    current_functions = list(functions)

    for round_num in range(max_rounds):
        try:
            new_functions, result = consolidate_group(current_functions, backend)

            # Check if consolidation is complete
            if result.assessment.complete:
                return new_functions

            # If no change in function count, avoid infinite loop
            if len(new_functions) >= len(current_functions) and round_num > 0:
                return new_functions

            current_functions = new_functions

        except Exception:
            # On any error, return what we have (don't lose data)
            return current_functions

    # Max rounds reached
    return current_functions

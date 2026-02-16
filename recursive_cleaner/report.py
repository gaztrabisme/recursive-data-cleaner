"""Cleaning report generation."""

import copy
from datetime import datetime, timezone
from pathlib import Path


def capture_transformations(
    code: str,
    function_name: str,
    sample_data: list[dict],
    max_examples: int = 5,
) -> list[dict]:
    """
    Run function on sample records and return before/after pairs.

    Args:
        code: Python source code of the function
        function_name: Name of the function to call
        sample_data: List of sample records to transform
        max_examples: Maximum examples to capture

    Returns:
        List of {"before": dict, "after": dict} for records that changed
    """
    if not sample_data:
        return []
    namespace: dict = {}
    try:
        exec(code, namespace)
    except Exception:
        return []
    func = namespace.get(function_name)
    if not func:
        return []
    examples = []
    for record in sample_data:
        original = copy.deepcopy(record)
        try:
            transformed = func(copy.deepcopy(record))
            if transformed != original:
                examples.append({"before": original, "after": transformed})
                if len(examples) >= max_examples:
                    break
        except Exception:
            continue
    return examples


def generate_report(
    file_path: str,
    total_chunks: int,
    functions: list[dict],
    latency_stats: dict | None = None,
    quality_before: dict | None = None,
    quality_after: dict | None = None,
) -> str:
    """
    Generate markdown cleaning report.

    Args:
        file_path: Path to the file that was cleaned
        total_chunks: Number of chunks processed
        functions: List of generated function dicts with 'name', 'docstring' keys
        latency_stats: Optional dict with call_count, total_ms, avg_ms, etc.
        quality_before: Optional dict with null_count, empty_string_count, etc.
        quality_after: Optional dict with quality metrics after cleaning

    Returns:
        Markdown-formatted report string
    """
    lines = ["# Data Cleaning Report", ""]

    # Summary section
    lines.append("## Summary")
    lines.append("")
    lines.append(f"- **File**: `{file_path}`")
    lines.append(f"- **Chunks processed**: {total_chunks}")
    lines.append(f"- **Functions generated**: {len(functions)}")

    if latency_stats and latency_stats.get("call_count", 0) > 0:
        total_ms = latency_stats.get("total_ms", 0)
        lines.append(f"- **Total LLM time**: {total_ms:.0f}ms")
        lines.append(f"- **LLM calls**: {latency_stats.get('call_count', 0)}")

    lines.append("")

    # Functions section
    if functions:
        lines.append("## Functions Generated")
        lines.append("")
        lines.append("| # | Name | Description |")
        lines.append("|---|------|-------------|")

        for i, func in enumerate(functions, 1):
            name = func.get("name", "unknown")
            docstring = func.get("docstring", "")
            # Get first line of docstring
            first_line = docstring.split("\n")[0].strip() if docstring else ""
            # Escape pipe characters for markdown table
            first_line = first_line.replace("|", "\\|")
            lines.append(f"| {i} | `{name}` | {first_line} |")

        lines.append("")

        # Sample transformations
        has_samples = any(func.get("samples") for func in functions)
        if has_samples:
            lines.append("### Sample Transformations")
            lines.append("")
            for func in functions:
                samples = func.get("samples", [])
                if not samples:
                    continue
                lines.append(f"**`{func.get('name', 'unknown')}`**")
                lines.append("")
                for sample in samples:
                    before = sample.get("before", {})
                    after = sample.get("after", {})
                    all_keys = sorted(set(list(before.keys()) + list(after.keys())))
                    for key in all_keys:
                        bval = before.get(key)
                        aval = after.get(key)
                        if bval != aval:
                            lines.append(f"- `{key}`: `{bval!r}` → `{aval!r}`")
                lines.append("")

    # Quality metrics section
    if quality_before:
        lines.append("## Quality Metrics")
        lines.append("")
        lines.append("| Metric | Before | After | Change |")
        lines.append("|--------|--------|-------|--------|")

        before_nulls = quality_before.get("null_count", 0)
        after_nulls = quality_after.get("null_count", 0) if quality_after else before_nulls
        null_change = _format_change(before_nulls, after_nulls)
        lines.append(f"| Null values | {before_nulls} | {after_nulls} | {null_change} |")

        before_empty = quality_before.get("empty_string_count", 0)
        after_empty = quality_after.get("empty_string_count", 0) if quality_after else before_empty
        empty_change = _format_change(before_empty, after_empty)
        lines.append(f"| Empty strings | {before_empty} | {after_empty} | {empty_change} |")

        lines.append("")

    # Footer
    lines.append("---")
    lines.append("")
    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    lines.append(f"*Generated by Recursive Data Cleaner at {timestamp}*")

    return "\n".join(lines)


def _format_change(before: int, after: int) -> str:
    """Format the change between before and after values."""
    if before == 0:
        if after == 0:
            return "-"
        return f"+{after}"

    diff = after - before
    pct = (diff / before) * 100

    if diff == 0:
        return "0%"
    elif diff < 0:
        return f"{pct:.0f}%"
    else:
        return f"+{pct:.0f}%"


def write_report(
    report_path: str,
    file_path: str,
    total_chunks: int,
    functions: list[dict],
    latency_stats: dict | None = None,
    quality_before: dict | None = None,
    quality_after: dict | None = None,
) -> None:
    """
    Generate and write cleaning report to file.

    Args:
        report_path: Path to write the report
        file_path: Path to the file that was cleaned
        total_chunks: Number of chunks processed
        functions: List of generated function dicts
        latency_stats: Optional latency statistics
        quality_before: Optional quality metrics before cleaning
        quality_after: Optional quality metrics after cleaning
    """
    content = generate_report(
        file_path=file_path,
        total_chunks=total_chunks,
        functions=functions,
        latency_stats=latency_stats,
        quality_before=quality_before,
        quality_after=quality_after,
    )
    Path(report_path).write_text(content)

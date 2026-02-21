"""Global distribution statistics for structured data."""

from collections import Counter

from .metrics import load_structured_data


def compute_field_stats(file_path: str, max_cardinality: int = 50) -> dict:
    """
    Compute per-field value frequency counts across the full dataset.

    Low-cardinality fields (≤ max_cardinality unique values) get full
    value counts. High-cardinality fields get a summary only.

    Args:
        file_path: Path to structured data file (JSONL, JSON, CSV, XLSX, ODS)
        max_cardinality: Threshold for showing full value counts vs summary

    Returns:
        Dict mapping field names to stats dicts with keys:
        - type: "categorical" or "high_cardinality"
        - For categorical: value_counts (list of (value, count) tuples),
          total (int), null_count (int)
        - For high_cardinality: unique (int), total (int)
    """
    data = load_structured_data(file_path)
    if not data:
        return {}

    fields = list(dict.fromkeys(k for r in data for k in r.keys()))
    stats = {}

    for field in fields:
        values = [r.get(field) for r in data if field in r]
        non_null = [v for v in values if v is not None]
        str_values = [str(v) for v in non_null]
        unique_count = len(set(str_values))

        if unique_count <= max_cardinality:
            counts = Counter(str_values).most_common(20)
            stats[field] = {
                "type": "categorical",
                "value_counts": counts,
                "total": len(values),
                "null_count": len(values) - len(non_null),
            }
        else:
            stats[field] = {
                "type": "high_cardinality",
                "unique": unique_count,
                "total": len(values),
            }

    return stats


def format_stats_for_prompt(stats: dict) -> str:
    """
    Format field stats as human-readable text for prompt injection.

    Args:
        stats: Output of compute_field_stats()

    Returns:
        Formatted string, or empty string if no stats
    """
    if not stats:
        return ""

    lines = [
        "Value frequencies across the FULL dataset (not just this chunk).",
        "Use these to determine canonical forms and identify typos/variants.",
    ]

    for field, info in stats.items():
        if info["type"] == "categorical":
            null_str = f", {info['null_count']} null" if info["null_count"] else ""
            lines.append(f"\n{field} ({info['total']} values{null_str}):")
            for value, count in info["value_counts"]:
                pct = count / info["total"] * 100
                lines.append(f"  {value!r}: {count} ({pct:.0f}%)")
        # High-cardinality fields omitted — no actionable info for the LLM

    return "\n".join(lines)

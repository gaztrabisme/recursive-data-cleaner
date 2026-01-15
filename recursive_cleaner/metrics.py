"""Quality metrics for measuring data cleaning effectiveness."""

import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path


@dataclass
class QualityMetrics:
    """Data quality metrics for a dataset."""

    null_count: int
    empty_string_count: int
    unique_values: dict[str, int] = field(default_factory=dict)  # field -> unique count
    total_records: int = 0
    timestamp: str = ""

    def __post_init__(self):
        if not self.timestamp:
            self.timestamp = datetime.now(timezone.utc).isoformat()


def measure_quality(data: list[dict]) -> QualityMetrics:
    """
    Measure quality metrics for a dataset.

    Args:
        data: List of dictionaries representing records

    Returns:
        QualityMetrics with null count, empty string count, and unique values per field
    """
    if not data:
        return QualityMetrics(
            null_count=0,
            empty_string_count=0,
            unique_values={},
            total_records=0,
        )

    null_count = 0
    empty_string_count = 0
    field_values: dict[str, set] = {}

    for record in data:
        if not isinstance(record, dict):
            continue
        for key, value in record.items():
            # Track nulls
            if value is None:
                null_count += 1
            # Track empty strings
            elif isinstance(value, str) and value == "":
                empty_string_count += 1

            # Track unique values per field
            if key not in field_values:
                field_values[key] = set()
            # Use JSON serialization for hashable representation of complex types
            try:
                if isinstance(value, (dict, list)):
                    field_values[key].add(json.dumps(value, sort_keys=True))
                else:
                    field_values[key].add(value)
            except TypeError:
                # Unhashable value, skip
                pass

    unique_values = {k: len(v) for k, v in field_values.items()}

    return QualityMetrics(
        null_count=null_count,
        empty_string_count=empty_string_count,
        unique_values=unique_values,
        total_records=len(data),
    )


def compare_quality(before: QualityMetrics, after: QualityMetrics) -> dict:
    """
    Compare before/after metrics and return improvement percentages.

    Args:
        before: Metrics measured before cleaning
        after: Metrics measured after cleaning

    Returns:
        Dictionary with improvement statistics
    """
    result = {
        "null_count_before": before.null_count,
        "null_count_after": after.null_count,
        "empty_string_before": before.empty_string_count,
        "empty_string_after": after.empty_string_count,
        "total_records_before": before.total_records,
        "total_records_after": after.total_records,
    }

    # Calculate null reduction percentage
    if before.null_count > 0:
        null_reduction = (before.null_count - after.null_count) / before.null_count * 100
        result["null_reduction_pct"] = round(null_reduction, 2)
    else:
        result["null_reduction_pct"] = 0.0

    # Calculate empty string reduction percentage
    if before.empty_string_count > 0:
        empty_reduction = (
            (before.empty_string_count - after.empty_string_count)
            / before.empty_string_count
            * 100
        )
        result["empty_string_reduction_pct"] = round(empty_reduction, 2)
    else:
        result["empty_string_reduction_pct"] = 0.0

    # Track unique value changes per field
    all_fields = set(before.unique_values.keys()) | set(after.unique_values.keys())
    unique_changes = {}
    for fld in all_fields:
        before_count = before.unique_values.get(fld, 0)
        after_count = after.unique_values.get(fld, 0)
        unique_changes[fld] = {"before": before_count, "after": after_count}
    result["unique_values_by_field"] = unique_changes

    return result


def load_structured_data(file_path: str) -> list[dict]:
    """
    Load JSONL/JSON file as list of dicts for measurement.

    Args:
        file_path: Path to JSONL or JSON file

    Returns:
        List of dictionaries (records)
    """
    path = Path(file_path)
    suffix = path.suffix.lower()
    content = path.read_text(encoding="utf-8")

    if suffix == ".jsonl":
        records = []
        for line in content.strip().split("\n"):
            line = line.strip()
            if line:
                try:
                    records.append(json.loads(line))
                except json.JSONDecodeError:
                    pass  # Skip invalid lines
        return records
    elif suffix == ".json":
        data = json.loads(content)
        if isinstance(data, list):
            return [r for r in data if isinstance(r, dict)]
        elif isinstance(data, dict):
            return [data]
        return []
    else:
        # Unsupported format
        return []

"""Schema inference for data files."""

import csv
import json
from io import StringIO
from pathlib import Path


def infer_schema(file_path: str, sample_size: int = 10) -> dict:
    """
    Infer data schema from first N records.

    Args:
        file_path: Path to data file
        sample_size: Number of records to sample

    Returns:
        {"fields": [...], "types": {...}, "samples": {...}, "nullable": {...}}
    """
    path = Path(file_path)
    suffix = path.suffix.lower()

    if not path.exists():
        return {"fields": [], "types": {}, "samples": {}, "nullable": {}}

    content = path.read_text(encoding="utf-8")
    if not content.strip():
        return {"fields": [], "types": {}, "samples": {}, "nullable": {}}

    if suffix == ".jsonl":
        return _infer_jsonl(content, sample_size)
    elif suffix == ".csv":
        return _infer_csv(content, sample_size)
    elif suffix == ".json":
        return _infer_json(content, sample_size)
    else:
        return {"fields": [], "types": {}, "samples": {}, "nullable": {}}


def _infer_jsonl(content: str, sample_size: int) -> dict:
    """Infer schema from JSONL content."""
    lines = [line.strip() for line in content.strip().split("\n") if line.strip()]
    records = [json.loads(line) for line in lines[:sample_size]]
    return _infer_from_records(records)


def _infer_csv(content: str, sample_size: int) -> dict:
    """Infer schema from CSV content."""
    reader = csv.DictReader(StringIO(content))
    records = [row for _, row in zip(range(sample_size), reader)]
    return _infer_from_records(records)


def _infer_json(content: str, sample_size: int) -> dict:
    """Infer schema from JSON content."""
    data = json.loads(content)
    if isinstance(data, list):
        records = data[:sample_size]
    elif isinstance(data, dict):
        records = [data]
    else:
        return {"fields": [], "types": {}, "samples": {}, "nullable": {}}
    return _infer_from_records(records)


def _infer_from_records(records: list[dict]) -> dict:
    """Build schema from list of record dicts."""
    if not records:
        return {"fields": [], "types": {}, "samples": {}, "nullable": {}}

    fields = list(dict.fromkeys(k for r in records for k in r.keys()))
    types = {}
    samples = {}
    nullable = {}

    for field in fields:
        values = [r.get(field) for r in records if field in r]
        nullable[field] = any(v is None for v in values)
        non_null = [v for v in values if v is not None]
        samples[field] = non_null[:3]
        types[field] = _infer_type(non_null)

    return {"fields": fields, "types": types, "samples": samples, "nullable": nullable}


def _infer_type(values: list) -> str:
    """Infer type from list of non-null values."""
    if not values:
        return "unknown"
    type_map = {str: "str", int: "int", float: "float", bool: "bool", list: "list", dict: "dict"}
    seen = set()
    for v in values:
        for py_type, name in type_map.items():
            if type(v) is py_type:
                seen.add(name)
                break
        else:
            seen.add("unknown")
    if len(seen) == 1:
        return seen.pop()
    return "mixed"


def format_schema_for_prompt(schema: dict) -> str:
    """Format schema dict as human-readable string for prompt injection."""
    if not schema.get("fields"):
        return ""
    lines = ["Fields detected:"]
    for field in schema["fields"]:
        ftype = schema["types"].get(field, "unknown")
        is_nullable = schema["nullable"].get(field, False)
        samples = schema["samples"].get(field, [])
        type_str = f"{ftype}, nullable" if is_nullable else ftype
        sample_strs = [repr(s) if isinstance(s, str) else str(s) for s in samples]
        sample_part = ", ".join(sample_strs) if sample_strs else "no samples"
        lines.append(f"- {field} ({type_str}): {sample_part}")
    return "\n".join(lines)

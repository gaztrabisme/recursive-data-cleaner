"""File chunking utilities for the recursive cleaner pipeline."""

import csv
import json
from io import StringIO
from pathlib import Path


def chunk_file(file_path: str, chunk_size: int = 50) -> list[str]:
    """
    Load and chunk a file based on its type.

    Args:
        file_path: Path to the file to chunk
        chunk_size: Number of items per chunk (rows for CSV/JSONL, items for JSON arrays)
                   For text files, this is multiplied by 80 to get character count.

    Returns:
        List of string chunks suitable for LLM context
    """
    path = Path(file_path)
    suffix = path.suffix.lower()

    if not path.exists():
        raise FileNotFoundError(f"File not found: {file_path}")

    content = path.read_text(encoding="utf-8")

    if not content.strip():
        return []

    if suffix == ".txt":
        return _chunk_text(content, chunk_size * 80)
    elif suffix == ".csv":
        return _chunk_csv(content, chunk_size)
    elif suffix == ".json":
        return _chunk_json(content, chunk_size)
    elif suffix == ".jsonl":
        return _chunk_jsonl(content, chunk_size)
    else:
        # Default to text chunking for unknown types
        return _chunk_text(content, chunk_size * 80)


def _chunk_text(content: str, char_count: int) -> list[str]:
    """Chunk text by character count."""
    chunks = []
    for i in range(0, len(content), char_count):
        chunk = content[i:i + char_count]
        if chunk.strip():
            chunks.append(chunk)
    return chunks


def _chunk_csv(content: str, row_count: int) -> list[str]:
    """Chunk CSV by row count, preserving header in each chunk."""
    reader = csv.reader(StringIO(content))
    rows = list(reader)

    if not rows:
        return []

    header = rows[0]
    data_rows = rows[1:]

    if not data_rows:
        return [content.strip()]

    chunks = []
    for i in range(0, len(data_rows), row_count):
        chunk_rows = data_rows[i:i + row_count]
        output = StringIO()
        writer = csv.writer(output)
        writer.writerow(header)
        writer.writerows(chunk_rows)
        chunks.append(output.getvalue().strip())

    return chunks


def _chunk_json(content: str, item_count: int) -> list[str]:
    """Chunk JSON - arrays by item count, objects as single chunk."""
    data = json.loads(content)

    if isinstance(data, list):
        if not data:
            return []
        chunks = []
        for i in range(0, len(data), item_count):
            chunk_data = data[i:i + item_count]
            chunks.append(json.dumps(chunk_data, indent=2))
        return chunks
    else:
        # Object - return as single chunk
        return [json.dumps(data, indent=2)]


def _chunk_jsonl(content: str, line_count: int) -> list[str]:
    """Chunk JSONL by line count."""
    lines = [line.strip() for line in content.strip().split("\n") if line.strip()]

    if not lines:
        return []

    chunks = []
    for i in range(0, len(lines), line_count):
        chunk_lines = lines[i:i + line_count]
        chunks.append("\n".join(chunk_lines))

    return chunks

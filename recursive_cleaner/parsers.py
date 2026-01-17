"""File chunking utilities for the recursive cleaner pipeline."""

import csv
import hashlib
import json
import random
import re
from io import StringIO
from pathlib import Path
from typing import Literal

# Try to import vendored SentenceChunker, fall back to simple implementation
try:
    from .vendor import SentenceChunker

    _HAS_SENTENCE_CHUNKER = True
except ImportError:
    _HAS_SENTENCE_CHUNKER = False

# File extensions supported by markitdown for conversion to text
MARKITDOWN_EXTENSIONS = {
    ".pdf", ".docx", ".doc", ".xlsx", ".xls", ".pptx", ".ppt",
    ".html", ".htm", ".epub", ".msg", ".rtf", ".odt", ".ods", ".odp"
}


def load_parquet(file_path: str) -> list[dict]:
    """Load parquet file as list of dicts.

    Args:
        file_path: Path to the parquet file

    Returns:
        List of dictionaries, one per row

    Raises:
        ImportError: If pyarrow is not installed
    """
    try:
        import pyarrow.parquet as pq
    except ImportError:
        raise ImportError(
            "pyarrow is required for parquet files. "
            "Install with: pip install recursive-cleaner[parquet]"
        )

    table = pq.read_table(file_path)
    return table.to_pylist()


def preprocess_with_markitdown(file_path: str) -> str:
    """
    Convert supported formats to text using markitdown.

    Args:
        file_path: Path to the file to convert

    Returns:
        Extracted text content from the file

    Raises:
        ImportError: If markitdown is not installed
    """
    try:
        from markitdown import MarkItDown
    except ImportError:
        raise ImportError(
            "markitdown is required for this file type. "
            "Install with: pip install recursive-cleaner[markitdown]"
        )

    md = MarkItDown()
    result = md.convert(file_path)
    return result.text_content


def chunk_file(
    file_path: str,
    chunk_size: int = 50,
    mode: Literal["auto", "structured", "text"] = "auto",
    chunk_overlap: int = 200,
    sampling_strategy: Literal["sequential", "random", "stratified"] = "sequential",
    stratify_field: str | None = None,
) -> list[str]:
    """
    Load and chunk a file based on its type.

    Args:
        file_path: Path to the file to chunk
        chunk_size: Number of items per chunk (rows for CSV/JSONL, items for JSON arrays)
                   For text mode, this is the character count per chunk.
        mode: "auto" detects from extension, "structured" for data, "text" for prose
        chunk_overlap: Character overlap between chunks (text mode only)
        sampling_strategy: "sequential" (default), "random", or "stratified"
        stratify_field: Field name for stratified sampling (JSONL only)

    Returns:
        List of string chunks suitable for LLM context

    Raises:
        ValueError: If non-sequential sampling requested for text mode
    """
    path = Path(file_path)
    suffix = path.suffix.lower()

    if not path.exists():
        raise FileNotFoundError(f"File not found: {file_path}")

    # Handle markitdown formats: preprocess to text, then chunk as text
    if suffix in MARKITDOWN_EXTENSIONS:
        content = preprocess_with_markitdown(file_path)
        if not content.strip():
            return []
        # Markitdown output is always processed as text
        if sampling_strategy != "sequential":
            raise ValueError(
                f"Text mode only supports 'sequential' sampling, got '{sampling_strategy}'"
            )
        return chunk_text_sentences(content, chunk_size, chunk_overlap)

    # Handle parquet files: load as list of dicts, chunk like JSONL
    if suffix == ".parquet":
        records = load_parquet(file_path)
        if not records:
            return []
        return _chunk_records(records, chunk_size, sampling_strategy, stratify_field)

    content = path.read_text(encoding="utf-8")

    if not content.strip():
        return []

    # Determine effective mode
    effective_mode = _detect_mode(suffix) if mode == "auto" else mode

    # Text mode only supports sequential sampling
    if effective_mode == "text" and sampling_strategy != "sequential":
        raise ValueError(
            f"Text mode only supports 'sequential' sampling, got '{sampling_strategy}'"
        )

    if effective_mode == "text":
        return chunk_text_sentences(content, chunk_size, chunk_overlap)
    elif suffix == ".csv":
        return _chunk_csv(content, chunk_size)
    elif suffix == ".json":
        return _chunk_json(content, chunk_size)
    elif suffix == ".jsonl":
        return _chunk_jsonl(content, chunk_size, sampling_strategy, stratify_field)
    else:
        # Fallback for structured mode with unknown extension
        return _chunk_text(content, chunk_size * 80)


def _detect_mode(suffix: str) -> Literal["structured", "text"]:
    """Detect mode from file extension."""
    structured_extensions = {".jsonl", ".csv", ".json", ".parquet"}
    if suffix in structured_extensions:
        return "structured"
    return "text"


def chunk_text_sentences(
    content: str, chunk_size: int, chunk_overlap: int = 200
) -> list[str]:
    """
    Chunk text with sentence-awareness and overlap.

    Uses vendored SentenceChunker if available, otherwise falls back to
    paragraph-based chunking.

    Args:
        content: Text content to chunk
        chunk_size: Maximum characters per chunk
        chunk_overlap: Character overlap between chunks

    Returns:
        List of text chunks
    """
    # Ensure chunk_overlap is less than chunk_size
    effective_overlap = min(chunk_overlap, chunk_size - 1) if chunk_size > 1 else 0

    if _HAS_SENTENCE_CHUNKER:
        chunker = SentenceChunker(
            chunk_size=chunk_size,
            chunk_overlap=effective_overlap,
        )
        chunks = chunker.chunk(content)
        return [c.text for c in chunks if c.text.strip()]

    # Fallback: paragraph-based chunking with overlap
    return _chunk_text_paragraphs(content, chunk_size, effective_overlap)


def _chunk_text_paragraphs(
    content: str, chunk_size: int, chunk_overlap: int
) -> list[str]:
    """
    Fallback paragraph-based chunking when SentenceChunker is unavailable.

    Splits on paragraph boundaries (double newlines), then groups paragraphs
    to fit within chunk_size while maintaining overlap.

    Args:
        content: Text content to chunk
        chunk_size: Maximum characters per chunk
        chunk_overlap: Character overlap between chunks

    Returns:
        List of text chunks with overlap
    """
    # Split on paragraph boundaries
    paragraphs = re.split(r"\n\n+", content.strip())
    paragraphs = [p.strip() for p in paragraphs if p.strip()]

    if not paragraphs:
        return []

    chunks = []
    current_chunk_parts: list[str] = []
    current_length = 0

    for para in paragraphs:
        para_len = len(para)

        # If single paragraph exceeds chunk_size, split it further
        if para_len > chunk_size:
            # Flush current chunk first
            if current_chunk_parts:
                chunks.append("\n\n".join(current_chunk_parts))
                current_chunk_parts = []
                current_length = 0

            # Split large paragraph by sentences
            sentences = re.split(r"(?<=[.!?])\s+", para)
            for sent in sentences:
                if len(sent) > chunk_size:
                    # Last resort: character split
                    for i in range(0, len(sent), chunk_size - chunk_overlap):
                        chunk_text = sent[i : i + chunk_size]
                        if chunk_text.strip():
                            chunks.append(chunk_text.strip())
                else:
                    if current_length + len(sent) + 1 > chunk_size and current_chunk_parts:
                        chunks.append("\n\n".join(current_chunk_parts))
                        # Keep overlap from last chunk
                        overlap_text = "\n\n".join(current_chunk_parts)[-chunk_overlap:]
                        current_chunk_parts = [overlap_text] if overlap_text.strip() else []
                        current_length = len(overlap_text) if overlap_text.strip() else 0
                    current_chunk_parts.append(sent)
                    current_length += len(sent) + 2
            continue

        # Check if adding this paragraph exceeds limit
        new_length = current_length + para_len + (2 if current_chunk_parts else 0)
        if new_length > chunk_size and current_chunk_parts:
            # Flush current chunk
            chunks.append("\n\n".join(current_chunk_parts))
            # Start new chunk with overlap
            overlap_text = "\n\n".join(current_chunk_parts)[-chunk_overlap:]
            if overlap_text.strip():
                current_chunk_parts = [overlap_text]
                current_length = len(overlap_text)
            else:
                current_chunk_parts = []
                current_length = 0

        current_chunk_parts.append(para)
        current_length += para_len + 2

    # Don't forget the last chunk
    if current_chunk_parts:
        chunks.append("\n\n".join(current_chunk_parts))

    return chunks


def _chunk_text(content: str, char_count: int) -> list[str]:
    """Chunk text by character count (legacy, no overlap)."""
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


def _chunk_jsonl(
    content: str,
    line_count: int,
    sampling_strategy: Literal["sequential", "random", "stratified"] = "sequential",
    stratify_field: str | None = None,
) -> list[str]:
    """Chunk JSONL by line count with optional sampling."""
    lines = [line.strip() for line in content.strip().split("\n") if line.strip()]

    if not lines:
        return []

    # Apply sampling strategy
    if sampling_strategy == "random":
        seed = _compute_seed(content)
        lines = _shuffle_records(lines, seed)
    elif sampling_strategy == "stratified" and stratify_field:
        seed = _compute_seed(content)
        lines = _stratified_sample(lines, stratify_field, seed)

    chunks = []
    for i in range(0, len(lines), line_count):
        chunk_lines = lines[i:i + line_count]
        chunks.append("\n".join(chunk_lines))

    return chunks


def _chunk_records(
    records: list[dict],
    item_count: int,
    sampling_strategy: Literal["sequential", "random", "stratified"] = "sequential",
    stratify_field: str | None = None,
) -> list[str]:
    """Chunk a list of dicts by item count with optional sampling."""
    if not records:
        return []

    # For seed computation, use JSON representation
    seed = _compute_seed(json.dumps(records[0]))

    # Apply sampling strategy
    if sampling_strategy == "random":
        records = _shuffle_records(records, seed)
    elif sampling_strategy == "stratified" and stratify_field:
        records = _stratified_sample_dicts(records, stratify_field, seed)

    chunks = []
    for i in range(0, len(records), item_count):
        chunk_records = records[i:i + item_count]
        # Convert to JSONL format for LLM context
        chunk_lines = [json.dumps(r) for r in chunk_records]
        chunks.append("\n".join(chunk_lines))

    return chunks


def _stratified_sample_dicts(records: list[dict], field: str, seed: int) -> list[dict]:
    """Group dicts by field, interleave proportionally."""
    groups: dict[str, list] = {}
    for record in records:
        key = str(record.get(field, "_missing_"))
        if key not in groups:
            groups[key] = []
        groups[key].append(record)

    # Shuffle within each group
    rng = random.Random(seed)
    for key in groups:
        rng.shuffle(groups[key])

    # Interleave from groups (round-robin)
    result = []
    group_lists = list(groups.values())
    while any(group_lists):
        for g in group_lists:
            if g:
                result.append(g.pop(0))
        group_lists = [g for g in group_lists if g]

    return result


def _compute_seed(content: str) -> int:
    """Compute deterministic seed from content hash."""
    return int(hashlib.md5(content.encode("utf-8")).hexdigest()[:8], 16)


def _shuffle_records(records: list, seed: int) -> list:
    """Deterministically shuffle records."""
    result = records.copy()
    rng = random.Random(seed)
    rng.shuffle(result)
    return result


def _stratified_sample(records: list, field: str, seed: int) -> list:
    """Group by field, interleave proportionally."""
    # Group records by field value
    groups: dict[str, list] = {}
    for record in records:
        try:
            data = json.loads(record)
            key = str(data.get(field, "_missing_"))
        except (json.JSONDecodeError, TypeError):
            key = "_invalid_"
        if key not in groups:
            groups[key] = []
        groups[key].append(record)

    # Shuffle within each group
    rng = random.Random(seed)
    for key in groups:
        rng.shuffle(groups[key])

    # Interleave from groups (round-robin)
    result = []
    group_lists = list(groups.values())
    while any(group_lists):
        for g in group_lists:
            if g:
                result.append(g.pop(0))
        group_lists = [g for g in group_lists if g]

    return result

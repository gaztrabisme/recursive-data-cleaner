# v1.0.0 API Contract - Apply Mode

## Python API

### `apply_cleaning()`

```python
def apply_cleaning(
    input_path: str,
    functions_path: str,
    output_path: str | None = None,
    on_progress: Callable[[dict], None] | None = None,
) -> str:
    """
    Apply cleaning functions to a data file.

    Args:
        input_path: Path to input data file
        functions_path: Path to cleaning_functions.py
        output_path: Path for output file (default: input.cleaned.ext)
        on_progress: Optional progress callback

    Returns:
        Path to output file

    Raises:
        FileNotFoundError: If input or functions file not found
        ImportError: If functions file cannot be imported
        ValueError: If input format is unsupported
    """
```

### Progress Events

```python
{"type": "apply_start", "total_records": int | None}  # None if unknown (streaming)
{"type": "apply_progress", "records_processed": int}
{"type": "apply_complete", "total_records": int, "output_path": str}
```

## CLI Contract

### Command: `apply`

```bash
recursive-cleaner apply <FILE> -f <FUNCTIONS> [-o OUTPUT]
```

### Arguments

| Argument | Required | Default | Description |
|----------|----------|---------|-------------|
| `FILE` | Yes | - | Input data file |
| `-f/--functions` | Yes | - | Path to cleaning_functions.py |
| `-o/--output` | No | `<input>.cleaned.<ext>` | Output file path |

### Exit Codes

| Code | Meaning |
|------|---------|
| 0 | Success |
| 1 | File not found |
| 2 | Import error (invalid functions file) |
| 3 | Runtime error during apply |

### Example Usage

```bash
# Data files - same format out
recursive-cleaner apply data.jsonl -f cleaning_functions.py -o cleaned.jsonl
recursive-cleaner apply customers.csv -f cleaning_functions.py
recursive-cleaner apply sales.xlsx -f cleaning_functions.py

# Text files - markdown out
recursive-cleaner apply document.pdf -f cleaning_functions.py -o cleaned.md
```

## Format Support

### Data Formats (Records → Same Format)

| Extension | Read With | Write With | Streaming | Dependency |
|-----------|-----------|------------|-----------|------------|
| `.jsonl` | stdlib | stdlib | Yes | None |
| `.csv` | stdlib | stdlib | Yes | None |
| `.json` | stdlib | stdlib | No | None |
| `.parquet` | pyarrow | pyarrow | No | `[parquet]` |
| `.xlsx` | openpyxl | openpyxl | No | `[excel]` |
| `.xls` | xlrd | → `.xlsx` | No | `[excel]` |

### Text Formats (Document → Markdown)

| Extension | Read With | Output |
|-----------|-----------|--------|
| `.txt` | stdlib | `.md` |
| `.pdf` | markitdown | `.md` |
| `.docx`, `.doc` | markitdown | `.md` |
| `.pptx`, `.ppt` | markitdown | `.md` |
| `.html`, `.htm` | markitdown | `.md` |
| `.epub` | markitdown | `.md` |
| `.msg` | markitdown | `.md` |
| `.rtf` | markitdown | `.md` |
| `.odt`, `.odp` | markitdown | `.md` |

## Error Handling

- **File not found**: Raise `FileNotFoundError` with clear message
- **Import failure**: Raise `ImportError` with details
- **Cleaning function error**: Propagate exception (fail fast)

## TUI Enhancement: Transmission Log Colors

| Element | Color |
|---------|-------|
| XML tags `<name>` | `cyan` |
| Attributes `solved="true"` | `yellow` |
| Function names | `green` |
| Issue (unsolved) | `bright_white` |
| Issue (solved) | `dim` |
| Code blocks | Syntax highlighted |
| `clean` status | `green` |
| `needs_more_work` | `yellow` |
| Docstrings | `italic` |
| Issue accent | Cycle: `blue` → `magenta` → `cyan` → `yellow` |

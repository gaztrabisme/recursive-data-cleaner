# v1.0.0 Implementation Plan

## Overview

Implement Apply mode to apply generated cleaning functions to full datasets, plus TUI enhancements for colored transmission log.

## Technology Stack

| Layer | Choice | Rationale |
|-------|--------|-----------|
| Core | stdlib | json, csv, importlib for dynamic import |
| Excel | openpyxl, xlrd | Industry standard, optional dep |
| TUI | Rich | Already used in v0.8.0 |

## Phase Breakdown

### Phase 1: Core Apply Function (~80 lines)

**Objective:** Create `apply.py` with streaming support for core formats.

**Deliverables:**
- [ ] `recursive_cleaner/apply.py`
- [ ] `load_cleaning_module()` - dynamic import of cleaning_functions.py
- [ ] `apply_to_jsonl()` - streaming line-by-line
- [ ] `apply_to_csv()` - streaming with DictReader/DictWriter
- [ ] `apply_to_json()` - batch array processing
- [ ] `apply_cleaning()` - main entry point with format routing
- [ ] Progress callback support

**Implementation:**
```python
# apply.py structure
def load_cleaning_module(functions_path: str):
    """Import cleaning_functions.py dynamically."""

def apply_to_jsonl(input_path, output_path, clean_fn, on_progress):
    """Stream JSONL: read line → clean → write line."""

def apply_to_csv(input_path, output_path, clean_fn, on_progress):
    """Stream CSV: DictReader → clean → DictWriter."""

def apply_to_json(input_path, output_path, clean_fn, on_progress):
    """Batch JSON array: load all → clean each → write array."""

def apply_cleaning(input_path, functions_path, output_path=None, on_progress=None):
    """Main entry point. Route by extension."""
```

**Dependencies:** None (stdlib only)

---

### Phase 2: CLI Integration (~40 lines)

**Objective:** Add `apply` subcommand to CLI.

**Deliverables:**
- [ ] `cmd_apply()` function in `cli.py`
- [ ] Argument parser with `-f/--functions`, `-o/--output`
- [ ] Error handling with correct exit codes
- [ ] Progress output

**Implementation:**
```python
# In cli.py
def cmd_apply(args) -> int:
    """Handle the apply command."""
    # Validate files exist
    # Call apply_cleaning()
    # Handle errors with correct exit codes

# In create_parser()
apply_parser = subparsers.add_parser("apply", help="Apply cleaning functions to data")
apply_parser.add_argument("file", help="Input data file")
apply_parser.add_argument("-f", "--functions", required=True)
apply_parser.add_argument("-o", "--output")
```

**Dependencies:** Phase 1

---

### Phase 3: Extended Format Support (~60 lines)

**Objective:** Add Parquet, Excel, and text format support.

**Deliverables:**
- [ ] `apply_to_parquet()` - pyarrow read/write
- [ ] `apply_to_excel()` - openpyxl read/write
- [ ] `apply_to_text()` - markitdown → clean → markdown out
- [ ] Default output path: `input.cleaned.ext`
- [ ] `.xls` input → `.xlsx` output

**Implementation:**
```python
def apply_to_parquet(input_path, output_path, clean_fn, on_progress):
    """Batch: pyarrow.read_table → clean each → write_table."""

def apply_to_excel(input_path, output_path, clean_fn, on_progress):
    """Batch: openpyxl load → clean each row → save."""

def apply_to_text(input_path, output_path, clean_fn, on_progress):
    """Load text/markitdown → clean → write .md."""

def get_default_output_path(input_path: str, force_ext: str | None = None) -> str:
    """Generate input.cleaned.ext path."""
```

**Dependencies:** Phase 1, optional deps (pyarrow, openpyxl, xlrd, markitdown)

---

### Phase 4: TUI Enhancement (~50 lines)

**Objective:** Add colored parsing to transmission log.

**Deliverables:**
- [ ] `colorize_transmission()` function in `tui.py`
- [ ] XML tag detection and coloring
- [ ] Attribute coloring
- [ ] Status value coloring
- [ ] Issue accent cycling

**Implementation:**
```python
# In tui.py
ISSUE_COLORS = ["blue", "magenta", "cyan", "yellow"]

def colorize_transmission(text: str) -> Text:
    """Parse XML response and apply colors."""
    # Regex patterns for:
    # - <tag> → cyan
    # - attr="value" → yellow
    # - <name>func_name</name> → green for func_name
    # - solved="true" → dim
    # - solved="false" → bright_white
    # - <chunk_status>clean</chunk_status> → green
    # - <chunk_status>needs_more_work</chunk_status> → yellow
```

**Dependencies:** None (Rich already installed for TUI)

---

### Phase 5: Tests (~200 lines)

**Objective:** Comprehensive test coverage for apply mode.

**Deliverables:**
- [ ] `tests/test_apply.py`
- [ ] Unit tests for each format (JSONL, CSV, JSON, Parquet, Excel, text)
- [ ] Integration test with real cleaning functions
- [ ] Error case tests (file not found, import error, cleaning error)
- [ ] Progress callback tests
- [ ] TUI colorization tests

**Test Structure:**
```python
class TestApplyJSONL:
    def test_basic_apply(self): ...
    def test_streaming_large_file(self): ...
    def test_progress_callback(self): ...

class TestApplyCSV:
    def test_basic_apply(self): ...
    def test_preserves_headers(self): ...

class TestApplyExcel:
    def test_xlsx_round_trip(self): ...
    def test_xls_to_xlsx(self): ...

class TestApplyText:
    def test_txt_to_md(self): ...
    def test_pdf_to_md(self): ...

class TestApplyErrors:
    def test_file_not_found(self): ...
    def test_import_error(self): ...
    def test_cleaning_function_error(self): ...

class TestTUIColors:
    def test_tag_coloring(self): ...
    def test_issue_accent_cycling(self): ...
```

**Dependencies:** Phases 1-4

---

## File Changes Summary

| File | Action | Lines |
|------|--------|-------|
| `recursive_cleaner/apply.py` | Create | ~140 |
| `recursive_cleaner/cli.py` | Modify | +40 |
| `recursive_cleaner/tui.py` | Modify | +50 |
| `recursive_cleaner/__init__.py` | Modify | +1 |
| `tests/test_apply.py` | Create | ~200 |
| `pyproject.toml` | Modify | +3 |
| `README.md` | Modify | +20 |
| `CLAUDE.md` | Modify | +5 |

**Total new code:** ~230 lines (excluding tests)

---

## Risk Register

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| openpyxl API changes | Low | Low | Pin version, test against multiple |
| Large Excel files OOM | Medium | Medium | Document limitation, recommend CSV for huge files |
| Cleaning function import fails | Low | High | Clear error messages, validate file exists first |

---

## Out of Scope

- ODS format (defer to v1.1)
- Parallel processing for large files
- Partial apply (resume from checkpoint)
- Apply with TUI progress display (future enhancement)

---

## Execution Order

1. Phase 1: Core apply.py (JSONL, CSV, JSON)
2. Phase 2: CLI integration
3. Phase 3: Extended formats (Parquet, Excel, text)
4. Phase 4: TUI colors
5. Phase 5: Tests
6. Documentation update
7. Version bump to 1.0.0

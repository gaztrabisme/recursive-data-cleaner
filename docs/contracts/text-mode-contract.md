# Contract: Text Mode + Vendored Chunker (v0.3.0)

## Overview

Add text/prose cleaning mode to DataCleaner with sentence-aware chunking via vendored chonkie code.

---

## API Contract

### DataCleaner Constructor Changes

```python
DataCleaner(
    llm_backend: LLMBackend,
    file_path: str,
    chunk_size: int = 50,              # records for structured, chars for text
    instructions: str = "",
    max_iterations: int = 5,
    context_budget: int = 8000,
    on_progress: Callable[[dict], None] | None = None,
    state_file: str | None = None,
    validate_runtime: bool = True,
    schema_sample_size: int = 10,
    # NEW v0.3.0
    mode: Literal["auto", "structured", "text"] = "auto",
    chunk_overlap: int = 200,          # chars overlap for text mode
)
```

### Mode Detection Rules

| Extension | Auto-detected Mode |
|-----------|-------------------|
| `.jsonl` | structured |
| `.csv` | structured |
| `.json` | structured |
| `.txt` | text |
| `.md` | text |
| other | text (fallback) |

### Text Mode Behavior

| Aspect | Structured Mode | Text Mode |
|--------|-----------------|-----------|
| Chunking | By record count | By char count with sentence-awareness |
| Chunk overlap | None | `chunk_overlap` chars |
| Schema inference | Yes | Skip (return empty) |
| Function signature | `def func(data: dict)` | `def func(text: str)` |
| Validation input | `list[dict]` | `str` |
| Prompt template | `STRUCTURED_PROMPT` | `TEXT_PROMPT` |

---

## Data Schema Contract

### Chunk (vendored from chonkie)

```python
@dataclass
class Chunk:
    text: str           # The chunk content
    start_index: int    # Position in original text
    end_index: int      # End position in original text
    token_count: int    # Character count (we use chars, not tokens)
```

### SentenceChunker Parameters

```python
SentenceChunker(
    chunk_size: int = 4000,           # Max chars per chunk
    chunk_overlap: int = 200,         # Overlap between chunks
    min_sentences_per_chunk: int = 1, # Minimum sentences
    min_characters_per_sentence: int = 12,  # Merge short sentences
    delim: list[str] = [". ", "! ", "? ", "\n"],  # Sentence boundaries
)
```

---

## Success Criteria

### Phase 1: Vendor Chunker
- [ ] `recursive_cleaner/vendor/__init__.py` exists
- [ ] `recursive_cleaner/vendor/chunker.py` contains SentenceChunker (~150 lines)
- [ ] MIT attribution comment present
- [ ] `tests/test_vendor_chunker.py` with 5+ tests
- [ ] All tests pass: `pytest tests/test_vendor_chunker.py -v`

### Phase 2: Text Mode
- [ ] `mode` parameter added to DataCleaner
- [ ] Mode auto-detection works (`.txt` → text, `.jsonl` → structured)
- [ ] `TEXT_PROMPT_TEMPLATE` in prompt.py
- [ ] Text chunking uses SentenceChunker with overlap
- [ ] Schema inference skipped for text mode
- [ ] Validation handles `str` input for text mode
- [ ] `tests/test_text_mode.py` with 8+ tests
- [ ] All tests pass: `pytest tests/test_text_mode.py -v`

### Phase 3: Integration
- [ ] End-to-end test with sample text file
- [ ] Generated cleaning functions are valid Python
- [ ] Functions use `def func(text: str)` signature
- [ ] All 127+ existing tests still pass

### Overall
- [ ] Total line count < 1150 (currently 977 + ~150 vendor + ~50 text mode)
- [ ] No new external dependencies
- [ ] Version bumped to 0.3.0

---

## Text Prompt Template

```python
TEXT_PROMPT_TEMPLATE = '''You are a text cleaning expert. Analyze text and generate Python functions to fix issues.

=== USER'S CLEANING GOALS ===
{instructions}

=== EXISTING FUNCTIONS (DO NOT RECREATE) ===
{context}

=== TEXT CHUNK ===
{chunk}

=== TASK ===
1. List ALL text quality issues (artifacts, spacing, OCR errors, formatting)
2. Mark each as solved="true" if an existing function handles it
3. Generate code for ONLY the FIRST unsolved issue
4. Use this EXACT format:

<cleaning_analysis>
  <issues_detected>
    <issue id="1" solved="true|false">Description of issue</issue>
  </issues_detected>

  <function_to_generate>
    <name>function_name</name>
    <docstring>What it does, edge cases handled</docstring>
    <code>
```python
def function_name(text: str) -> str:
    # Complete implementation
    return text
```
    </code>
  </function_to_generate>

  <chunk_status>clean|needs_more_work</chunk_status>
</cleaning_analysis>

RULES:
- ONE function per response
- Function takes text string, returns cleaned text string
- If all issues solved: <chunk_status>clean</chunk_status>, omit <function_to_generate>
- Function must be idempotent (safe to run multiple times)
- Use ```python markdown blocks for code'''
```

---

## File Structure

```
recursive_cleaner/
    vendor/
        __init__.py          # Export SentenceChunker, Chunk
        chunker.py           # Vendored chonkie code (~150 lines)
    cleaner.py               # Add mode parameter, text handling
    prompt.py                # Add TEXT_PROMPT_TEMPLATE
    parsers.py               # Use SentenceChunker for text mode
    validation.py            # Handle str input for text mode
tests/
    test_vendor_chunker.py   # Chunker tests
    test_text_mode.py        # Text mode tests
```

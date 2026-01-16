# CLAUDE.md - Recursive Docstring Data Cleaning Pipeline

## Project Status

| Version | Status | Date |
|---------|--------|------|
| v0.6.0 | **Implemented** | 2025-01-15 |
| v0.5.1 | Implemented | 2025-01-15 |
| v0.5.0 | Implemented | 2025-01-15 |
| v0.4.0 | Implemented | 2025-01-15 |
| v0.3.0 | Implemented | 2025-01-14 |
| v0.2.0 | Implemented | 2025-01-14 |
| v0.1.0 | Implemented | 2025-01-14 |

**Current State**: v0.6.0 complete. 392 tests passing, 2,967 lines total.

### Version History
- **v0.6.0**: Latency metrics, import consolidation, cleaning report, dry-run mode
- **v0.5.1**: Dangerous code detection (AST-based security)
- **v0.5.0**: Two-pass optimization with LLM agency (consolidation, early termination)
- **v0.4.0**: Holdout validation, dependency resolution, smart sampling, quality metrics
- **v0.3.0**: Text mode with vendored sentence-aware chunker
- **v0.2.0**: Runtime validation, schema inference, callbacks, incremental saves
- **v0.1.0**: Core pipeline

## Project Overview

A Python library that uses LLMs to incrementally build data cleaning solutions for massive datasets. The system processes data in chunks, identifies quality issues, generates Python functions to solve them one at a time, and maintains awareness of existing solutions through docstring feedback loops.

**Core Philosophy**: Elegant, clean, lean, path of least resistance. Trade computational efficiency for human time savings. No frameworks, no abstractions we don't need, just a while loop with good error handling.

## Design Principles

1. **Simplicity over extensibility** - A 500-line library that does one thing well beats a 5000-line framework
2. **stdlib over dependencies** - Use `ast.parse()`, `xml.etree`, not custom parsers
3. **Functions over classes** - Unless state genuinely helps
4. **Delete over abstract** - No interfaces for things with one implementation
5. **Retry over recover** - On error, retry with error message appended to prompt

## Target User Experience

```python
from recursive_cleaner import DataCleaner

cleaner = DataCleaner(
    llm_backend=my_ollama_client,  # User-provided LLM interface
    file_path="messy_customers.jsonl",
    chunk_size=50,  # items per chunk
    instructions="""
    CRM export data that needs:
    - Phone numbers normalized to E.164 format
    - Fix typos in 'status' field (valid: active, pending, churned)
    - Remove duplicates by email
    - All dates to ISO 8601
    """,
    # Validation & schema (v0.2.0)
    on_progress=lambda e: print(f"{e['type']}: {e.get('chunk_index', '')}"),
    state_file="cleaning_state.json",  # Resume on interrupt
    validate_runtime=True,  # Test functions before accepting
    schema_sample_size=10,  # Infer schema from first N records
    # Sampling & metrics (v0.4.0)
    holdout_ratio=0.2,  # Test on hidden 20% of each chunk
    sampling_strategy="stratified",  # "sequential", "random", or "stratified"
    stratify_field="status",  # Field for stratified sampling
    track_metrics=True,  # Measure before/after quality
    # Optimization (v0.5.0)
    optimize=True,  # Consolidate redundant functions after generation
    early_termination=True,  # Stop when patterns saturate
    # Observability (v0.6.0)
    report_path="cleaning_report.md",  # Generate markdown report (None to disable)
    dry_run=False,  # Set True to analyze without generating functions
)

cleaner.run()  # Outputs: cleaning_functions.py, cleaning_report.md

# Check improvement metrics
print(cleaner.get_improvement_report())

# Or resume from saved state
cleaner = DataCleaner.resume("cleaning_state.json", my_ollama_client)
cleaner.run()
```

## Core Concepts

### 1. Chunked Processing
Large files exceed LLM context windows. Process in chunks:
- **Text files**: By character count (default 4000)
- **CSV/JSON/JSONL**: By item count (default 50)

### 2. Docstring Registry (Context Memory)
Each generated function's docstring is fed back into subsequent prompts. Simple list, most recent N functions, character budget.

```python
def build_context(functions: list[dict], max_chars: int = 8000) -> str:
    """Most recent functions that fit in budget. That's it."""
    ctx = ""
    for f in reversed(functions):
        entry = f"## {f['name']}\n{f['docstring']}\n\n"
        if len(ctx) + len(entry) > max_chars:
            break
        ctx = entry + ctx
    return ctx or "(No functions generated yet)"
```

### 3. Single-Problem Focus
Per chunk iteration:
1. LLM identifies ALL issues in chunk
2. LLM checks which are already solved (by reviewing docstrings)
3. LLM generates code for ONLY the first unsolved issue
4. Repeat until "clean" or max iterations (default 5)

### 4. XML Output with Markdown Code Blocks
XML wrapper for structure, markdown fences for code (handles LLM variance):

```xml
<cleaning_analysis>
  <issues_detected>
    <issue id="1" solved="false">Phone numbers have inconsistent formats</issue>
    <issue id="2" solved="true">Already handled by normalize_dates()</issue>
  </issues_detected>

  <function_to_generate>
    <name>normalize_phone_numbers</name>
    <docstring>
    Normalize phone numbers to E.164 format.
    Handles: +1-555-1234, (555) 123-4567, raw digits
    </docstring>
    <code>
```python
import re

def normalize_phone_numbers(data):
    # Implementation...
    pass
```
    </code>
  </function_to_generate>

  <chunk_status>needs_more_work</chunk_status>
</cleaning_analysis>
```

## The Lean Architecture (~2,967 lines total)

### File Structure (Implemented)
```
recursive_cleaner/
    __init__.py          # Public exports (~45 lines)
    cleaner.py           # Main DataCleaner class (~580 lines)
    context.py           # Docstring registry with FIFO eviction (~27 lines)
    dependencies.py      # Topological sort for function ordering (~59 lines) [v0.4.0]
    errors.py            # 4 exception classes (~17 lines)
    metrics.py           # Quality metrics before/after (~163 lines) [v0.4.0]
    optimizer.py         # Two-pass consolidation with LLM agency (~336 lines) [v0.5.0]
    output.py            # Function file generation (~195 lines)
    parsers.py           # Chunk text/csv/json/jsonl with sampling (~325 lines)
    prompt.py            # LLM prompt templates (~218 lines)
    report.py            # Markdown report generation (~120 lines) [v0.6.0]
    response.py          # XML/markdown parsing + agency dataclasses (~292 lines)
    schema.py            # Schema inference (~117 lines) [v0.2.0]
    types.py             # LLMBackend protocol (~11 lines)
    validation.py        # Runtime validation + safety checks (~200 lines)
    vendor/
        __init__.py      # Vendor exports (~4 lines)
        chunker.py       # Vendored sentence-aware chunker (~187 lines) [v0.3.0]

backends/
    __init__.py          # Backend exports
    mlx_backend.py       # MLX-LM backend for Apple Silicon

tests/                   # 392 tests
    test_callbacks.py    # Progress callback tests
    test_cleaner.py      # DataCleaner tests
    test_context.py      # Context management tests
    test_dependencies.py # Dependency resolution tests [v0.4.0]
    test_dry_run.py      # Dry run mode tests [v0.6.0]
    test_holdout.py      # Holdout validation tests [v0.4.0]
    test_incremental.py  # Incremental save tests
    test_integration.py  # End-to-end tests
    test_latency.py      # Latency metrics tests [v0.6.0]
    test_metrics.py      # Quality metrics tests [v0.4.0]
    test_optimizer.py    # Two-pass optimization tests [v0.5.0]
    test_output.py       # Output generation tests
    test_parsers.py      # Parsing tests
    test_report.py       # Cleaning report tests [v0.6.0]
    test_sampling.py     # Sampling strategy tests [v0.4.0]
    test_schema.py       # Schema inference tests
    test_text_mode.py    # Text mode tests [v0.3.0]
    test_validation.py   # Runtime validation + safety tests
    test_vendor_chunker.py  # Vendored chunker tests [v0.3.0]

test_cases/              # Comprehensive test datasets
    ecommerce_*.jsonl    # Product catalog data
    healthcare_*.jsonl   # Patient records
    financial_*.jsonl    # Transaction data

docs/                    # Orchestrated dev docs
    contracts/           # API and data contracts
    research/            # Research findings
    handoffs/            # Phase completion handoffs

pyproject.toml
```

### Error Classes (18 lines)
```python
class CleanerError(Exception):
    """Base error for the pipeline"""

class ParseError(CleanerError):
    """XML or code extraction failed - retry with error feedback"""

class MaxIterationsError(CleanerError):
    """Chunk never marked clean - skip and continue"""

class OutputValidationError(CleanerError):
    """Generated output file has invalid Python syntax"""
```

### LLM Backend Protocol (5 lines)
```python
from typing import Protocol

class LLMBackend(Protocol):
    def generate(self, prompt: str) -> str: ...
```

### Retry Logic (use tenacity)
```python
from tenacity import retry, stop_after_attempt, wait_exponential

@retry(stop=stop_after_attempt(3), wait=wait_exponential(min=1, max=10))
def call_llm(backend: LLMBackend, prompt: str) -> str:
    return backend.generate(prompt)
```

### Response Parsing (~30 lines)
```python
import ast
import re
import xml.etree.ElementTree as ET

def parse_response(text: str) -> dict:
    """Extract structured data from LLM response."""
    try:
        # Find XML content
        root = ET.fromstring(f"<root>{text}</root>")

        # Extract code from markdown fence
        code_elem = root.find(".//code")
        code_text = code_elem.text if code_elem is not None else ""
        code = extract_python_block(code_text)

        # Validate Python syntax
        ast.parse(code)

        return {
            "issues": parse_issues(root),
            "name": root.findtext(".//name", "").strip(),
            "docstring": root.findtext(".//docstring", "").strip(),
            "code": code,
            "status": root.findtext(".//chunk_status", "needs_more_work").strip()
        }
    except ET.ParseError as e:
        raise ParseError(f"Invalid XML: {e}")
    except SyntaxError as e:
        raise ParseError(f"Invalid Python: {e}")

def extract_python_block(text: str) -> str:
    """Extract code from ```python ... ``` block."""
    match = re.search(r"```python\s*(.*?)\s*```", text, re.DOTALL)
    return match.group(1) if match else text.strip()
```

### The Main Loop (~80 lines)
```python
class DataCleaner:
    def __init__(self, llm_backend, file_path, chunk_size=50,
                 instructions="", max_iterations=5, context_budget=8000):
        self.backend = llm_backend
        self.file_path = file_path
        self.chunk_size = chunk_size
        self.instructions = instructions
        self.max_iterations = max_iterations
        self.context_budget = context_budget
        self.functions = []  # List of {name, docstring, code}

    def run(self):
        chunks = self._load_chunks()

        for i, chunk in enumerate(chunks):
            print(f"Processing chunk {i+1}/{len(chunks)}...")
            self._process_chunk(chunk, i)

        self._write_output()
        print(f"Done! Generated {len(self.functions)} functions.")

    def _process_chunk(self, chunk, chunk_idx):
        for iteration in range(self.max_iterations):
            prompt = self._build_prompt(chunk)

            try:
                response = call_llm(self.backend, prompt)
                result = parse_response(response)
            except ParseError as e:
                # Retry with error feedback
                prompt += f"\n\nYour previous response had an error: {e}\nPlease try again."
                continue

            if result["status"] == "clean":
                return

            if result["code"]:
                self.functions.append({
                    "name": result["name"],
                    "docstring": result["docstring"],
                    "code": result["code"]
                })

        print(f"  Warning: chunk {chunk_idx} hit max iterations")

    def _build_prompt(self, chunk):
        context = build_context(self.functions, self.context_budget)
        return PROMPT_TEMPLATE.format(
            instructions=self.instructions,
            context=context,
            chunk=chunk
        )

    def _write_output(self):
        # Generate cleaning_functions.py with all functions
        # and a clean_data() entrypoint
        ...
```

## Prompt Template

```python
PROMPT_TEMPLATE = '''You are a data cleaning expert. Analyze data and generate Python functions to fix issues.

=== USER'S CLEANING GOALS ===
{instructions}

=== EXISTING FUNCTIONS (DO NOT RECREATE) ===
{context}

=== DATA CHUNK ===
{chunk}

=== TASK ===
1. List ALL data quality issues
2. Mark each as solved="true" if an existing function handles it
3. Generate code for ONLY the FIRST unsolved issue
4. Use this EXACT format:

<cleaning_analysis>
  <issues_detected>
    <issue id="1" solved="true|false">Description</issue>
  </issues_detected>

  <function_to_generate>
    <name>function_name</name>
    <docstring>What it does, edge cases handled</docstring>
    <code>
```python
def function_name(data):
    # Complete implementation
    pass
```
    </code>
  </function_to_generate>

  <chunk_status>clean|needs_more_work</chunk_status>
</cleaning_analysis>

RULES:
- ONE function per response
- If all issues solved: <chunk_status>clean</chunk_status>, omit <function_to_generate>
- Include imports in function or at top
- Function must be idempotent'''
```

## Dependencies

```toml
[project]
dependencies = [
    "tenacity>=8.0",  # Retry logic (battle-tested, 1 decorator)
]
```

That's it. No langchain, no frameworks, no abstractions.

## Edge Cases

| Case | Handling |
|------|----------|
| Malformed XML | Retry with error appended to prompt (max 3) |
| Invalid Python | Retry with syntax error in prompt (max 3) |
| `__main__` imports | Reject during parsing, retry with error feedback |
| Duplicate functions | Skip duplicates, keep first occurrence |
| Invalid combined output | Fall back to writing only valid functions |
| Chunk never "clean" | Skip after 5 iterations, log warning |
| Empty chunk | Skip without LLM call |
| Context too large | FIFO eviction, keep most recent functions |

## Known Limitations

1. **Stateful operations** (deduplication, aggregations) only work within chunks, not globally
2. ~~**Function ordering** follows generation order, not dependency order~~ → Fixed in v0.4.0 (dependency resolution)
3. ~~**No runtime testing** of generated functions before output~~ → Fixed in v0.2.0 (runtime validation)
4. ~~**Redundant functions** when similar issues appear in different chunks~~ → Fixed in v0.5.0 (two-pass consolidation)

## LLM Agency (v0.5.0)

The LLM now has agency over key decisions:

| Decision Point | LLM Decides |
|----------------|-------------|
| Chunk cleanliness | `chunk_status: clean/needs_more_work` |
| Consolidation complete | `complete: true/false` in self-assessment |
| Pattern saturation | `saturated: true/false` for early termination |

This follows the wu wei principle: let the model that understands the data make decisions about the data.

## Observability (v0.6.0)

New features for monitoring and analysis:

| Feature | Description |
|---------|-------------|
| Latency Metrics | Track LLM call timing (min/max/avg/total) via `llm_call` events |
| Import Consolidation | Merge duplicate imports, combine `from x import a, b` |
| Cleaning Report | Markdown summary with functions, metrics, latency stats |
| Dry-Run Mode | Analyze data without generating functions (`dry_run=True`) |

New events emitted:
- `llm_call` - After each LLM call with `latency_ms`
- `issues_detected` - In dry-run mode with detected issues
- `dry_run_complete` - End of dry run with stats
- `complete` now includes `latency_stats` dict

## Success Criteria

User with 500MB JSONL + clear instructions can:
1. Write 5 lines of setup
2. Run and walk away
3. Return to working `cleaning_functions.py`
4. Tweak edge cases
5. Apply to full dataset

---

**For A/B testing with advanced patterns, see `CLAUDE_ADVANCED.md`**

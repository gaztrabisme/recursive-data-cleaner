# CLAUDE.md - Recursive Docstring Data Cleaning Pipeline

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
    """
)

cleaner.run()  # Outputs: cleaning_functions.py
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

## The Lean Architecture (~300 lines total)

### File Structure
```
recursive_cleaner/
    __init__.py          # Exports DataCleaner
    cleaner.py           # Main class (~150 lines)
    parsers.py           # Chunk text/csv/json (~80 lines)
    errors.py            # 3 exception classes (~10 lines)

pyproject.toml
```

### Error Classes (10 lines)
```python
class CleanerError(Exception):
    """Base error for the pipeline"""

class ParseError(CleanerError):
    """XML or code extraction failed - retry with error feedback"""

class MaxIterationsError(CleanerError):
    """Chunk never marked clean - skip and continue"""
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
| Chunk never "clean" | Skip after 5 iterations, log warning |
| Empty chunk | Skip without LLM call |
| Context too large | FIFO eviction, keep most recent functions |

## Known Limitations

1. **Stateful operations** (deduplication, aggregations) only work within chunks, not globally
2. **Function ordering** follows generation order, not dependency order
3. **No runtime testing** of generated functions before output

## Success Criteria

User with 500MB JSONL + clear instructions can:
1. Write 5 lines of setup
2. Run and walk away
3. Return to working `cleaning_functions.py`
4. Tweak edge cases
5. Apply to full dataset

---

**For A/B testing with advanced patterns, see `CLAUDE_ADVANCED.md`**

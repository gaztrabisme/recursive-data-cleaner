# CLAUDE_ADVANCED.md - Framework-Inspired Architecture

> **For A/B testing against `CLAUDE.md` (lean version)**
>
> This document describes an architecture borrowing patterns from smolagents, LangChain, LangGraph, AutoGen, CrewAI, and Pydantic-AI. More extensible, more abstracted, potentially more robust for complex use cases.

## Project Overview

Same as lean version: LLM-powered incremental data cleaning with docstring feedback loops.

**Philosophy**: Borrow battle-tested patterns from production agent frameworks. More infrastructure upfront, potentially better error recovery and extensibility.

## Architecture Patterns Adopted

### From smolagents (HuggingFace)
- Typed memory steps with dataclasses
- Error hierarchy with logging integration
- AST-based code validation
- Callback system for extensibility
- Jinja2 prompt templates

### From LangChain
- Tenacity retry with exponential backoff + jitter
- Output fixing parser (LLM-powered error recovery)
- Summary buffer memory for context management
- Structured exception hierarchy

### From LangGraph
- TypedDict state with annotated reducers
- Checkpoint interface for persistence
- Conditional routing for iteration control

### From Pydantic-AI
- Output validator pattern (separated validation)
- ModelRetry exception for retry-with-feedback
- Clean exception categorization

### From CrewAI
- Guardrail system for chunk completion validation
- Task-centric workflow definition

---

## File Structure (~800 lines total)

```
recursive_cleaner/
    __init__.py
    cleaner.py              # Main orchestrator (~200 lines)
    state.py                # TypedDict state + reducers (~50 lines)
    memory.py               # Summary buffer registry (~100 lines)
    parsing.py              # XML + code extraction (~80 lines)
    validation.py           # Guardrails + validators (~100 lines)
    errors.py               # Exception hierarchy (~40 lines)
    callbacks.py            # Event hooks (~60 lines)
    prompts/
        system.yaml         # Jinja2 templates
        retry.yaml
    checkpoints.py          # Optional persistence (~80 lines)

pyproject.toml
```

---

## Exception Hierarchy (errors.py)

Inspired by smolagents + Pydantic-AI:

```python
from dataclasses import dataclass
from typing import Any

class CleanerError(Exception):
    """Base exception for all pipeline errors"""
    def __init__(self, message: str, context: dict[str, Any] | None = None):
        super().__init__(message)
        self.message = message
        self.context = context or {}

class ParseError(CleanerError):
    """XML parsing failed"""
    pass

class CodeValidationError(CleanerError):
    """Generated Python code is invalid"""
    def __init__(self, message: str, code: str, syntax_error: str):
        super().__init__(message, {"code": code, "syntax_error": syntax_error})
        self.code = code
        self.syntax_error = syntax_error

class RetryableError(CleanerError):
    """Error that should trigger retry with feedback to LLM"""
    def __init__(self, message: str, retry_prompt: str):
        super().__init__(message)
        self.retry_prompt = retry_prompt

class MaxIterationsError(CleanerError):
    """Chunk processing exceeded iteration limit"""
    def __init__(self, chunk_index: int, iterations: int):
        super().__init__(f"Chunk {chunk_index} exceeded {iterations} iterations")
        self.chunk_index = chunk_index
        self.iterations = iterations

class ChunkSkippedError(CleanerError):
    """Chunk was skipped due to unrecoverable errors"""
    pass
```

---

## Typed State with Reducers (state.py)

Inspired by LangGraph:

```python
from typing import Annotated, TypedDict
from dataclasses import dataclass, field
from datetime import datetime

def merge_dicts(current: dict, new: dict) -> dict:
    """Reducer: merge new keys into existing dict"""
    result = current.copy()
    result.update(new)
    return result

def append_list(current: list, new: list) -> list:
    """Reducer: append new items to list"""
    return current + new

@dataclass
class GeneratedFunction:
    name: str
    docstring: str
    code: str
    issues_solved: list[str]
    chunk_index: int
    created_at: datetime = field(default_factory=datetime.now)

@dataclass
class ChunkResult:
    chunk_index: int
    iterations: int
    status: str  # "clean" | "max_iterations" | "skipped"
    functions_generated: list[str]
    issues_found: int
    issues_solved: int

class PipelineState(TypedDict):
    # Accumulated across all chunks
    functions: Annotated[list[GeneratedFunction], append_list]
    docstring_registry: Annotated[dict[str, str], merge_dicts]
    chunk_results: Annotated[list[ChunkResult], append_list]

    # Current processing context
    current_chunk_index: int
    current_iteration: int
    total_chunks: int

    # Metadata
    file_path: str
    started_at: str
    errors: Annotated[list[dict], append_list]
```

---

## Summary Buffer Memory (memory.py)

Inspired by LangChain's ConversationSummaryBufferMemory:

```python
from dataclasses import dataclass
from typing import Protocol

class LLMBackend(Protocol):
    def generate(self, prompt: str) -> str: ...

@dataclass
class DocstringRegistry:
    """
    Manages docstring context with token budget.
    When budget exceeded: summarize old functions, keep recent verbatim.
    """
    llm_backend: LLMBackend
    max_tokens: int = 4000
    summary: str = ""
    recent_functions: list[dict] = None  # {name, docstring}

    def __post_init__(self):
        self.recent_functions = self.recent_functions or []

    def add(self, name: str, docstring: str):
        self.recent_functions.append({"name": name, "docstring": docstring})
        self._prune_if_needed()

    def _count_tokens(self) -> int:
        # Approximate: 1 token ~= 4 chars
        total = len(self.summary)
        for f in self.recent_functions:
            total += len(f["name"]) + len(f["docstring"]) + 10
        return total // 4

    def _prune_if_needed(self):
        if self._count_tokens() <= self.max_tokens:
            return

        # Move oldest to summary
        to_summarize = []
        while self._count_tokens() > self.max_tokens * 0.7 and self.recent_functions:
            to_summarize.append(self.recent_functions.pop(0))

        if to_summarize:
            self._update_summary(to_summarize)

    def _update_summary(self, functions: list[dict]):
        func_text = "\n".join(f"- {f['name']}: {f['docstring'][:100]}..." for f in functions)
        prompt = f"""Summarize these data cleaning functions in 2-3 sentences.
Focus on what types of data issues they handle.

Previous summary: {self.summary or '(none)'}

New functions:
{func_text}

Concise summary:"""

        self.summary = self.llm_backend.generate(prompt).strip()

    def get_context(self) -> str:
        parts = []
        if self.summary:
            parts.append(f"**Previously generated functions (summarized):**\n{self.summary}")
        if self.recent_functions:
            recent = "\n\n".join(
                f"## {f['name']}\n{f['docstring']}"
                for f in self.recent_functions
            )
            parts.append(f"**Recent functions (full docstrings):**\n{recent}")
        return "\n\n".join(parts) or "(No functions generated yet)"


# Alternative: Vector-based retrieval for large registries
@dataclass
class VectorDocstringRegistry:
    """
    For 50+ functions: embed docstrings, retrieve top-K relevant per chunk.
    Requires: chromadb or faiss
    """
    embedder: any  # User-provided embedding function
    store: any     # Vector store
    top_k: int = 10

    def add(self, name: str, docstring: str):
        embedding = self.embedder(docstring)
        self.store.add(name, docstring, embedding)

    def get_context(self, chunk_text: str) -> str:
        """Retrieve most relevant docstrings for this chunk"""
        chunk_embedding = self.embedder(chunk_text)
        results = self.store.query(chunk_embedding, k=self.top_k)
        return "\n\n".join(f"## {r.name}\n{r.docstring}" for r in results)
```

---

## Validation & Guardrails (validation.py)

Inspired by CrewAI + Pydantic-AI:

```python
import ast
from dataclasses import dataclass
from typing import Callable

@dataclass
class ValidationResult:
    success: bool
    error: str | None = None
    retry_prompt: str | None = None

class CodeValidator:
    """AST-based validation of generated Python code"""

    DANGEROUS_IMPORTS = {"os", "subprocess", "sys", "shutil", "pathlib"}
    DANGEROUS_CALLS = {"eval", "exec", "compile", "__import__"}

    def validate(self, code: str) -> ValidationResult:
        # Syntax check
        try:
            tree = ast.parse(code)
        except SyntaxError as e:
            return ValidationResult(
                success=False,
                error=f"Syntax error: {e}",
                retry_prompt=f"Your code has a syntax error on line {e.lineno}: {e.msg}\nPlease fix and regenerate."
            )

        # Check for dangerous patterns
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    if alias.name.split('.')[0] in self.DANGEROUS_IMPORTS:
                        return ValidationResult(
                            success=False,
                            error=f"Dangerous import: {alias.name}",
                            retry_prompt=f"Do not import {alias.name}. Use only safe data processing imports."
                        )

            if isinstance(node, ast.Call):
                if isinstance(node.func, ast.Name) and node.func.id in self.DANGEROUS_CALLS:
                    return ValidationResult(
                        success=False,
                        error=f"Dangerous function: {node.func.id}",
                        retry_prompt=f"Do not use {node.func.id}(). It's a security risk."
                    )

        # Check has docstring
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef):
                if not ast.get_docstring(node):
                    return ValidationResult(
                        success=False,
                        error="Function missing docstring",
                        retry_prompt="Your function must have a docstring explaining what it does."
                    )

        return ValidationResult(success=True)


@dataclass
class ChunkGuardrail:
    """Validates chunk processing results"""
    max_iterations: int = 5
    code_validator: CodeValidator = None

    def __post_init__(self):
        self.code_validator = self.code_validator or CodeValidator()

    def check(self, result: dict, iteration: int) -> ValidationResult:
        # Check if done
        if result.get("status") == "clean":
            return ValidationResult(success=True)

        # Check iteration limit
        if iteration >= self.max_iterations:
            return ValidationResult(
                success=False,
                error=f"Max iterations ({self.max_iterations}) reached"
            )

        # Validate generated code
        if result.get("code"):
            code_result = self.code_validator.validate(result["code"])
            if not code_result.success:
                return code_result

        return ValidationResult(success=True)


class OutputFixingParser:
    """
    LLM-powered error recovery for malformed outputs.
    Inspired by LangChain's OutputFixingParser.
    """

    def __init__(self, llm_backend, max_retries: int = 2):
        self.llm_backend = llm_backend
        self.max_retries = max_retries

    def parse_with_fix(self, text: str, parse_fn: Callable, original_prompt: str) -> dict:
        last_error = None

        for attempt in range(self.max_retries + 1):
            try:
                return parse_fn(text)
            except Exception as e:
                last_error = e
                if attempt < self.max_retries:
                    fix_prompt = f"""Your previous response could not be parsed.

Original request:
{original_prompt[:500]}...

Your response:
{text[:1000]}...

Error: {e}

Please provide your response again, ensuring valid XML format with the code wrapped in ```python blocks."""

                    text = self.llm_backend.generate(fix_prompt)

        raise last_error
```

---

## Callback System (callbacks.py)

Inspired by smolagents + LangChain:

```python
from abc import ABC
from dataclasses import dataclass
from datetime import datetime
from typing import Any

@dataclass
class Event:
    timestamp: datetime
    event_type: str
    data: dict[str, Any]

class CleanerCallback(ABC):
    """Base class for pipeline event handlers"""

    def on_run_start(self, file_path: str, total_chunks: int): pass
    def on_chunk_start(self, chunk_index: int, chunk_preview: str): pass
    def on_iteration_start(self, chunk_index: int, iteration: int): pass
    def on_llm_call(self, prompt_preview: str): pass
    def on_llm_response(self, response_preview: str, latency_ms: float): pass
    def on_function_generated(self, name: str, docstring: str): pass
    def on_validation_error(self, error: str, retry_prompt: str | None): pass
    def on_chunk_complete(self, chunk_index: int, status: str, iterations: int): pass
    def on_run_complete(self, total_functions: int, total_errors: int): pass
    def on_error(self, error: Exception, context: dict): pass


class LoggingCallback(CleanerCallback):
    """Logs events to console and file"""

    def __init__(self, log_file: str | None = None, verbose: bool = True):
        self.log_file = log_file
        self.verbose = verbose
        self.events: list[Event] = []

    def _log(self, message: str):
        timestamp = datetime.now().strftime("%H:%M:%S")
        line = f"[{timestamp}] {message}"
        if self.verbose:
            print(line)
        if self.log_file:
            with open(self.log_file, "a") as f:
                f.write(line + "\n")

    def on_run_start(self, file_path: str, total_chunks: int):
        self._log(f"Starting pipeline: {file_path} ({total_chunks} chunks)")

    def on_chunk_start(self, chunk_index: int, chunk_preview: str):
        self._log(f"Processing chunk {chunk_index}...")

    def on_function_generated(self, name: str, docstring: str):
        self._log(f"  Generated: {name}()")

    def on_validation_error(self, error: str, retry_prompt: str | None):
        self._log(f"  Validation error: {error}")

    def on_chunk_complete(self, chunk_index: int, status: str, iterations: int):
        self._log(f"  Chunk {chunk_index} complete: {status} ({iterations} iterations)")

    def on_run_complete(self, total_functions: int, total_errors: int):
        self._log(f"Pipeline complete! {total_functions} functions, {total_errors} errors")


class MetricsCallback(CleanerCallback):
    """Collects metrics for analysis"""

    def __init__(self):
        self.metrics = {
            "llm_calls": 0,
            "total_latency_ms": 0,
            "functions_generated": 0,
            "chunks_processed": 0,
            "chunks_skipped": 0,
            "validation_errors": 0,
            "retries": 0,
        }

    def on_llm_response(self, response_preview: str, latency_ms: float):
        self.metrics["llm_calls"] += 1
        self.metrics["total_latency_ms"] += latency_ms

    def on_function_generated(self, name: str, docstring: str):
        self.metrics["functions_generated"] += 1

    def on_validation_error(self, error: str, retry_prompt: str | None):
        self.metrics["validation_errors"] += 1
        if retry_prompt:
            self.metrics["retries"] += 1

    def get_summary(self) -> dict:
        m = self.metrics
        return {
            **m,
            "avg_latency_ms": m["total_latency_ms"] / max(m["llm_calls"], 1),
        }
```

---

## Jinja2 Prompt Templates (prompts/system.yaml)

Inspired by smolagents:

```yaml
# prompts/system.yaml
system_prompt: |
  You are a data cleaning expert. Your job is to analyze data chunks and generate Python functions to fix quality issues.

  === USER'S CLEANING GOALS ===
  {{ instructions }}

  === EXISTING CLEANING FUNCTIONS ===
  {% if docstring_context %}
  {{ docstring_context }}
  {% else %}
  (No functions generated yet)
  {% endif %}

  === DATA CHUNK {{ chunk_index }}/{{ total_chunks }} ===
  {{ chunk_data }}

  === YOUR TASK ===
  1. Identify ALL data quality issues in this chunk
  2. Check if each issue is already solved by existing functions
  3. Generate code for ONLY the FIRST unsolved issue
  4. Return your analysis in this EXACT format:

  <cleaning_analysis>
    <issues_detected>
      <issue id="1" solved="true|false">Description</issue>
    </issues_detected>

    <function_to_generate>
      <name>function_name</name>
      <docstring>
      What this function does.
      What edge cases it handles.
      </docstring>
      <code>
  ```python
  def function_name(data):
      """Docstring here"""
      # Implementation
      pass
  ```
      </code>
    </function_to_generate>

    <chunk_status>clean|needs_more_work</chunk_status>
  </cleaning_analysis>

  CRITICAL RULES:
  - Generate EXACTLY ONE function per response
  - If all issues solved: set <chunk_status>clean</chunk_status> and omit <function_to_generate>
  - Include all imports at the top of the code block
  - Functions must be idempotent (safe to run multiple times)
  - Always include a docstring in your function
```

```yaml
# prompts/retry.yaml
retry_prompt: |
  Your previous response had an error:

  {{ error_message }}

  {% if retry_hint %}
  Hint: {{ retry_hint }}
  {% endif %}

  Please regenerate your response in the correct format.
```

---

## Checkpoint Persistence (checkpoints.py)

Inspired by LangGraph:

```python
import json
from abc import ABC, abstractmethod
from dataclasses import asdict
from datetime import datetime
from pathlib import Path
from typing import Any

class CheckpointSaver(ABC):
    """Abstract interface for state persistence"""

    @abstractmethod
    def save(self, state: dict, step: int) -> None: ...

    @abstractmethod
    def load(self, step: int | None = None) -> dict | None: ...

    @abstractmethod
    def list_steps(self) -> list[int]: ...

    @abstractmethod
    def delete(self, step: int) -> None: ...


class FileCheckpointSaver(CheckpointSaver):
    """Save checkpoints to JSON files"""

    def __init__(self, directory: str = ".checkpoints"):
        self.directory = Path(directory)
        self.directory.mkdir(exist_ok=True)

    def _path(self, step: int) -> Path:
        return self.directory / f"checkpoint_{step:06d}.json"

    def save(self, state: dict, step: int) -> None:
        data = {
            "step": step,
            "timestamp": datetime.now().isoformat(),
            "state": self._serialize(state),
        }
        with open(self._path(step), "w") as f:
            json.dump(data, f, indent=2, default=str)

    def load(self, step: int | None = None) -> dict | None:
        if step is None:
            steps = self.list_steps()
            if not steps:
                return None
            step = max(steps)

        path = self._path(step)
        if not path.exists():
            return None

        with open(path) as f:
            data = json.load(f)
        return data["state"]

    def list_steps(self) -> list[int]:
        steps = []
        for path in self.directory.glob("checkpoint_*.json"):
            try:
                step = int(path.stem.split("_")[1])
                steps.append(step)
            except (IndexError, ValueError):
                continue
        return sorted(steps)

    def delete(self, step: int) -> None:
        path = self._path(step)
        if path.exists():
            path.unlink()

    def _serialize(self, obj: Any) -> Any:
        if hasattr(obj, "__dict__"):
            return {k: self._serialize(v) for k, v in obj.__dict__.items()}
        if isinstance(obj, list):
            return [self._serialize(v) for v in obj]
        if isinstance(obj, dict):
            return {k: self._serialize(v) for k, v in obj.items()}
        if isinstance(obj, datetime):
            return obj.isoformat()
        return obj


class InMemoryCheckpointSaver(CheckpointSaver):
    """For testing - stores checkpoints in memory"""

    def __init__(self):
        self.checkpoints: dict[int, dict] = {}

    def save(self, state: dict, step: int) -> None:
        self.checkpoints[step] = state.copy()

    def load(self, step: int | None = None) -> dict | None:
        if step is None:
            if not self.checkpoints:
                return None
            step = max(self.checkpoints.keys())
        return self.checkpoints.get(step)

    def list_steps(self) -> list[int]:
        return sorted(self.checkpoints.keys())

    def delete(self, step: int) -> None:
        self.checkpoints.pop(step, None)
```

---

## Main Orchestrator (cleaner.py)

```python
import time
from dataclasses import dataclass, field
from datetime import datetime
from typing import Protocol
from jinja2 import Environment, PackageLoader

from .state import PipelineState, GeneratedFunction, ChunkResult
from .memory import DocstringRegistry
from .validation import ChunkGuardrail, OutputFixingParser, CodeValidator
from .callbacks import CleanerCallback, LoggingCallback
from .checkpoints import CheckpointSaver
from .errors import *
from .parsing import parse_response

from tenacity import retry, stop_after_attempt, wait_exponential_jitter

class LLMBackend(Protocol):
    def generate(self, prompt: str) -> str: ...

@dataclass
class DataCleaner:
    llm_backend: LLMBackend
    file_path: str
    instructions: str
    chunk_size: int = 50
    max_iterations: int = 5
    context_budget: int = 4000
    callbacks: list[CleanerCallback] = field(default_factory=list)
    checkpointer: CheckpointSaver | None = None
    checkpoint_interval: int = 10  # Save every N chunks

    def __post_init__(self):
        self.env = Environment(loader=PackageLoader("recursive_cleaner", "prompts"))
        self.system_template = self.env.get_template("system.yaml")
        self.retry_template = self.env.get_template("retry.yaml")

        self.registry = DocstringRegistry(self.llm_backend, self.context_budget)
        self.guardrail = ChunkGuardrail(self.max_iterations)
        self.output_fixer = OutputFixingParser(self.llm_backend)

        self.state: PipelineState = {
            "functions": [],
            "docstring_registry": {},
            "chunk_results": [],
            "current_chunk_index": 0,
            "current_iteration": 0,
            "total_chunks": 0,
            "file_path": self.file_path,
            "started_at": datetime.now().isoformat(),
            "errors": [],
        }

        # Add default logging callback if none provided
        if not self.callbacks:
            self.callbacks.append(LoggingCallback())

    def run(self, resume_from: int | None = None):
        """Run the cleaning pipeline"""
        chunks = self._load_chunks()
        self.state["total_chunks"] = len(chunks)

        # Resume from checkpoint if requested
        start_index = 0
        if resume_from is not None and self.checkpointer:
            saved_state = self.checkpointer.load(resume_from)
            if saved_state:
                self.state = saved_state
                start_index = saved_state["current_chunk_index"]

        self._emit("on_run_start", self.file_path, len(chunks))

        for i, chunk in enumerate(chunks[start_index:], start=start_index):
            self.state["current_chunk_index"] = i
            self._emit("on_chunk_start", i, chunk[:100])

            try:
                result = self._process_chunk(chunk, i)
                self.state["chunk_results"].append(result)
            except ChunkSkippedError as e:
                self.state["errors"].append({"chunk": i, "error": str(e)})

            # Checkpoint periodically
            if self.checkpointer and i % self.checkpoint_interval == 0:
                self.checkpointer.save(self.state, i)

        self._write_output()
        self._emit("on_run_complete", len(self.state["functions"]), len(self.state["errors"]))

    def _process_chunk(self, chunk: str, chunk_index: int) -> ChunkResult:
        functions_generated = []
        issues_found = 0

        for iteration in range(self.max_iterations):
            self.state["current_iteration"] = iteration
            self._emit("on_iteration_start", chunk_index, iteration)

            prompt = self._build_prompt(chunk, chunk_index)

            # Call LLM with retry
            start_time = time.time()
            try:
                response = self._call_llm_with_retry(prompt)
            except Exception as e:
                self._emit("on_error", e, {"chunk": chunk_index, "iteration": iteration})
                raise ChunkSkippedError(f"LLM call failed: {e}")

            latency_ms = (time.time() - start_time) * 1000
            self._emit("on_llm_response", response[:100], latency_ms)

            # Parse with auto-fix
            try:
                result = self.output_fixer.parse_with_fix(response, parse_response, prompt)
            except Exception as e:
                self._emit("on_validation_error", str(e), None)
                continue

            issues_found = len(result.get("issues", []))

            # Validate
            validation = self.guardrail.check(result, iteration)
            if not validation.success:
                if validation.retry_prompt:
                    self._emit("on_validation_error", validation.error, validation.retry_prompt)
                    # Retry with feedback
                    continue
                else:
                    # Non-recoverable
                    break

            # Check if clean
            if result.get("status") == "clean":
                self._emit("on_chunk_complete", chunk_index, "clean", iteration + 1)
                return ChunkResult(
                    chunk_index=chunk_index,
                    iterations=iteration + 1,
                    status="clean",
                    functions_generated=functions_generated,
                    issues_found=issues_found,
                    issues_solved=issues_found,
                )

            # Store generated function
            if result.get("code"):
                func = GeneratedFunction(
                    name=result["name"],
                    docstring=result["docstring"],
                    code=result["code"],
                    issues_solved=[],  # Could parse from issues
                    chunk_index=chunk_index,
                )
                self.state["functions"].append(func)
                self.registry.add(func.name, func.docstring)
                functions_generated.append(func.name)
                self._emit("on_function_generated", func.name, func.docstring)

        # Max iterations reached
        self._emit("on_chunk_complete", chunk_index, "max_iterations", self.max_iterations)
        return ChunkResult(
            chunk_index=chunk_index,
            iterations=self.max_iterations,
            status="max_iterations",
            functions_generated=functions_generated,
            issues_found=issues_found,
            issues_solved=len(functions_generated),
        )

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential_jitter(initial=1, max=30, jitter=5),
    )
    def _call_llm_with_retry(self, prompt: str) -> str:
        self._emit("on_llm_call", prompt[:100])
        return self.llm_backend.generate(prompt)

    def _build_prompt(self, chunk: str, chunk_index: int) -> str:
        return self.system_template.render(
            instructions=self.instructions,
            docstring_context=self.registry.get_context(),
            chunk_index=chunk_index + 1,
            total_chunks=self.state["total_chunks"],
            chunk_data=chunk,
        )

    def _emit(self, event: str, *args, **kwargs):
        for callback in self.callbacks:
            method = getattr(callback, event, None)
            if method:
                try:
                    method(*args, **kwargs)
                except Exception:
                    pass  # Don't let callback errors break pipeline

    def _load_chunks(self) -> list[str]:
        # Implementation for text/csv/json chunking
        ...

    def _write_output(self):
        # Generate cleaning_functions.py
        ...
```

---

## Dependencies

```toml
[project]
dependencies = [
    "tenacity>=8.0",      # Retry logic
    "jinja2>=3.0",        # Prompt templates
]

[project.optional-dependencies]
vector = [
    "chromadb>=0.4",      # Vector store for large registries
]
```

---

## Comparison: Lean vs Advanced

| Feature | Lean (CLAUDE.md) | Advanced (this file) |
|---------|------------------|----------------------|
| Lines of code | ~300 | ~800 |
| Dependencies | tenacity | tenacity, jinja2, (chromadb) |
| Error handling | 3 exception classes | 6 exception classes + hierarchy |
| Context management | FIFO eviction | Summary buffer + optional vector |
| Output recovery | Retry with error msg | LLM-powered output fixer |
| Validation | ast.parse() | AST + dangerous code detection |
| Extensibility | None | Callback system |
| Persistence | None | Checkpoint interface |
| Templates | f-strings | Jinja2 YAML files |
| State | Plain dicts | TypedDict with reducers |

---

## When to Use Each

**Use Lean (CLAUDE.md) when:**
- Getting started / prototyping
- Simple, predictable data
- You want minimal dependencies
- You'll monitor the run yourself

**Use Advanced (this file) when:**
- Running on large datasets (1000+ chunks)
- Need to resume interrupted runs
- Want detailed metrics/logging
- Integrating into larger systems
- Need security validation of generated code

---

## References

See `docs/` folder for detailed framework analyses:
- `smolagents-analysis.md` - Memory steps, error hierarchy, AST validation
- `langchain-analysis.md` - Tenacity retry, summary buffer, output fixing
- `langgraph-analysis.md` - TypedDict state, reducers, checkpoints
- `other-frameworks-analysis.md` - Guardrails, validation patterns

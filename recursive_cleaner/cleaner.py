"""Main DataCleaner class - the core pipeline."""

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Literal

from tenacity import retry, stop_after_attempt, wait_exponential

from .context import build_context
from .errors import OutputValidationError, ParseError
from .parsers import chunk_file
from .prompt import build_prompt
from .response import parse_response
from .schema import format_schema_for_prompt, infer_schema
from .types import LLMBackend
from .validation import extract_sample_data, validate_function

STATE_VERSION = "0.3.0"


@retry(stop=stop_after_attempt(3), wait=wait_exponential(min=1, max=10))
def call_llm(backend: LLMBackend, prompt: str) -> str:
    """Call LLM with retry logic."""
    return backend.generate(prompt)


class DataCleaner:
    """
    LLM-powered incremental data cleaning pipeline.

    Processes data in chunks, identifies issues, generates Python
    cleaning functions one at a time, maintaining awareness of
    existing solutions through docstring feedback.
    """

    def __init__(
        self,
        llm_backend: LLMBackend,
        file_path: str,
        chunk_size: int = 50,
        instructions: str = "",
        max_iterations: int = 5,
        context_budget: int = 8000,
        on_progress: Callable[[dict], None] | None = None,
        validate_runtime: bool = True,
        schema_sample_size: int = 10,
        state_file: str | None = None,
        mode: Literal["auto", "structured", "text"] = "auto",
        chunk_overlap: int = 200,
    ):
        self.backend = llm_backend
        self.file_path = file_path
        self.chunk_size = chunk_size
        self.instructions = instructions
        self.max_iterations = max_iterations
        self.context_budget = context_budget
        self.on_progress = on_progress
        self.validate_runtime = validate_runtime
        self.schema_sample_size = schema_sample_size
        self.state_file = state_file
        self.mode = mode
        self.chunk_overlap = chunk_overlap
        self.functions: list[dict] = []  # List of {name, docstring, code}
        self._total_chunks: int = 0  # Set during run()
        self._schema_str: str = ""  # Formatted schema for prompts
        self._last_completed_chunk: int = -1  # -1 means no chunks completed yet
        self._effective_mode: Literal["structured", "text"] = "structured"  # Resolved at run()

    def _emit(self, event_type: str, chunk_index: int = 0, **kwargs) -> None:
        """Emit a progress event to the callback, if set."""
        if self.on_progress is None:
            return
        event = {
            "type": event_type,
            "chunk_index": chunk_index,
            "total_chunks": self._total_chunks,
            **kwargs,
        }
        try:
            self.on_progress(event)
        except Exception as e:
            print(f"  Warning: callback error: {e}")

    def _save_state(self) -> None:
        """Save current state to JSON file with atomic write."""
        if self.state_file is None:
            return
        state = {
            "version": STATE_VERSION,
            "file_path": self.file_path,
            "instructions": self.instructions,
            "chunk_size": self.chunk_size,
            "last_completed_chunk": self._last_completed_chunk,
            "total_chunks": self._total_chunks,
            "functions": self.functions,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        tmp_path = self.state_file + ".tmp"
        with open(tmp_path, "w") as f:
            json.dump(state, f, indent=2)
        os.rename(tmp_path, self.state_file)

    def _load_state(self) -> bool:
        """Load state from JSON file if it exists. Returns True if loaded."""
        if self.state_file is None or not os.path.exists(self.state_file):
            return False
        try:
            with open(self.state_file) as f:
                state = json.load(f)
        except json.JSONDecodeError as e:
            raise ValueError(f"Invalid state file JSON: {e}")
        # Validate file_path matches
        if state.get("file_path") != self.file_path:
            raise ValueError(
                f"State file_path mismatch: state has '{state.get('file_path')}', "
                f"but current file_path is '{self.file_path}'"
            )
        # Load state
        self.functions = state.get("functions", [])
        self._last_completed_chunk = state.get("last_completed_chunk", -1)
        self._total_chunks = state.get("total_chunks", 0)
        print(f"Resumed from state: {self._last_completed_chunk + 1}/{self._total_chunks} chunks completed")
        return True

    @classmethod
    def resume(cls, state_file: str, llm_backend: LLMBackend) -> "DataCleaner":
        """
        Resume processing from a saved state file.

        Args:
            state_file: Path to state JSON file
            llm_backend: LLM backend to use (not saved in state)

        Returns:
            DataCleaner instance ready to continue processing

        Raises:
            FileNotFoundError: If state file doesn't exist
            ValueError: If state file is invalid
        """
        if not os.path.exists(state_file):
            raise FileNotFoundError(f"State file not found: {state_file}")
        try:
            with open(state_file) as f:
                state = json.load(f)
        except json.JSONDecodeError as e:
            raise ValueError(f"Invalid state file JSON: {e}")
        # Create instance with saved parameters
        instance = cls(
            llm_backend=llm_backend,
            file_path=state["file_path"],
            chunk_size=state.get("chunk_size", 50),
            instructions=state.get("instructions", ""),
            state_file=state_file,
        )
        # Restore state
        instance.functions = state.get("functions", [])
        instance._last_completed_chunk = state.get("last_completed_chunk", -1)
        instance._total_chunks = state.get("total_chunks", 0)
        return instance

    def _detect_mode(self) -> Literal["structured", "text"]:
        """Detect mode from file extension."""
        suffix = Path(self.file_path).suffix.lower()
        structured_extensions = {".jsonl", ".csv", ".json"}
        if suffix in structured_extensions:
            return "structured"
        return "text"

    def run(self) -> None:
        """Run the cleaning pipeline."""
        # Resolve effective mode
        if self.mode == "auto":
            self._effective_mode = self._detect_mode()
        else:
            self._effective_mode = self.mode

        chunks = chunk_file(
            self.file_path,
            self.chunk_size,
            mode=self._effective_mode,
            chunk_overlap=self.chunk_overlap,
        )

        if not chunks:
            print("No data to process.")
            return

        # Try to load existing state
        resumed = self._load_state()

        # Infer schema only for structured mode
        if self._effective_mode == "structured":
            schema = infer_schema(self.file_path, self.schema_sample_size)
            self._schema_str = format_schema_for_prompt(schema)
        else:
            self._schema_str = ""  # No schema for text mode

        self._total_chunks = len(chunks)

        for i, chunk in enumerate(chunks):
            # Skip already completed chunks
            if i <= self._last_completed_chunk:
                if resumed:
                    print(f"Skipping chunk {i + 1}/{len(chunks)} (already completed)")
                continue
            print(f"Processing chunk {i + 1}/{len(chunks)}...")
            self._process_chunk(chunk, i)
            # Mark chunk as completed and save state
            self._last_completed_chunk = i
            self._save_state()

        self._write_output()
        self._emit("complete", chunk_index=self._total_chunks - 1)
        print(f"Done! Generated {len(self.functions)} functions.")

    def _process_chunk(self, chunk: str, chunk_idx: int) -> None:
        """Process a single chunk, iterating until clean or max iterations."""
        self._emit("chunk_start", chunk_index=chunk_idx)
        error_feedback = ""

        for iteration in range(self.max_iterations):
            self._emit("iteration", chunk_index=chunk_idx, iteration=iteration)
            context = build_context(self.functions, self.context_budget)
            prompt = build_prompt(
                self.instructions,
                context,
                chunk,
                self._schema_str,
                mode=self._effective_mode,
            )

            if error_feedback:
                prompt += f"\n\nYour previous response had an error: {error_feedback}\nPlease fix and try again."

            try:
                response = call_llm(self.backend, prompt)
                result = parse_response(response)
                error_feedback = ""  # Clear on success
            except ParseError as e:
                error_feedback = str(e)
                continue

            if result["status"] == "clean":
                self._emit("chunk_done", chunk_index=chunk_idx)
                return

            if result["code"]:
                # Runtime validation if enabled
                if self.validate_runtime:
                    sample_data = extract_sample_data(chunk, mode=self._effective_mode)
                    valid, error_msg = validate_function(
                        result["code"],
                        sample_data,
                        result["name"],
                        mode=self._effective_mode,
                    )
                    if not valid:
                        error_feedback = f"Runtime validation failed: {error_msg}"
                        self._emit(
                            "validation_failed",
                            chunk_index=chunk_idx,
                            function_name=result["name"],
                            error=error_msg,
                        )
                        print(f"  Validation failed: {error_msg}")
                        continue

                self.functions.append({
                    "name": result["name"],
                    "docstring": result["docstring"],
                    "code": result["code"],
                })
                self._emit(
                    "function_generated",
                    chunk_index=chunk_idx,
                    function_name=result["name"],
                )
                print(f"  Generated: {result['name']}")
            else:
                # LLM said needs_more_work but didn't provide code
                print(f"  Warning: iteration {iteration + 1} produced no function")

        print(f"  Warning: chunk {chunk_idx} hit max iterations ({self.max_iterations})")
        self._emit("chunk_done", chunk_index=chunk_idx)

    def _write_output(self) -> None:
        """Write generated functions to cleaning_functions.py."""
        from .output import write_cleaning_file

        try:
            write_cleaning_file(self.functions)
        except OutputValidationError as e:
            print(f"  Error: {e}")
            print("  Attempting to write valid functions only...")
            # Try writing functions one by one, skipping invalid ones
            valid_functions = []
            for f in self.functions:
                try:
                    import ast
                    ast.parse(f["code"])
                    valid_functions.append(f)
                except SyntaxError:
                    print(f"  Skipping invalid function: {f['name']}")
            if valid_functions:
                write_cleaning_file(valid_functions)
            else:
                print("  No valid functions to write.")

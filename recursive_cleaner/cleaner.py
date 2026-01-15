"""Main DataCleaner class - the core pipeline."""

import json
import os
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Literal

from tenacity import retry, stop_after_attempt, wait_exponential

from .context import build_context
from .errors import OutputValidationError, ParseError
from .metrics import QualityMetrics, compare_quality, load_structured_data, measure_quality
from .parsers import chunk_file
from .prompt import build_prompt
from .response import parse_response
from .schema import format_schema_for_prompt, infer_schema
from .types import LLMBackend
from .validation import check_code_safety, extract_sample_data, split_holdout, validate_function

STATE_VERSION = "0.5.0"


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
        holdout_ratio: float = 0.2,
        track_metrics: bool = False,
        sampling_strategy: Literal["sequential", "random", "stratified"] = "sequential",
        stratify_field: str | None = None,
        optimize: bool = False,
        optimize_threshold: int = 10,
        early_termination: bool = False,
        saturation_check_interval: int = 20,
        report_path: str | None = "cleaning_report.md",
        dry_run: bool = False,
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
        self.holdout_ratio = holdout_ratio
        self.track_metrics = track_metrics
        self.sampling_strategy = sampling_strategy
        self.stratify_field = stratify_field
        self.optimize = optimize
        self.optimize_threshold = optimize_threshold
        self.early_termination = early_termination
        self.saturation_check_interval = saturation_check_interval
        self.report_path = report_path
        self.dry_run = dry_run
        self.functions: list[dict] = []  # List of {name, docstring, code}
        # Track recent function generation for saturation check
        self._recent_new_function_count = 0
        self._last_check_function_count = 0
        self._total_chunks: int = 0  # Set during run()
        self._schema_str: str = ""  # Formatted schema for prompts
        self._last_completed_chunk: int = -1  # -1 means no chunks completed yet
        self._effective_mode: Literal["structured", "text"] = "structured"  # Resolved at run()
        # Quality metrics (populated when track_metrics=True)
        self.metrics_before: QualityMetrics | None = None
        self.metrics_after: QualityMetrics | None = None
        # Latency tracking for LLM calls
        self._latency_stats: dict = {
            "call_count": 0,
            "total_ms": 0.0,
            "min_ms": float("inf"),
            "max_ms": 0.0,
        }

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

    def _call_llm_timed(self, prompt: str, chunk_index: int = 0) -> str:
        """Call LLM with timing and emit latency event."""
        start = time.perf_counter()
        response = call_llm(self.backend, prompt)
        elapsed_ms = (time.perf_counter() - start) * 1000

        # Update stats
        self._latency_stats["call_count"] += 1
        self._latency_stats["total_ms"] += elapsed_ms
        self._latency_stats["min_ms"] = min(self._latency_stats["min_ms"], elapsed_ms)
        self._latency_stats["max_ms"] = max(self._latency_stats["max_ms"], elapsed_ms)

        # Emit event
        self._emit("llm_call", chunk_index=chunk_index, latency_ms=round(elapsed_ms, 2))

        return response

    def _get_latency_summary(self) -> dict:
        """Get summary of latency stats with avg calculation."""
        stats = self._latency_stats.copy()
        if stats["call_count"] > 0:
            stats["avg_ms"] = round(stats["total_ms"] / stats["call_count"], 2)
            stats["min_ms"] = round(stats["min_ms"], 2)
            stats["max_ms"] = round(stats["max_ms"], 2)
            stats["total_ms"] = round(stats["total_ms"], 2)
        else:
            stats["avg_ms"] = 0.0
            stats["min_ms"] = 0.0
        return stats

    def _optimize_functions(self) -> None:
        """
        Run two-pass optimization on generated functions.

        1. Group functions by salience (IDF)
        2. Consolidate each group with agency
        3. Replace self.functions with optimized result
        """
        from .optimizer import consolidate_with_agency, group_by_salience

        self._emit(
            "optimize_start",
            function_count=len(self.functions),
        )

        # Group by IDF
        groups = group_by_salience(self.functions)

        optimized = []
        for group_name, group_funcs in groups.items():
            self._emit(
                "optimize_group",
                group=group_name,
                count=len(group_funcs),
            )

            # Consolidate with agency
            consolidated = consolidate_with_agency(group_funcs, self.backend)
            optimized.extend(consolidated)

        self._emit(
            "optimize_complete",
            original=len(self.functions),
            final=len(optimized),
        )

        self.functions = optimized

    def _check_saturation(self, chunks_processed: int) -> bool:
        """
        Ask LLM if pattern discovery has saturated.

        Returns True if should stop early, False to continue.
        """
        from .prompt import SATURATION_CHECK_TEMPLATE
        from .response import parse_saturation_response

        # Build function summaries (name + first line of docstring)
        summaries = []
        for f in self.functions:
            first_line = f["docstring"].split("\n")[0] if f["docstring"] else ""
            summaries.append(f"- {f['name']}: {first_line}")

        prompt = SATURATION_CHECK_TEMPLATE.format(
            count=len(self.functions),
            function_summaries="\n".join(summaries) or "(none)",
            total_chunks=chunks_processed,
            recent_window=self.saturation_check_interval,
            recent_new_functions=self._recent_new_function_count,
        )

        try:
            response = self._call_llm_timed(prompt, chunk_index=chunks_processed - 1)
            assessment = parse_saturation_response(response)
        except Exception as e:
            print(f"  Warning: saturation check failed: {e}")
            return False  # Continue on error

        self._emit(
            "saturation_check",
            chunk_index=chunks_processed - 1,
            saturated=assessment.saturated,
            confidence=assessment.confidence,
            recommendation=assessment.recommendation,
        )

        # Reset counter for next interval
        self._recent_new_function_count = 0

        # Only stop if saturated with high or medium confidence
        return assessment.saturated and assessment.confidence != "low"

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
            "optimize": self.optimize,
            "optimize_threshold": self.optimize_threshold,
            "early_termination": self.early_termination,
            "saturation_check_interval": self.saturation_check_interval,
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
            optimize=state.get("optimize", False),
            optimize_threshold=state.get("optimize_threshold", 10),
            early_termination=state.get("early_termination", False),
            saturation_check_interval=state.get("saturation_check_interval", 20),
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
            sampling_strategy=self.sampling_strategy,
            stratify_field=self.stratify_field,
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
            # Measure initial quality metrics if tracking enabled
            if self.track_metrics:
                data = load_structured_data(self.file_path)
                self.metrics_before = measure_quality(data)
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

            # Check for early termination (saturation detection)
            if (
                self.early_termination
                and i > 0
                and (i + 1) % self.saturation_check_interval == 0
            ):
                if self._check_saturation(i + 1):
                    self._emit("early_termination", chunk_index=i)
                    print(f"Early termination: pattern discovery saturated at chunk {i + 1}")
                    break

        # Skip optimization and output in dry_run mode
        if self.dry_run:
            self._emit(
                "dry_run_complete",
                chunk_index=self._total_chunks - 1,
                latency_stats=self._get_latency_summary(),
            )
            print("Dry run complete. No functions generated or saved.")
            return

        # Two-pass optimization (if enabled and enough functions)
        if self.optimize and len(self.functions) >= self.optimize_threshold:
            self._optimize_functions()

        self._write_output()
        self._write_report()
        self._emit(
            "complete",
            chunk_index=self._total_chunks - 1,
            latency_stats=self._get_latency_summary(),
        )
        print(f"Done! Generated {len(self.functions)} functions.")

    def _process_chunk(self, chunk: str, chunk_idx: int) -> None:
        """Process a single chunk, iterating until clean or max iterations."""
        self._emit("chunk_start", chunk_index=chunk_idx)
        error_feedback = ""

        # Dry run mode: just detect issues, don't generate functions
        if self.dry_run:
            self._process_chunk_dry_run(chunk, chunk_idx)
            return

        # Split chunk for holdout validation if enabled
        use_holdout = self.validate_runtime and self.holdout_ratio > 0
        if use_holdout:
            gen_chunk, holdout_chunk = split_holdout(
                chunk, self.holdout_ratio, mode=self._effective_mode
            )
        else:
            gen_chunk, holdout_chunk = chunk, ""

        for iteration in range(self.max_iterations):
            self._emit("iteration", chunk_index=chunk_idx, iteration=iteration)
            context = build_context(self.functions, self.context_budget)
            prompt = build_prompt(
                self.instructions,
                context,
                gen_chunk,
                self._schema_str,
                mode=self._effective_mode,
            )

            if error_feedback:
                prompt += f"\n\nYour previous response had an error: {error_feedback}\nPlease fix and try again."

            try:
                response = self._call_llm_timed(prompt, chunk_index=chunk_idx)
                result = parse_response(response)
                error_feedback = ""  # Clear on success
            except ParseError as e:
                error_feedback = str(e)
                continue

            if result["status"] == "clean":
                self._emit("chunk_done", chunk_index=chunk_idx)
                return

            if result["code"]:
                # Safety check: reject dangerous patterns before execution
                safe, safety_error = check_code_safety(result["code"])
                if not safe:
                    error_feedback = f"Code safety check failed: {safety_error}. Data cleaning functions should not access filesystem, network, or use eval/exec."
                    self._emit(
                        "safety_failed",
                        chunk_index=chunk_idx,
                        function_name=result["name"],
                        error=safety_error,
                    )
                    print(f"  Safety check failed: {safety_error}")
                    continue

                # Runtime validation if enabled
                if self.validate_runtime:
                    # Use holdout data if available, else sample from generation chunk
                    if use_holdout and holdout_chunk:
                        sample_data = extract_sample_data(
                            holdout_chunk, mode=self._effective_mode
                        )
                    else:
                        sample_data = extract_sample_data(
                            gen_chunk, mode=self._effective_mode
                        )
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
                # Track for saturation check
                self._recent_new_function_count += 1
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

    def _process_chunk_dry_run(self, chunk: str, chunk_idx: int) -> None:
        """Process chunk in dry run mode - detect issues only."""
        context = build_context(self.functions, self.context_budget)
        prompt = build_prompt(
            self.instructions,
            context,
            chunk,
            self._schema_str,
            mode=self._effective_mode,
        )

        try:
            response = self._call_llm_timed(prompt, chunk_index=chunk_idx)
            result = parse_response(response)
        except ParseError as e:
            print(f"  Warning: parse error in dry run: {e}")
            self._emit("chunk_done", chunk_index=chunk_idx)
            return

        # Extract issues from result
        issues = result.get("issues", [])
        self._emit(
            "issues_detected",
            chunk_index=chunk_idx,
            issues=issues,
        )

        if issues:
            unsolved = [i for i in issues if not i.get("solved", False)]
            print(f"  Found {len(issues)} issues ({len(unsolved)} unsolved)")
        else:
            print("  No issues detected")

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

    def _write_report(self) -> None:
        """Write cleaning report if report_path is set."""
        if self.report_path is None:
            return

        from .report import write_report

        # Prepare quality metrics if available
        quality_before = None
        quality_after = None
        if self.metrics_before:
            quality_before = {
                "null_count": self.metrics_before.null_count,
                "empty_string_count": self.metrics_before.empty_string_count,
            }
        if self.metrics_after:
            quality_after = {
                "null_count": self.metrics_after.null_count,
                "empty_string_count": self.metrics_after.empty_string_count,
            }

        write_report(
            report_path=self.report_path,
            file_path=self.file_path,
            total_chunks=self._total_chunks,
            functions=self.functions,
            latency_stats=self._get_latency_summary(),
            quality_before=quality_before,
            quality_after=quality_after,
        )

    def get_improvement_report(self) -> dict | None:
        """
        Get a comparison report of before/after quality metrics.

        Returns:
            Dictionary with improvement statistics, or None if metrics
            weren't tracked or after metrics aren't available yet.
        """
        if self.metrics_before is None:
            return None
        if self.metrics_after is None:
            # Return partial report with just before metrics
            return {
                "status": "incomplete",
                "metrics_before": {
                    "null_count": self.metrics_before.null_count,
                    "empty_string_count": self.metrics_before.empty_string_count,
                    "unique_values": self.metrics_before.unique_values,
                    "total_records": self.metrics_before.total_records,
                },
                "metrics_after": None,
            }
        return compare_quality(self.metrics_before, self.metrics_after)

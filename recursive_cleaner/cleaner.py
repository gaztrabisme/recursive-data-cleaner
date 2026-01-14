"""Main DataCleaner class - the core pipeline."""

from tenacity import retry, stop_after_attempt, wait_exponential

from .context import build_context
from .errors import OutputValidationError, ParseError
from .parsers import chunk_file
from .prompt import build_prompt
from .response import parse_response
from .types import LLMBackend


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
    ):
        self.backend = llm_backend
        self.file_path = file_path
        self.chunk_size = chunk_size
        self.instructions = instructions
        self.max_iterations = max_iterations
        self.context_budget = context_budget
        self.functions: list[dict] = []  # List of {name, docstring, code}

    def run(self) -> None:
        """Run the cleaning pipeline."""
        chunks = chunk_file(self.file_path, self.chunk_size)

        if not chunks:
            print("No data to process.")
            return

        for i, chunk in enumerate(chunks):
            print(f"Processing chunk {i + 1}/{len(chunks)}...")
            self._process_chunk(chunk, i)

        self._write_output()
        print(f"Done! Generated {len(self.functions)} functions.")

    def _process_chunk(self, chunk: str, chunk_idx: int) -> None:
        """Process a single chunk, iterating until clean or max iterations."""
        error_feedback = ""

        for iteration in range(self.max_iterations):
            context = build_context(self.functions, self.context_budget)
            prompt = build_prompt(self.instructions, context, chunk)

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
                return

            if result["code"]:
                self.functions.append({
                    "name": result["name"],
                    "docstring": result["docstring"],
                    "code": result["code"],
                })
                print(f"  Generated: {result['name']}")
            else:
                # LLM said needs_more_work but didn't provide code
                print(f"  Warning: iteration {iteration + 1} produced no function")

        print(f"  Warning: chunk {chunk_idx} hit max iterations ({self.max_iterations})")

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

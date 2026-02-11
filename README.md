# Recursive Data Cleaner

LLM-powered incremental data cleaning for massive datasets. Process files in chunks, identify quality issues, and automatically generate Python cleaning functions.

## How It Works

1. **Chunk** your data (JSONL, CSV, JSON, Parquet, PDF, Word, Excel, XML, and more)
2. **Analyze** each chunk with an LLM to identify issues
3. **Generate** one cleaning function per issue
4. **Validate** functions on holdout data before accepting
5. **Output** a ready-to-use `cleaning_functions.py`

The system maintains a "docstring registry" - feeding generated function descriptions back into prompts so the LLM knows what's already solved and avoids duplicate work.

## Installation

```bash
pip install -e .
```

For Apple Silicon (MLX backend):
```bash
pip install -e ".[mlx]"
```

For document conversion (PDF, Word, Excel, HTML, etc.):
```bash
pip install -e ".[markitdown]"
```

For Parquet files:
```bash
pip install -e ".[parquet]"
```

For Excel files (.xlsx/.xls):
```bash
pip install -e ".[excel]"
```

For Terminal UI (Rich dashboard):
```bash
pip install -e ".[tui]"
```

## Quick Start

```python
from recursive_cleaner import DataCleaner
from backends import MLXBackend

# Any LLM with generate(prompt) -> str works
llm = MLXBackend(model_path="your-model")

cleaner = DataCleaner(
    llm_backend=llm,
    file_path="messy_data.jsonl",
    chunk_size=50,
    instructions="""
    - Normalize phone numbers to E.164
    - Fix typos in status field (valid: active, pending, churned)
    - Convert dates to ISO 8601
    """,
)

cleaner.run()  # Generates cleaning_functions.py
```

## Features

### Core
- **Chunked Processing**: Handle files larger than LLM context windows
- **Incremental Generation**: One function per issue, building up a complete solution
- **Docstring Registry**: Automatic context management with FIFO eviction
- **AST Validation**: All generated code validated before output
- **Error Recovery**: Retries with error feedback on parse failures
- **Processing Modes**: Auto-detect format from file extension, or force `structured` (record-by-record) or `text` (prose/document) mode

### Data Quality (v0.4.0+)
- **Holdout Validation**: Test functions on unseen 20% of each chunk
- **Sampling Strategies**: Sequential, random, or stratified sampling
- **Quality Metrics**: Before/after comparison with improvement reports
- **Dependency Resolution**: Topological sort for correct function ordering

### Optimization (v0.5.0+)
- **Two-Pass Consolidation**: Merge redundant functions after generation
- **Early Termination**: Stop when LLM detects pattern saturation
- **LLM Agency**: Model decides chunk cleanliness and saturation

### Validation (v0.5.1+, v1.0.1)
- **Dangerous Code Detection**: AST-based detection of exec, eval, subprocess, network calls
- **Return Type Validation**: Ensures generated functions return the correct type (`dict` for structured, `str` for text)
- **Duplicate Field Detection**: Prevents multiple functions from modifying the same field, asks LLM to target a different issue instead

### Observability (v0.6.0)
- **Latency Metrics**: Track min/max/avg/total LLM call times
- **Import Consolidation**: Deduplicate and merge imports in output
- **Cleaning Reports**: Markdown summary with functions, timing, quality delta
- **Dry-Run Mode**: Analyze data without generating functions

### Format Expansion (v0.7.0)
- **Markitdown Integration**: Convert 20+ formats (PDF, Word, Excel, PowerPoint, HTML, EPUB, etc.) to text
- **Parquet Support**: Load parquet files as structured data via pyarrow
- **LLM-Generated Parsers**: Auto-generate parsers for XML and unknown formats (`auto_parse=True`)

### Terminal UI (v0.8.0)
- **Mission Control Dashboard**: Rich-based live terminal UI with retro aesthetic
- **Real-time Progress**: Animated progress bars, chunk/iteration counters
- **Transmission Log**: Parsed LLM responses showing issues detected and functions being generated
- **Token Estimation**: Track estimated input/output tokens across the run
- **Graceful Fallback**: Works without Rich installed (falls back to callbacks)

### CLI (v0.9.0)
- **Command Line Interface**: Use without writing Python code
- **Multiple Backends**: MLX (Apple Silicon) and OpenAI-compatible (OpenAI, LM Studio, Ollama)
- **Four Commands**: `generate`, `analyze` (dry-run), `resume`, `apply`

### Apply Mode (v1.0.0)
- **Apply Cleaning Functions**: Apply generated functions to full datasets
- **Data Formats**: JSONL, CSV, JSON, Parquet, Excel (.xlsx/.xls) output same format
- **Text Formats**: PDF, Word, HTML, etc. output as Markdown
- **Streaming**: Memory-efficient line-by-line processing for JSONL/CSV
- **Colored TUI**: Enhanced transmission log with syntax-highlighted XML parsing

## Command Line Interface

After installation, the `recursive-cleaner` command is available:

```bash
# Generate cleaning functions with MLX (Apple Silicon)
recursive-cleaner generate data.jsonl \
  --provider mlx \
  --model "lmstudio-community/Qwen3-80B-MLX-4bit" \
  --instructions "Normalize phone numbers to E.164" \
  --output cleaning_functions.py

# Use OpenAI
export OPENAI_API_KEY=your-key
recursive-cleaner generate data.jsonl \
  --provider openai \
  --model gpt-4o \
  --instructions "Fix date formats"

# Use LM Studio or Ollama (OpenAI-compatible)
recursive-cleaner generate data.jsonl \
  --provider openai \
  --model "qwen/qwen3-vl-30b" \
  --base-url http://localhost:1234/v1 \
  --instructions "Normalize prices"

# Dry-run analysis
recursive-cleaner analyze data.jsonl \
  --provider openai \
  --model gpt-4o \
  --instructions @instructions.txt

# Resume from checkpoint
recursive-cleaner resume cleaning_state.json \
  --provider mlx \
  --model "model-path"

# Apply cleaning functions to data
recursive-cleaner apply data.jsonl \
  --functions cleaning_functions.py \
  --output cleaned_data.jsonl

# Apply to Excel (outputs same format)
recursive-cleaner apply sales.xlsx \
  --functions cleaning_functions.py

# Apply to PDF (outputs markdown)
recursive-cleaner apply document.pdf \
  --functions cleaning_functions.py \
  --output cleaned.md
```

### CLI Options

```
recursive-cleaner generate <FILE> [OPTIONS]

Required:
  FILE                      Input data file
  -p, --provider {mlx,openai}  LLM provider
  -m, --model MODEL         Model name/path

Optional:
  -i, --instructions TEXT   Cleaning instructions (text, @file.txt, or - for stdin)
  --base-url URL            API URL for OpenAI-compatible servers
  --api-key KEY             API key (or use OPENAI_API_KEY env var)
  --chunk-size N            Items per chunk (default: 50)
  --max-iterations N        Max iterations per chunk (default: 5)
  --mode {auto,structured,text}  Processing mode (default: auto)
  -o, --output PATH         Output file (default: cleaning_functions.py)
  --report PATH             Report file (empty to disable, default: cleaning_report.md)
  --state-file PATH         Checkpoint file for resume on interrupt
  --tui                     Enable Rich dashboard
  --optimize                Consolidate redundant functions
  --track-metrics           Measure before/after quality
  --early-termination       Stop when LLM detects pattern saturation
```

```
recursive-cleaner analyze <FILE> [OPTIONS]

Required:
  FILE                      Input data file
  -p, --provider {mlx,openai}  LLM provider
  -m, --model MODEL         Model name/path

Optional:
  -i, --instructions TEXT   Cleaning instructions (text, @file.txt, or - for stdin)
  --base-url URL            API URL for OpenAI-compatible servers
  --api-key KEY             API key (or use OPENAI_API_KEY env var)
  --chunk-size N            Items per chunk (default: 50)
  --max-iterations N        Max iterations per chunk (default: 5)
  --mode {auto,structured,text}  Processing mode (default: auto)
  --tui                     Enable Rich dashboard
```

```
recursive-cleaner resume <STATE_FILE> [OPTIONS]

Required:
  STATE_FILE                Path to checkpoint JSON file
  -p, --provider {mlx,openai}  LLM provider
  -m, --model MODEL         Model name/path

Optional:
  --base-url URL            API URL for OpenAI-compatible servers
  --api-key KEY             API key (or use OPENAI_API_KEY env var)
```

```
recursive-cleaner apply <FILE> [OPTIONS]

Required:
  FILE                      Input data file
  -f, --functions PATH      Path to cleaning_functions.py

Optional:
  -o, --output PATH         Output file (default: <input>.cleaned.<ext>)
```

Exit codes: 0 = success, 1 = general error, 2 = backend error, 3 = validation error

## Configuration

```python
cleaner = DataCleaner(
    # Required
    llm_backend=llm,
    file_path="data.jsonl",

    # Chunking & mode
    chunk_size=50,              # Items per chunk (or chars for text mode)
    max_iterations=5,           # Max LLM iterations per chunk before moving on
    context_budget=8000,        # Max chars for docstring registry fed into prompts
    mode="auto",                # "auto" detects from extension; "structured" for records, "text" for prose
    chunk_overlap=200,          # Chars of overlap between text chunks to avoid splitting context

    # Validation
    validate_runtime=True,      # Test functions before accepting
    schema_sample_size=10,      # Records for schema inference
    holdout_ratio=0.2,          # Fraction held out for validation

    # Sampling
    sampling_strategy="stratified",  # "sequential", "random", "stratified"
    stratify_field="status",         # Field for stratified sampling

    # Optimization
    optimize=True,              # Two-pass: merge redundant functions after generation
    optimize_threshold=10,      # Only run consolidation when >= N functions exist
    early_termination=True,     # Ask LLM if new patterns are unlikely; stop if saturated
    saturation_check_interval=20,  # How many chunks between saturation checks
    track_metrics=True,         # Measure null counts, empty strings, uniqueness before/after

    # Output
    output_path="cleaning_functions.py",  # Where to write the generated Python file
    report_path="report.md",    # Markdown summary with functions, latency, quality delta (None to disable)
    dry_run=False,              # If True, detect issues but don't generate or save functions

    # Format Expansion
    auto_parse=False,           # If True, ask LLM to generate a parser for unrecognized file formats

    # Terminal UI
    tui=True,                   # Enable Rich dashboard (requires [tui] extra)

    # Progress & State
    on_progress=callback,       # Progress event callback
    state_file="state.json",    # Enable resume on interrupt
)
```

## Progress Events

```python
def on_progress(event):
    match event["type"]:
        case "chunk_start":
            print(f"Chunk {event['chunk_index']}/{event['total_chunks']}")
        case "iteration":
            print(f"Iteration {event['iteration']}")
        case "llm_call":
            print(f"LLM latency: {event['latency_ms']}ms")
        case "function_generated":
            print(f"Generated: {event['function_name']}")
        case "validation_failed":
            print(f"Validation failed for {event['function_name']}: {event['error']}")
        case "safety_failed":
            print(f"Safety check failed for {event['function_name']}: {event['error']}")
        case "duplicate_field":
            print(f"Duplicate field in {event['function_name']}: {event['fields']}")
        case "chunk_done":
            print(f"Chunk {event['chunk_index']} done")
        case "issues_detected":  # dry-run mode
            print(f"Found {len(event['issues'])} issues")
        case "dry_run_complete":
            print("Dry run finished")
        case "optimize_start":
            print(f"Optimizing {event['function_count']} functions")
        case "optimize_complete":
            print(f"Optimized: {event['original']} -> {event['final']} functions")
        case "saturation_check":
            print(f"Saturated: {event['saturated']} ({event['confidence']})")
        case "early_termination":
            print("Stopped early: patterns saturated")
        case "parser_generation_start":
            print("Generating parser for unknown format")
        case "apply_start":
            print("Starting to apply cleaning functions")
        case "apply_progress":
            print(f"Records processed: {event['records_processed']}")
        case "apply_complete":
            print(f"Applied to {event['total_records']} records -> {event['output_path']}")
        case "complete":
            stats = event["latency_stats"]
            print(f"Done! Avg latency: {stats['avg_ms']}ms")
```

## Output

The cleaner generates `cleaning_functions.py`:

```python
# Auto-generated cleaning functions
import re

def normalize_phone_numbers(data):
    """Normalize phone numbers to E.164 format."""
    # ... implementation ...

def fix_status_typos(data):
    """Fix typos in status field."""
    # ... implementation ...

def clean_data(data):
    """Apply all cleaning functions in order."""
    data = normalize_phone_numbers(data)
    data = fix_status_typos(data)
    return data
```

## Custom LLM Backend

Implement the simple protocol:

```python
class MyBackend:
    def generate(self, prompt: str) -> str:
        # Call your LLM (OpenAI, Anthropic, local, etc.)
        return response
```

## Text Mode

For plain text files (PDFs, documents):

```python
cleaner = DataCleaner(
    llm_backend=llm,
    file_path="document.txt",
    chunk_size=4000,  # Characters, not items
    instructions="Fix OCR errors, normalize whitespace",
)
```

Text mode uses sentence-aware chunking to avoid splitting mid-sentence.

## Resume on Interrupt

```python
# Start with state file
cleaner = DataCleaner(
    llm_backend=llm,
    file_path="huge_file.jsonl",
    state_file="cleaning_state.json",
)
cleaner.run()

# If interrupted, resume later:
cleaner = DataCleaner.resume("cleaning_state.json", llm)
cleaner.run()
```

## Architecture

```
recursive_cleaner/
├── apply.py            # Apply cleaning functions to data
├── cli.py              # Command line interface
├── cleaner.py          # Main DataCleaner class
├── context.py          # Docstring registry with FIFO eviction
├── dependencies.py     # Topological sort for function ordering
├── errors.py           # Exception classes (CleanerError, ParseError, etc.)
├── latency.py          # LLM call timing and LatencyTracker
├── metrics.py          # Quality metrics before/after
├── optimizer.py        # Two-pass consolidation with LLM agency
├── output.py           # Function file generation + import consolidation
├── parser_generator.py # LLM-generated parsers for unknown formats
├── parsers.py          # Chunking for all formats + sampling
├── prompt.py           # LLM prompt templates
├── report.py           # Markdown report generation
├── response.py         # XML/markdown parsing + agency dataclasses
├── schema.py           # Schema inference
├── state.py            # Pipeline state persistence
├── tui.py              # Rich terminal dashboard
├── types.py            # LLMBackend protocol
├── validation.py       # Runtime validation + holdout + safety
└── vendor/
    └── chunker.py      # Vendored sentence-aware chunker

backends/
├── mlx_backend.py      # MLX-LM backend for Apple Silicon
└── openai_backend.py   # OpenAI-compatible backend
```

## Testing

```bash
pytest tests/ -v
```

555 tests covering all features. Test datasets in `test_cases/`:
- E-commerce product catalogs
- Healthcare patient records
- Financial transaction data

## Philosophy

- **Simplicity over extensibility**: ~5,000 lines that do one thing well
- **stdlib over dependencies**: Only `tenacity` required
- **Retry over recover**: On error, retry with error in prompt
- **Wu wei**: Let the LLM make decisions about data it understands

## Version History

| Version | Features |
|---------|----------|
| v1.0.2 | Documentation completeness, version alignment |
| v1.0.1 | Return type validation, prompt signature clarity, duplicate field detection |
| v1.0.0 | Apply mode for cleaning data, Excel support (.xlsx/.xls), enhanced TUI colors |
| v0.9.0 | CLI tool with MLX and OpenAI-compatible backends (LM Studio, Ollama) |
| v0.8.0 | Terminal UI with Rich dashboard, mission control aesthetic, transmission log |
| v0.7.0 | Markitdown (20+ formats), Parquet support, LLM-generated parsers |
| v0.6.0 | Latency metrics, import consolidation, cleaning report, dry-run mode |
| v0.5.1 | Dangerous code detection (AST-based security) |
| v0.5.0 | Two-pass optimization, early termination, LLM agency |
| v0.4.0 | Holdout validation, dependency resolution, sampling, quality metrics |
| v0.3.0 | Text mode with sentence-aware chunking |
| v0.2.0 | Runtime validation, schema inference, callbacks, incremental saves |
| v0.1.0 | Core pipeline, chunking, docstring registry |

## Acknowledgments

- Sentence-aware text chunking adapted from [Chonkie](https://github.com/chonkie-inc/chonkie) (MIT License)
- Development assisted by [Claude Code](https://claude.ai/claude-code)

## License

MIT

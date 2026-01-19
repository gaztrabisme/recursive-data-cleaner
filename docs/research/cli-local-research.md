# CLI Local Research - v0.9.0

## 1. DataCleaner Constructor Parameters (23 total)

### Required
| Parameter | Type | Description |
|-----------|------|-------------|
| `llm_backend` | `LLMBackend` | LLM implementation (Protocol) |

### Core File & Processing
| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `file_path` | `str` | - | Path to input file |
| `chunk_size` | `int` | `50` | Items per chunk (structured) or chars (text) |
| `instructions` | `str` | `""` | Cleaning goals for LLM |

### Iteration & Context
| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `max_iterations` | `int` | `5` | Max iterations per chunk |
| `context_budget` | `int` | `8000` | Max chars of function context |

### Validation & Safety
| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `validate_runtime` | `bool` | `True` | Test functions before accepting |
| `schema_sample_size` | `int` | `10` | Rows for schema inference |

### Sampling & Metrics (v0.4.0)
| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `holdout_ratio` | `float` | `0.2` | Holdout fraction for validation |
| `sampling_strategy` | `Literal` | `"sequential"` | sequential/random/stratified |
| `stratify_field` | `str\|None` | `None` | Field for stratified sampling |
| `track_metrics` | `bool` | `False` | Measure quality before/after |

### File Handling
| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `mode` | `Literal` | `"auto"` | auto/structured/text |
| `chunk_overlap` | `int` | `200` | Char overlap for text chunks |
| `auto_parse` | `bool` | `False` | Generate parser for unknown formats |

### Optimization (v0.5.0)
| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `optimize` | `bool` | `False` | Consolidate redundant functions |
| `optimize_threshold` | `int` | `10` | Min functions before optimization |
| `early_termination` | `bool` | `False` | Stop on pattern saturation |
| `saturation_check_interval` | `int` | `20` | Check saturation every N chunks |

### Observability & Output (v0.6.0-v0.8.0)
| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `state_file` | `str\|None` | `None` | Resume checkpoint path |
| `report_path` | `str\|None` | `"cleaning_report.md"` | Markdown report output |
| `dry_run` | `bool` | `False` | Analyze without generating |
| `tui` | `bool` | `False` | Rich terminal dashboard |

### Callback
| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `on_progress` | `Callable\|None` | `None` | Event callback |

---

## 2. DataCleaner Methods

### Instance Methods
- `.run() -> None` - Main execution
- `.get_improvement_report() -> dict | None` - Quality improvement stats

### Class Methods
- `.resume(state_file: str, llm_backend: LLMBackend) -> DataCleaner` - Resume from checkpoint

---

## 3. LLM Backend Protocol

```python
class LLMBackend(Protocol):
    def generate(self, prompt: str) -> str: ...
```

### Built-in Backend
- `MLXBackend` - Apple Silicon (mlx-lm)
  - Params: `model_path`, `max_tokens`, `temperature`, `top_p`, `repetition_penalty`, `verbose`

---

## 4. CLI Flag Mapping

### Positional
```
FILE                         → file_path
```

### Simple Value Flags
```
--chunk-size INT             → chunk_size
--max-iterations INT         → max_iterations
--context-budget INT         → context_budget
--holdout-ratio FLOAT        → holdout_ratio
--schema-sample-size INT     → schema_sample_size
--chunk-overlap INT          → chunk_overlap
--optimize-threshold INT     → optimize_threshold
--saturation-interval INT    → saturation_check_interval
--stratify-field FIELD       → stratify_field
--state-file PATH            → state_file
--report-path PATH           → report_path
--output PATH                → output file (cleaning_functions.py location)
```

### Choice Flags
```
--mode {auto,structured,text}
--sampling {sequential,random,stratified}
```

### Boolean Flags
```
--validate / --no-validate   → validate_runtime
--track-metrics              → track_metrics
--optimize                   → optimize
--early-termination          → early_termination
--dry-run                    → dry_run
--tui                        → tui
--auto-parse                 → auto_parse
```

### Special Handling Needed
```
--instructions TEXT          → instructions (or @file.txt to read from file)
--backend SPEC               → llm_backend (needs factory function)
```

---

## 5. Design Decisions

### Backend Specification
Options:
1. **Environment variable**: `RECURSIVE_CLEANER_BACKEND=mlx:model-path`
2. **CLI flag**: `--backend mlx:model-path`
3. **Config file**: `~/.recursive-cleaner.toml`

Recommendation: CLI flag with env var fallback. Keep it simple.

### Instructions Handling
- `--instructions "text"` for short instructions
- `--instructions @file.txt` to read from file
- `--instructions -` to read from stdin

### Subcommand Structure
```bash
recursive-cleaner generate FILE [OPTIONS]   # Main workflow (default)
recursive-cleaner analyze FILE [OPTIONS]    # Dry-run mode
recursive-cleaner resume STATE_FILE         # Resume from checkpoint
```

Note: `apply` command deferred to v1.0.0

### Output Defaults
- `cleaning_functions.py` in current directory
- `cleaning_report.md` in current directory (if track_metrics)
- Configurable via `--output` and `--report-path`

---

## 6. Test Patterns

Typical test instantiation:
```python
cleaner = DataCleaner(
    llm_backend=mock_llm,
    file_path=str(test_file),
    chunk_size=10,
    instructions="Fix phone numbers",
)
cleaner.run()
```

CLI tests should:
- Use `subprocess.run()` or mock `sys.argv`
- Capture stdout/stderr
- Check exit codes
- Verify output files created

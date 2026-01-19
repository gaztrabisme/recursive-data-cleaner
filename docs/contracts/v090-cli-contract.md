# CLI Contract - v0.9.0

## Command Structure

```
recursive-cleaner <command> [options]
```

### Commands

| Command | Description |
|---------|-------------|
| `generate` | Generate cleaning functions (main workflow) |
| `analyze` | Dry-run analysis without generating functions |
| `resume` | Resume from checkpoint file |

---

## Command: `generate`

Generate cleaning functions from data file.

```bash
recursive-cleaner generate <FILE> [OPTIONS]
```

### Required Arguments

| Argument | Description |
|----------|-------------|
| `FILE` | Path to input data file |

### Required Options (one of)

| Option | Description |
|--------|-------------|
| `--provider` / `-p` | LLM provider: `mlx` or `openai` |
| `--model` / `-m` | Model name/path |

### Optional: Instructions

| Option | Description | Default |
|--------|-------------|---------|
| `--instructions` / `-i` | Cleaning instructions (text or `@file.txt`) | `""` |

### Optional: Provider Config

| Option | Description | Default |
|--------|-------------|---------|
| `--base-url` | API base URL (for openai-compatible) | Provider default |
| `--api-key` | API key (or use env var) | `$OPENAI_API_KEY` |

### Optional: Processing

| Option | Description | Default |
|--------|-------------|---------|
| `--chunk-size` | Items per chunk | `50` |
| `--max-iterations` | Max iterations per chunk | `5` |
| `--mode` | Processing mode: `auto`, `structured`, `text` | `auto` |

### Optional: Output

| Option | Description | Default |
|--------|-------------|---------|
| `--output` / `-o` | Output file path | `cleaning_functions.py` |
| `--report` | Report file path (empty to disable) | `cleaning_report.md` |
| `--state-file` | Checkpoint file for resume | None |

### Optional: Features

| Option | Description | Default |
|--------|-------------|---------|
| `--tui` | Enable Rich terminal dashboard | `False` |
| `--optimize` | Consolidate redundant functions | `False` |
| `--track-metrics` | Measure before/after quality | `False` |
| `--early-termination` | Stop on pattern saturation | `False` |

### Example

```bash
recursive-cleaner generate data.jsonl \
  --provider mlx \
  --model "lmstudio-community/Qwen3-80B-MLX-4bit" \
  --instructions "Normalize phone numbers to E.164" \
  --chunk-size 50 \
  --tui \
  --output cleaning_functions.py
```

---

## Command: `analyze`

Dry-run analysis (same as `generate --dry-run`).

```bash
recursive-cleaner analyze <FILE> [OPTIONS]
```

Same options as `generate`, but:
- Does not generate `cleaning_functions.py`
- Reports issues detected per chunk
- Useful for data assessment

### Example

```bash
recursive-cleaner analyze data.jsonl \
  --provider openai \
  --model gpt-4o \
  --instructions @instructions.txt
```

---

## Command: `resume`

Resume from checkpoint file.

```bash
recursive-cleaner resume <STATE_FILE> [OPTIONS]
```

### Required Arguments

| Argument | Description |
|----------|-------------|
| `STATE_FILE` | Path to checkpoint JSON file |

### Required Options

| Option | Description |
|--------|-------------|
| `--provider` / `-p` | LLM provider |
| `--model` / `-m` | Model name/path |

### Optional Options

Same provider config options as `generate` (`--base-url`, `--api-key`).

### Example

```bash
recursive-cleaner resume cleaning_state.json \
  --provider mlx \
  --model "model-path"
```

---

## Exit Codes

| Code | Meaning |
|------|---------|
| `0` | Success |
| `1` | General error (invalid args, file not found, etc.) |
| `2` | LLM backend error (API failure, model not found) |
| `3` | Validation error (generated code failed validation) |

---

## Environment Variables

| Variable | Description |
|----------|-------------|
| `OPENAI_API_KEY` | API key for OpenAI provider |
| `RECURSIVE_CLEANER_DEFAULT_PROVIDER` | Default provider if not specified |
| `RECURSIVE_CLEANER_DEFAULT_MODEL` | Default model if not specified |

---

## Instructions Format

Instructions can be provided as:

1. **Inline text**: `--instructions "Normalize phone numbers"`
2. **File reference**: `--instructions @instructions.txt`
3. **Stdin**: `--instructions -` (reads from stdin)

---

## Output Files

### cleaning_functions.py

Generated Python file with:
- Import statements (consolidated)
- Individual cleaning functions
- `clean_data()` entrypoint function

### cleaning_report.md (if `--track-metrics`)

Markdown report with:
- Functions generated
- Quality metrics (before/after)
- Latency statistics
- Per-chunk breakdown

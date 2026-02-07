# Success Criteria - v0.9.0 CLI Tool

## Project-Level Success

- [ ] `recursive-cleaner` command available after `pip install`
- [ ] Can generate cleaning functions via CLI without writing Python
- [ ] Supports MLX and OpenAI-compatible backends
- [ ] All existing tests pass (465+)
- [ ] New CLI tests pass

---

## Phase 1: Core CLI Module

### Deliverables
- [ ] `recursive_cleaner/cli.py` - Main CLI module (~180 lines)
- [ ] `recursive_cleaner/__main__.py` - Entry point (~5 lines)
- [ ] `backends/openai_backend.py` - OpenAI-compatible backend (~30 lines)

### Success Criteria

**1. Entry point works**
```bash
pip install -e .
recursive-cleaner --help
# Exit code: 0
# Output: Shows usage with generate, analyze, resume commands
```

**2. Generate command creates output**
```bash
recursive-cleaner generate test_cases/ecommerce_products.jsonl \
  --provider mlx \
  --model "test-model" \
  --instructions "Fix prices" \
  --chunk-size 5 \
  --max-iterations 1
# Exit code: 0
# Creates: cleaning_functions.py
```

**3. Analyze command runs dry-run**
```bash
recursive-cleaner analyze test_cases/ecommerce_products.jsonl \
  --provider mlx \
  --model "test-model" \
  --instructions "Fix prices"
# Exit code: 0
# Does NOT create: cleaning_functions.py
# Output: Issues detected per chunk
```

**4. Resume command works**
```bash
recursive-cleaner resume cleaning_state.json \
  --provider mlx \
  --model "test-model"
# Exit code: 0 (if valid state file)
# Exit code: 1 (if file not found)
```

**5. OpenAI backend works**
```bash
export OPENAI_API_KEY=test-key
recursive-cleaner generate data.jsonl \
  --provider openai \
  --model gpt-4o \
  --instructions "Test"
# Backend instantiated with correct base_url and api_key
```

**6. LM Studio / Ollama via base-url**
```bash
recursive-cleaner generate data.jsonl \
  --provider openai \
  --model local-model \
  --base-url http://localhost:1234/v1 \
  --instructions "Test"
# Backend uses custom base_url
```

**7. Instructions from file**
```bash
echo "Normalize phones" > /tmp/inst.txt
recursive-cleaner generate data.jsonl \
  --provider mlx \
  --model test \
  --instructions @/tmp/inst.txt
# Instructions read from file
```

**8. TUI flag passed through**
```bash
recursive-cleaner generate data.jsonl \
  --provider mlx \
  --model test \
  --instructions "Test" \
  --tui
# TUI enabled (if Rich installed)
```

**9. Exit codes correct**
```bash
recursive-cleaner generate nonexistent.jsonl --provider mlx --model x
# Exit code: 1

recursive-cleaner generate data.jsonl --provider invalid --model x
# Exit code: 2
```

---

## Test Requirements

### Unit Tests (`tests/test_cli.py`)
- [ ] `test_help_command` - `--help` returns 0
- [ ] `test_generate_command_args` - Parses all flags correctly
- [ ] `test_analyze_command_args` - Parses analyze flags
- [ ] `test_resume_command_args` - Parses resume flags
- [ ] `test_instructions_from_file` - `@file.txt` syntax works
- [ ] `test_instructions_inline` - Inline text works
- [ ] `test_exit_code_file_not_found` - Returns 1 for missing file
- [ ] `test_exit_code_invalid_provider` - Returns 2 for bad provider
- [ ] `test_backend_factory_mlx` - Creates MLXBackend
- [ ] `test_backend_factory_openai` - Creates OpenAIBackend
- [ ] `test_backend_factory_openai_custom_url` - Uses custom base_url
- [ ] `test_env_var_api_key` - Reads OPENAI_API_KEY from env

### Integration Tests
- [ ] `test_generate_end_to_end` - Full generate with mock LLM
- [ ] `test_analyze_end_to_end` - Full analyze with mock LLM
- [ ] `test_resume_end_to_end` - Full resume with mock LLM

---

## Line Count Budget

| File | Target | Max |
|------|--------|-----|
| `cli.py` | 180 | 220 |
| `__main__.py` | 5 | 10 |
| `openai_backend.py` | 30 | 50 |
| `test_cli.py` | 150 | 200 |
| **Total new** | 365 | 480 |

---

## Non-Goals (Deferred)

- [ ] `apply` command (v1.0.0)
- [ ] Config file support (`~/.config/recursive-cleaner/`)
- [ ] Anthropic-specific backend (use OpenAI-compatible)
- [ ] Interactive mode

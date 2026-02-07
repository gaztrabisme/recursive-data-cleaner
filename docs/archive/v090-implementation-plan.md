# Implementation Plan - v0.9.0 CLI Tool

## Overview

Add a CLI interface to recursive-cleaner using argparse (stdlib). Two backends: MLX (existing) and OpenAI-compatible (new).

## Technology Stack

| Layer | Choice | Rationale |
|-------|--------|-----------|
| CLI Framework | argparse | stdlib, no dependencies |
| Entry Point | `[project.scripts]` | Standard pip-installable pattern |
| OpenAI Backend | `openai` SDK | Already common dependency, handles auth |

## Phase Breakdown

### Phase 1: OpenAI Backend (~30 lines)

**Objective:** Add OpenAI-compatible backend that works with OpenAI, LM Studio, Ollama.

**Deliverables:**
- [ ] `backends/openai_backend.py` - OpenAIBackend class
- [ ] `backends/__init__.py` - Export OpenAIBackend
- [ ] `tests/test_openai_backend.py` - Backend tests

**Success Criteria:**
- [ ] `OpenAIBackend(model="gpt-4o").generate(prompt)` returns string
- [ ] Custom `base_url` works for LM Studio/Ollama
- [ ] Reads `OPENAI_API_KEY` from environment
- [ ] Falls back to `"not-needed"` for local servers

**Estimated Complexity:** Low

**Dependencies:** None

---

### Phase 2: CLI Module (~180 lines)

**Objective:** Implement argparse CLI with generate, analyze, resume commands.

**Deliverables:**
- [ ] `recursive_cleaner/cli.py` - Main CLI module
- [ ] `recursive_cleaner/__main__.py` - `python -m recursive_cleaner` support

**Success Criteria:**
- [ ] `python -m recursive_cleaner --help` shows all commands
- [ ] `generate` command parses all flags from contract
- [ ] `analyze` command sets `dry_run=True`
- [ ] `resume` command calls `DataCleaner.resume()`
- [ ] `--instructions @file.txt` reads from file
- [ ] Backend factory creates correct backend from `--provider`
- [ ] Exit codes match contract (0, 1, 2, 3)

**Estimated Complexity:** Medium

**Dependencies:** Phase 1 (OpenAI backend)

---

### Phase 3: Entry Point & Integration (~10 lines)

**Objective:** Make `recursive-cleaner` command available after pip install.

**Deliverables:**
- [ ] `pyproject.toml` - Add `[project.scripts]` entry
- [ ] Update `recursive_cleaner/__init__.py` - Export cli module

**Success Criteria:**
- [ ] `pip install -e .` succeeds
- [ ] `recursive-cleaner --help` works from terminal
- [ ] `recursive-cleaner generate --help` shows generate options

**Estimated Complexity:** Low

**Dependencies:** Phase 2

---

### Phase 4: Tests (~150 lines)

**Objective:** Comprehensive test coverage for CLI.

**Deliverables:**
- [ ] `tests/test_cli.py` - CLI unit and integration tests

**Success Criteria:**
- [ ] All 15+ tests from success criteria pass
- [ ] Test coverage for argument parsing
- [ ] Test coverage for backend factory
- [ ] Test coverage for exit codes
- [ ] Integration test with mock LLM

**Estimated Complexity:** Medium

**Dependencies:** Phase 3

---

## File Structure After Implementation

```
recursive_cleaner/
    __init__.py          # Updated exports
    __main__.py          # NEW: Entry point
    cli.py               # NEW: CLI module
    cleaner.py           # Unchanged
    ...

backends/
    __init__.py          # Updated exports
    mlx_backend.py       # Unchanged
    openai_backend.py    # NEW: OpenAI-compatible backend

tests/
    test_cli.py          # NEW: CLI tests
    test_openai_backend.py  # NEW: Backend tests
    ...
```

## Risk Register

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| `openai` SDK not installed | Medium | Medium | Make optional, clear error message |
| argparse complexity | Low | Low | Keep to basic patterns, no custom actions |
| MLX import fails on non-Mac | Medium | Low | Lazy import, clear error |

## Out of Scope

- `apply` command (v1.0.0)
- Config file support
- Anthropic-specific backend
- Interactive prompts
- Shell completion

## Estimated Total

| Component | Lines |
|-----------|-------|
| `openai_backend.py` | 30 |
| `cli.py` | 180 |
| `__main__.py` | 5 |
| `test_cli.py` | 100 |
| `test_openai_backend.py` | 50 |
| pyproject.toml changes | 5 |
| **Total** | ~370 |

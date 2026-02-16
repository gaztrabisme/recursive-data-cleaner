# v1.1.0 Handoff — Pipeline Efficiency

## Delivered

| File | Changes |
|------|---------|
| `backends/mlx_backend.py` | Added `enable_thinking: bool = True` param, passes through to `apply_chat_template` when False |
| `recursive_cleaner/cleaner.py` | Removed per-chunk `_fields_covered` reset (cumulative cross-chunk dedup). Added `fruitless_iterations` counter with break after 2 consecutive no-code iterations. |
| `tests/test_mlx_backend.py` | New file: 4 tests for `enable_thinking` parameter (default, storage, kwarg passthrough, omission when True) |
| `tests/test_cleaner.py` | 2 new tests: adaptive budget stops early, fruitless counter resets on success |
| `tests/test_validation.py` | 1 new test: cross-chunk duplicate field rejected |
| `pyproject.toml` | Version bump 1.0.4 → 1.1.0 |

## Test Evidence

```
620 passed, 2 skipped (was 613 passed, 2 skipped)
+7 new tests, 0 regressions
```

## Key Decisions

1. **enable_thinking only passed when False** — When `enable_thinking=True` (default), the kwarg is omitted from `apply_chat_template` entirely. This preserves exact current behavior for models that don't support it. Only when explicitly disabled does the kwarg appear.

2. **Cumulative field dedup (delete, not add)** — Removed the `self._fields_covered = set()` reset in `_process_chunk`. One line deletion. Cross-chunk dups now rejected by the same AST-based field extraction that handles within-chunk dups. No new data structures needed.

3. **Fruitless = no code produced only** — Validation failures (safety, runtime, test cases, metric gate) don't count as fruitless because error feedback gives the LLM targeted context for the next attempt. Only the case where the LLM says "needs_more_work" but produces no code counts.

## What Next Session Needs To Know

- `MLXBackend(enable_thinking=False)` suppresses Qwen3 `<think>` blocks
- `_fields_covered` is now cumulative — a field can only be targeted by one function across the entire pipeline run
- Chunks auto-skip remaining iterations after 2 consecutive no-code responses
- The 2 skipped tests are `pytest.importorskip("openpyxl")` for Excel tests (pre-existing)

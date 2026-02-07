# Session 001: Refactor Cleaner

## Delivered

### Files Created
- `recursive_cleaner/latency.py` (53 lines) — LatencyTracker class + call_llm function
- `recursive_cleaner/state.py` (97 lines) — save_state, load_state, load_state_for_resume functions

### Files Modified
- `recursive_cleaner/cleaner.py` — 789 -> 729 lines (-60). Removed latency tracking inline code, state persistence logic
- `recursive_cleaner/parsers.py` — 456 -> 448 lines (-8). Replaced duplicate `_stratified_sample` with delegation to `_stratified_sample_dicts`
- `tests/test_latency.py` — Updated to use `cleaner._latency.call_count` etc. instead of `cleaner._latency_stats["call_count"]`

### Files Moved (docs archival)
- 8 implementation plan markdowns -> `docs/archive/`
- `docs/contracts/`, `docs/handoffs/`, `docs/research/` -> `docs/archive/`
- `docs/mlx-lm-guide.md`, `docs/workflow-state.md` -> `docs/archive/`

## Key Decisions
- **LatencyTracker as a class** (not functions) because it holds mutable state (counters). Cleaner composes with `self._latency = LatencyTracker()`.
- **State functions are standalone** (not a class) because they don't hold state — they serialize/deserialize. Cleaner calls them with explicit parameters.
- **Sampling consolidation via delegation** — `_stratified_sample` (JSONL strings) parses to dicts and delegates to `_stratified_sample_dicts`, then maps back. Uses `id()` for O(1) reverse mapping.

## Test Evidence
```
555 passed in 4.88s  (after all changes)
```

All 555 tests passed at every step.

## Verify
```bash
python3 -m pytest --tb=short -q
wc -l recursive_cleaner/cleaner.py  # Should be 729
```

# Refactor Assessment: Recursive Data Cleaner

**Date:** 2026-02-07
**Scope:** Entire project
**Codebase:** 54 Python files, ~15,700 lines (22 library, 25 tests, 7 scripts/demos)

---

## Executive Summary

This is a **healthy, well-structured codebase** that delivers on its design philosophy of "elegant, clean, lean, path of least resistance." The core library (`recursive_cleaner/`) is 22 files totaling ~4,900 lines — impressively lean for what it does. 555 tests pass. The only file that genuinely warrants attention is `cleaner.py` at 789 lines — it's accumulating concerns and approaching the threshold where it becomes hard to navigate. Everything else is either fine or cosmetic.

---

## What's Working Well

**Clear module boundaries.** Each file in `recursive_cleaner/` has one job you can describe in a sentence: `parsers.py` chunks files, `response.py` parses XML, `validation.py` checks safety, `optimizer.py` groups and consolidates. This is textbook separation of concerns.

**Consistent patterns.** LLM interactions follow the same prompt -> call -> parse -> validate cycle everywhere. Error handling is uniform (retry with error feedback appended). The XML parsing approach in `response.py` handles three different response types (cleaning, consolidation, saturation) with the same structure.

**No dependency bloat.** The only real runtime dependency is `tenacity`. Everything else (Rich, pyarrow, markitdown, openpyxl) is optional with graceful `ImportError` handling. This is exactly right.

**Test coverage is excellent.** 555 tests across 25 test files. Test files mirror source files 1:1. Test names are descriptive. The oversized test files (`test_optimizer.py` at 1,504 lines, `test_integration.py` at 943 lines) are natural — they're exercising complex behaviors with many scenarios.

**Clean dependency graph.** No real circular dependencies (the ones flagged are `__init__.py` re-exports, which are benign and standard Python). Import hotspot is `recursive_cleaner/__init__.py`, which is expected — it's the public API surface.

---

## What Hurts

### 1. `cleaner.py` is accumulating too many concerns (789 lines) — High impact, Low effort

**Evidence:** `recursive_cleaner/cleaner.py` — 789 lines, 1 class (`DataCleaner`) with 14 methods.

The `DataCleaner` class currently handles:
- Pipeline orchestration (`run()`, `_process_chunk()`)
- State persistence (`_save_state()`, `_load_state()`, `resume()`)
- Latency tracking (`_call_llm_timed()`, `_get_latency_summary()`)
- TUI integration (scattered `if self._tui_renderer:` checks in 8+ places)
- Optimization orchestration (`_optimize_functions()`)
- Saturation checking (`_check_saturation()`)
- Report writing (`_write_report()`)
- Dry-run mode (`_process_chunk_dry_run()`)
- Duplicate field detection

This isn't broken yet — it's readable and working. But it's the one file where adding the next feature will feel uncomfortable. The 27-parameter `__init__` is a signal.

**Recommended extraction (one at a time, test after each):**

| Extract | From | Lines saved | Effort |
|---------|------|-------------|--------|
| Latency tracking to `latency.py` | `_call_llm_timed()`, `_get_latency_summary()`, `_latency_stats` dict | ~50 | Trivial |
| State persistence to its own module | `_save_state()`, `_load_state()`, `resume()` | ~80 | Low |

These two alone bring `cleaner.py` under 650 lines and remove the two most self-contained concerns. The TUI integration wiring and dry-run mode are more interleaved and not worth extracting until the class grows further.

### 2. Duplicate stratified sampling logic in `parsers.py` — Medium impact, Low effort

**Evidence:** `recursive_cleaner/parsers.py:388-455`

`_stratified_sample()` (for JSONL strings, lines 427-455) and `_stratified_sample_dicts()` (for dict lists, lines 388-411) implement the **exact same algorithm** — group by field, shuffle within groups, round-robin interleave. The only difference is that one parses JSON from strings first.

One function could handle both by accepting a key-extraction callable, or `_stratified_sample` could convert strings to dicts and delegate to `_stratified_sample_dicts`.

### 3. Docs directory has accumulated stale artifacts — Low impact, Low effort

**Evidence:** `docs/` — 44 files, ~14,000 lines

The `docs/` directory contains:
- 6 versioned implementation plans (`implementation-plan.md`, `-v03.md` through `v100-implementation-plan.md`)
- An `archive/` with framework analysis docs (langchain, smolagents, langgraph)
- `contracts/`, `handoffs/`, `research/` from orchestrated development phases
- A previous `refactor-assessment/` with stale data

These served their purpose during development. They're not causing bugs, but they add noise when exploring the codebase. The `archive/` directory is correctly named — the implementation plans could join it.

---

## What to Skip (Wu Wei filter)

**Test file sizes.** `test_optimizer.py` (1,504 lines), `test_integration.py` (943), `test_tui.py` (758), `test_validation.py` (740), `test_apply.py` (645). These are all big, but they're test files — cohesive collections of scenarios for a single module. Splitting them adds indirection without benefit. Leave them.

**`tui.py` at 614 lines.** It's a single-purpose rendering module. The ASCII banner alone is 14 lines. The layout code is inherently verbose with Rich's API. It's well-structured internally (dataclass state, separate `_refresh_*` methods). Not worth splitting.

**`apply.py` at 484 lines.** Each `apply_to_*` function handles one format. They're repetitive (read, transform, write) but intentionally so — no shared abstraction would be cleaner than the current explicit handlers. This is the right design.

**`__init__.py` as import hotspot.** 25 modules import from `recursive_cleaner`. This is normal — it's the public API package. The re-exports in `__init__.py` are clean and intentional.

**Circular dependency cycles.** The three flagged cycles all run through `__init__.py` re-exports (`recursive_cleaner` -> `recursive_cleaner.cleaner` -> `recursive_cleaner.optimizer` -> `recursive_cleaner.response` -> `recursive_cleaner`). These are benign `__init__.py` barrel-file patterns, not real architectural cycles. The actual module-to-module imports are acyclic.

**"Orphan" modules.** All 27 flagged orphans are test files, demo scripts, and test case runners — they're entry points, not dead code. Static analysis can't detect `pytest` test discovery.

**CLAUDE.md at 469 lines.** Under the 500-line threshold. It's comprehensive but not bloated.

---

## Dependency Analysis

### Hotspots (expected and healthy)
| Module | Imported by | Assessment |
|--------|-------------|------------|
| `recursive_cleaner` (init) | 25 modules | Expected — it's the public API |
| `recursive_cleaner.parsers` | 7 modules | Core utility, expected |
| `backends` | 6 modules | Expected — used by CLI, demos, tests |

### Circular Dependencies
All 3 cycles run through `__init__.py` — benign, standard Python package pattern. No action needed.

### External Dependencies
Runtime: `tenacity` (required), everything else optional.
This is the leanest dependency profile possible for the feature set.

---

## Priority Summary

| # | Finding | Impact | Effort | Action |
|---|---------|--------|--------|--------|
| 1 | `cleaner.py` accumulating concerns (789 lines) | High | Low | Extract latency tracking and state persistence |
| 2 | Duplicate stratified sampling in `parsers.py` | Medium | Low | Consolidate to single implementation |
| 3 | Stale docs artifacts | Low | Low | Move implementation plans to `docs/archive/` |

---

## Raw Data

- Analysis output: `docs/refactor-assessment/data/stats.json` (generated by analyze.py)
- Analysis script: `/Users/GaryT/.claude/skills/refactor-assessment/scripts/analyze.py`

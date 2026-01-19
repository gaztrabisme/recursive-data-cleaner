# Success Criteria: Rich TUI (v0.8.0)

## Project-Level Success

- [ ] `pip install recursive-cleaner[tui]` installs rich>=13.0
- [ ] `DataCleaner(..., tui=True)` shows live dashboard
- [ ] Dashboard displays all state from data schema contract
- [ ] Falls back gracefully when Rich not installed
- [ ] All 432 existing tests pass
- [ ] Zero breaking changes to existing API

## Phase 1: Core TUI Module

**Deliverables:**
- [ ] `recursive_cleaner/tui.py` with `TUIRenderer` class
- [ ] `HAS_RICH` check with graceful import
- [ ] Basic `start()` / `stop()` lifecycle
- [ ] Static layout matching schema (header, body split, footer)

**Success Criteria:**
- [ ] `from recursive_cleaner.tui import TUIRenderer, HAS_RICH` works
- [ ] `TUIRenderer` can be instantiated without Rich (no crash)
- [ ] With Rich: `start()` shows layout, `stop()` exits cleanly
- [ ] Layout has correct sections per data schema

**Tests:**
- [ ] test_tui_import_without_rich
- [ ] test_tui_renderer_lifecycle
- [ ] test_tui_layout_structure

## Phase 2: Dynamic Updates

**Deliverables:**
- [ ] `update_chunk()` updates progress bar and counters
- [ ] `update_llm_status()` shows/hides spinner
- [ ] `add_function()` appends to function list
- [ ] `update_metrics()` updates footer stats

**Success Criteria:**
- [ ] Progress bar fills based on chunk_index/total_chunks
- [ ] Spinner animates when status="calling", stops when "idle"
- [ ] Functions list grows, shows "+N more" when >5 functions
- [ ] Metrics panel shows formatted latency and counts

**Tests:**
- [ ] test_progress_updates
- [ ] test_spinner_states
- [ ] test_function_list_display
- [ ] test_metrics_display

## Phase 3: Integration & Polish

**Deliverables:**
- [ ] `tui=True` parameter on DataCleaner
- [ ] Integration: TUI updates from cleaner loop
- [ ] `show_complete()` with summary panel
- [ ] Fallback warning when Rich not installed
- [ ] Color transitions (yellow→green on chunk complete)

**Success Criteria:**
- [ ] Full cleaner run with `tui=True` shows live dashboard
- [ ] Completion shows summary with all stats
- [ ] `tui=True` without Rich logs warning, uses callbacks
- [ ] Chunk completion triggers green color flash

**Tests:**
- [ ] test_datacleaner_tui_integration
- [ ] test_tui_fallback_warning
- [ ] test_completion_summary
- [ ] test_color_transitions

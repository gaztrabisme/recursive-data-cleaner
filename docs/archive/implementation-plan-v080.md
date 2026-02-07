# Implementation Plan: Rich TUI (v0.8.0)

## Overview

Add optional Rich-based terminal dashboard for visual progress tracking during data cleaning runs.

## Technology Stack

| Layer | Choice | Rationale |
|-------|--------|-----------|
| TUI Library | Rich >=13.0 | Simple API, same author as Textual, 50KB |
| Pattern | Live + Layout | Mission control style, update sections independently |
| Fallback | Plain callbacks | Zero-dep baseline preserved |

## Phase Breakdown

### Phase 1: Core TUI Module

**Objective:** Create standalone TUI renderer with basic layout.

**Deliverables:**
- [ ] `recursive_cleaner/tui.py` (~150 lines)
- [ ] `tests/test_tui.py` (basic tests)
- [ ] `pyproject.toml` update for `[tui]` extra

**Implementation:**
```python
# tui.py structure
try:
    from rich.live import Live
    from rich.layout import Layout
    from rich.panel import Panel
    HAS_RICH = True
except ImportError:
    HAS_RICH = False

class TUIRenderer:
    def __init__(self, file_path, total_chunks, total_records):
        self._state = TUIState(...)
        self._layout = self._make_layout() if HAS_RICH else None
        self._live = None

    def _make_layout(self):
        layout = Layout()
        layout.split_column(
            Layout(name="header", size=3),
            Layout(name="body"),
            Layout(name="footer", size=3)
        )
        layout["body"].split_row(
            Layout(name="progress"),
            Layout(name="functions")
        )
        return layout

    def start(self):
        if not HAS_RICH:
            return
        self._live = Live(self._layout, refresh_per_second=2)
        self._live.start()

    def stop(self):
        if self._live:
            self._live.stop()
```

**Success Criteria:**
- Import works with/without Rich
- Layout renders with correct sections
- Start/stop lifecycle works

---

### Phase 2: Dynamic Updates

**Objective:** Wire up all state updates to visual components.

**Deliverables:**
- [ ] `update_chunk()` - progress bar + counters
- [ ] `update_llm_status()` - spinner control
- [ ] `add_function()` - function list panel
- [ ] `update_metrics()` - footer stats
- [ ] Additional tests for each update method

**Implementation:**
```python
def update_chunk(self, chunk_index, iteration, max_iterations):
    self._state.current_chunk = chunk_index
    self._state.current_iteration = iteration
    self._refresh_progress_panel()

def _refresh_progress_panel(self):
    progress = Progress(BarColumn(), TextColumn("{task.percentage:.0f}%"))
    task = progress.add_task("", total=self._state.total_chunks)
    progress.update(task, completed=self._state.current_chunk)

    content = Group(
        progress,
        Text(f"Chunk {self._state.current_chunk}/{self._state.total_chunks}"),
        Text(f"Iteration {self._state.current_iteration}/{self._state.max_iterations}"),
        self._make_spinner()
    )
    self._layout["progress"].update(Panel(content, title="Progress"))
```

**Success Criteria:**
- Progress bar animates smoothly
- Spinner shows during LLM calls
- Function list grows dynamically
- Metrics update in real-time

---

### Phase 3: Integration & Polish

**Objective:** Connect TUI to DataCleaner and add finishing touches.

**Deliverables:**
- [ ] `tui=True` parameter on DataCleaner.__init__
- [ ] TUI updates from main processing loop
- [ ] `show_complete()` summary panel
- [ ] Fallback warning via logging
- [ ] Color transitions on chunk completion
- [ ] Integration tests

**Implementation in cleaner.py:**
```python
def __init__(self, ..., tui: bool = False):
    self.tui = tui
    self._tui_renderer = None

def run(self):
    if self.tui:
        from recursive_cleaner.tui import TUIRenderer, HAS_RICH
        if HAS_RICH:
            self._tui_renderer = TUIRenderer(...)
            self._tui_renderer.start()
        else:
            import logging
            logging.warning("tui=True but Rich not installed. pip install recursive-cleaner[tui]")

    # ... existing loop with TUI updates injected ...

    if self._tui_renderer:
        self._tui_renderer.show_complete(summary)
        self._tui_renderer.stop()
```

**Success Criteria:**
- Full run with tui=True shows dashboard
- Fallback logs warning, uses callbacks
- Completion summary displays all stats
- Green flash on chunk completion

---

## Risk Register

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| Terminal size too small | Low | Medium | Use `vertical_overflow="crop"` |
| Rich version incompatibility | Low | Medium | Pin `>=13.0` (stable API) |
| Performance overhead | Low | Low | refresh_per_second=2 is fine |

## Out of Scope

- Keyboard interactivity (pause/resume)
- Mouse support
- Scrollable function list
- Custom themes
- Textual upgrade path

## File Changes Summary

| File | Change |
|------|--------|
| `recursive_cleaner/tui.py` | NEW (~200 lines) |
| `recursive_cleaner/cleaner.py` | Add `tui` param, TUI integration |
| `recursive_cleaner/__init__.py` | Export TUIRenderer, HAS_RICH |
| `pyproject.toml` | Add `[tui]` optional dependency |
| `tests/test_tui.py` | NEW (~15 tests) |
| `README.md` | Document TUI feature |

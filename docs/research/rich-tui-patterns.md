# Rich TUI Patterns Research

## Key APIs We'll Use

### 1. Live Display (`rich.live.Live`)
- Context manager for continuous updates
- `refresh_per_second=1` for our use case (not too noisy)
- `screen=True` for full-screen mode
- `transient=False` to preserve final state

### 2. Layout (`rich.layout.Layout`)
- Grid-based section management
- `split_column()` for vertical stacking
- `split_row()` for horizontal arrangement
- Create structure once, update content per cycle

### 3. Progress (`rich.progress.Progress`)
- `add_task()` returns task_id
- `update(task_id, advance=1)` or `update(task_id, completed=N)`
- Custom columns: `BarColumn`, `TextColumn`, `SpinnerColumn`

### 4. Panel (`rich.panel.Panel`)
- `Panel(content, title="Header")`
- `box` parameter for border style
- `expand=False` to fit content

### 5. Table (`rich.table.Table`)
- Dynamic rows with `add_row()`
- `header_style`, `border_style` for appearance

### 6. Spinner (`rich.spinner.Spinner`)
- 50+ styles: "dots", "line", "clock"
- Animates automatically within Live context

## Recommended Pattern

```python
def make_layout():
    layout = Layout()
    layout.split_column(
        Layout(name="header", size=3),
        Layout(name="body"),
        Layout(name="footer", size=3)
    )
    layout["body"].split_row(
        Layout(name="left"),
        Layout(name="right")
    )
    return layout

with Live(console=console, refresh_per_second=1) as live:
    layout = make_layout()  # Create once

    for chunk in chunks:
        # Update sections
        layout["header"].update(make_header())
        layout["left"].update(make_progress_panel())
        layout["right"].update(make_functions_table())
        layout["footer"].update(make_metrics())

        live.update(layout)
        process_chunk(chunk)
```

## Dashboard Layout for Data Cleaner

```
┌─────────────────────────────────────────────────────────┐
│  RECURSIVE DATA CLEANER                        v0.8.0   │
├────────────────────┬────────────────────────────────────┤
│  PROGRESS          │  FUNCTIONS GENERATED               │
│  [████████░░] 45%  │  ├─ normalize_phone_numbers        │
│  Chunk 45/100      │  ├─ fix_status_typos               │
│  Iteration 2/5     │  └─ standardize_dates              │
│                    │                                    │
│  ⠋ Calling LLM...  │  QUALITY: +23% improvement         │
├────────────────────┴────────────────────────────────────┤
│  ⏱️ 1.2s avg │ 45.2s total │ 12 LLM calls               │
└─────────────────────────────────────────────────────────┘
```

## Graceful Fallback

```python
try:
    from rich.live import Live
    from rich.panel import Panel
    HAS_RICH = True
except ImportError:
    HAS_RICH = False

class TUIRenderer:
    def __init__(self, enabled=True):
        self.enabled = enabled and HAS_RICH

    def render(self):
        if self.enabled:
            return self._rich_render()
        else:
            return self._plain_render()
```

## Gotchas

| Issue | Solution |
|-------|----------|
| Console output mixed with Live | Use `live.console.print()` |
| High CPU from frequent redraws | Lower `refresh_per_second` |
| Rich not installed | Check `HAS_RICH`, fallback to print |
| Terminal too small | Use `vertical_overflow="crop"` |

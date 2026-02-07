# API Contract: Rich TUI (v0.8.0)

## New Parameter

```python
DataCleaner(
    ...,
    tui: bool = False,  # Enable Rich terminal dashboard
)
```

## Behavior Matrix

| `tui` | Rich installed | Behavior |
|-------|----------------|----------|
| `False` | Any | Existing callback-based output (no change) |
| `True` | Yes | Live dashboard replaces callback prints |
| `True` | No | Warning logged, falls back to callbacks |

## New Optional Dependency

```toml
[project.optional-dependencies]
tui = ["rich>=13.0"]
```

```bash
pip install recursive-cleaner[tui]
```

## TUI Module API

### `recursive_cleaner/tui.py`

```python
# Check availability
HAS_RICH: bool

# Main renderer class
class TUIRenderer:
    def __init__(self, file_path: str, total_chunks: int, total_records: int)
    def start(self) -> None
    def stop(self) -> None
    def update_chunk(self, chunk_index: int, iteration: int, max_iterations: int) -> None
    def update_llm_status(self, status: str) -> None  # "calling" | "idle"
    def add_function(self, name: str, docstring: str) -> None
    def update_metrics(self, quality_delta: float, latency_last: float, latency_avg: float, latency_total: float, llm_calls: int) -> None
    def show_complete(self, summary: dict) -> None
```

## Integration with DataCleaner

When `tui=True` and Rich available:
1. `on_progress` callback still fires (for logging, state tracking)
2. TUI replaces console output, not callbacks
3. TUI auto-stops on completion or error

## No Breaking Changes

- All existing parameters unchanged
- All existing callbacks unchanged
- `tui=False` (default) = identical to v0.7.0 behavior

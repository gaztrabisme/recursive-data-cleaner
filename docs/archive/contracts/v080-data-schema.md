# Data Schema: TUI Display State (v0.8.0)

## Dashboard State

```python
@dataclass
class TUIState:
    # Header
    file_path: str
    total_records: int
    version: str = "0.8.0"

    # Progress
    current_chunk: int = 0
    total_chunks: int = 0
    current_iteration: int = 0
    max_iterations: int = 5

    # LLM Status
    llm_status: Literal["idle", "calling"] = "idle"

    # Functions
    functions: list[FunctionInfo] = field(default_factory=list)

    # Metrics
    quality_delta: float = 0.0  # Percentage improvement
    latency_last_ms: float = 0.0
    latency_avg_ms: float = 0.0
    latency_total_ms: float = 0.0
    llm_call_count: int = 0

@dataclass
class FunctionInfo:
    name: str
    docstring: str  # First 50 chars displayed
```

## Dashboard Layout Schema

```
┌─────────────────────────────────────────────────────────┐
│  {file_path}                              v{version}    │  <- HEADER (size=3)
├────────────────────┬────────────────────────────────────┤
│  PROGRESS          │  FUNCTIONS ({len(functions)})      │  <- BODY
│  [████░░░░░░] {%}  │  ├─ {functions[0].name}            │
│  Chunk {cur}/{tot} │  ├─ {functions[1].name}            │
│  Iter {i}/{max}    │  └─ {functions[2].name}            │
│                    │      (+{n} more)                   │
│  {spinner} {status}│  QUALITY: +{quality_delta}%        │
├────────────────────┴────────────────────────────────────┤
│  ⏱️ {latency_last}ms │ avg {latency_avg}ms │ {llm_calls} │  <- FOOTER (size=3)
└─────────────────────────────────────────────────────────┘
```

## Color Scheme

| Element | Color | Condition |
|---------|-------|-----------|
| Header title | cyan | Always |
| Progress bar | yellow | In progress |
| Progress bar | green | Chunk complete |
| Spinner | yellow | LLM calling |
| Function names | green | Always |
| Quality delta | green | Positive |
| Quality delta | red | Negative |
| Latency | dim white | Always |

## Spinner States

| `llm_status` | Display |
|--------------|---------|
| `"calling"` | Animated spinner + "Calling LLM..." |
| `"idle"` | Static checkmark or empty |

## Completion Summary

On `show_complete()`:

```
┌─────────────────────────────────────────────────────────┐
│  ✓ COMPLETE                                             │
├─────────────────────────────────────────────────────────┤
│  Functions generated: {n}                               │
│  Chunks processed: {total_chunks}                       │
│  Quality improvement: +{quality_delta}%                 │
│  Total time: {latency_total}ms ({llm_calls} LLM calls)  │
│                                                         │
│  Output: cleaning_functions.py                          │
└─────────────────────────────────────────────────────────┘
```

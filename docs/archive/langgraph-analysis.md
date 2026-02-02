# LangGraph Framework Analysis

**Date**: 2026-01-13  
**Purpose**: Evaluate LangGraph patterns for the Recursive Data Cleaning Pipeline project  
**Repository**: https://github.com/langchain-ai/langgraph

---

## Overview

LangGraph is a low-level orchestration framework for building stateful, long-running agents. Built by the LangChain team, it provides infrastructure for durable execution, human-in-the-loop workflows, and comprehensive state management.

### Core Philosophy
- **Graph-based execution**: Workflows are modeled as directed graphs where nodes are functions and edges define control flow
- **Persistence-first**: State can be checkpointed and resumed at any point, enabling fault tolerance and human intervention
- **Minimal abstraction**: Does not abstract away prompts or architecture decisions - provides infrastructure only
- **Inspired by**: Google's Pregel (distributed graph processing) and Apache Beam

### Key Capabilities
1. **Durable execution**: Automatic resume from failures
2. **Human-in-the-loop**: Pause/resume with state inspection
3. **Comprehensive memory**: Short-term (within run) and long-term (across sessions)
4. **Debugging/observability**: Via LangSmith integration

---

## Graph Architecture

### StateGraph - The Core Primitive

LangGraph uses a `StateGraph` class that defines:
1. **State Schema**: A TypedDict or Pydantic model defining the graph's state shape
2. **Nodes**: Functions that receive state and return updates
3. **Edges**: Define transitions between nodes (static or conditional)

```python
from langgraph.graph import START, StateGraph
from typing import TypedDict

class State(TypedDict):
    text: str
    issues_found: list[str]
    functions_generated: list[str]

def analyze_chunk(state: State) -> dict:
    # Analyze data, return updates
    return {"issues_found": ["issue1", "issue2"]}

def generate_function(state: State) -> dict:
    # Generate cleaning function
    return {"functions_generated": [...]}

graph = StateGraph(State)
graph.add_node("analyze", analyze_chunk)
graph.add_node("generate", generate_function)
graph.add_edge(START, "analyze")
graph.add_edge("analyze", "generate")
compiled = graph.compile()
```

### Pregel Execution Engine

Under the hood, LangGraph uses a Pregel-inspired execution model (`libs/langgraph/langgraph/pregel/`):

1. **Super-steps**: Graph executes in discrete steps where all eligible nodes run
2. **Channel-based communication**: State flows through "channels" between nodes
3. **Version tracking**: Each channel tracks versions for change detection
4. **Deterministic execution**: Same inputs produce same outputs (important for debugging)

Key files:
- `pregel/main.py`: Core `Pregel` class (~1200 lines)
- `pregel/_loop.py`: Main execution loop with checkpoint management
- `pregel/_algo.py`: Task scheduling and write application

### Conditional Branching

The `BranchSpec` class (`graph/_branch.py`) enables dynamic routing:

```python
def route_next(state: State) -> str:
    if all_issues_solved(state):
        return "finish"
    return "generate_more"

graph.add_conditional_edges(
    "analyze",
    route_next,
    {"finish": END, "generate_more": "generate"}
)
```

This is directly applicable to our "iterate until chunk is clean" requirement.

---

## State Management

### Channel Types

LangGraph uses "channels" for state fields (`libs/langgraph/langgraph/channels/`):

| Channel Type | Behavior | Use Case |
|-------------|----------|----------|
| `LastValue` | Keeps most recent value | Simple state fields |
| `BinaryOperatorAggregate` | Applies reducer function | Accumulating lists, counters |
| `EphemeralValue` | Resets each step | Temporary computation values |
| `Topic` | Pub/sub messaging | Event streams |

### State Reducers (Annotated Types)

The powerful `BinaryOperatorAggregate` channel enables accumulation:

```python
from typing import Annotated
import operator

class State(TypedDict):
    # Using operator.add as reducer - new values append to list
    functions: Annotated[list[str], operator.add]
    
    # Custom reducer for docstring registry
    docstrings: Annotated[dict[str, str], merge_docstrings]
```

**Key insight for our project**: Our docstring registry should use a custom reducer that merges new docstrings while preserving existing ones.

### Checkpointing System

The checkpoint system (`libs/checkpoint/`) provides:

1. **BaseCheckpointSaver**: Abstract interface for persistence
2. **InMemorySaver**: Development/testing (see `checkpoint/memory/__init__.py`)
3. **PostgresSaver**: Production persistence
4. **SQLiteSaver**: Local persistence

Checkpoint structure:
```python
class Checkpoint(TypedDict):
    v: int                          # Version
    id: str                         # Unique, monotonically increasing
    ts: str                         # ISO 8601 timestamp
    channel_values: dict[str, Any]  # Current state values
    channel_versions: ChannelVersions  # Version per channel
    versions_seen: dict[str, ChannelVersions]  # What each node has seen
```

---

## Applicable Concepts for Our Project

### 1. Iterative Refinement Loop

LangGraph's conditional edges with cycles perfectly match our "process chunk until clean" pattern:

```python
def should_continue(state: CleaningState) -> str:
    if state["chunk_status"] == "clean":
        return "next_chunk"
    if state["iteration_count"] >= MAX_ITERATIONS:
        return "next_chunk"
    return "generate_function"

graph.add_conditional_edges(
    "analyze_chunk",
    should_continue,
    {
        "next_chunk": "load_next_chunk",
        "generate_function": "generate_function"
    }
)
```

### 2. State Schema for Docstring Registry

```python
from typing import Annotated, TypedDict
from dataclasses import dataclass

def merge_registry(existing: dict, new: dict) -> dict:
    """Merge new functions into registry, preserving existing."""
    merged = existing.copy()
    merged.update(new)
    return merged

class CleaningState(TypedDict):
    # Current chunk being processed
    current_chunk: str
    chunk_index: int
    
    # Accumulated registry (grows over time)
    docstring_registry: Annotated[dict[str, str], merge_registry]
    generated_functions: Annotated[list[str], operator.add]
    
    # Per-chunk tracking (resets)
    issues_detected: list[dict]
    iteration_count: int
    chunk_status: str  # "clean" | "needs_work"
```

### 3. Retry Policy

LangGraph's `RetryPolicy` (`types.py` and `pregel/_retry.py`) is directly applicable:

```python
from langgraph.types import RetryPolicy

# Retry on LLM errors with exponential backoff
retry_policy = RetryPolicy(
    initial_interval=0.5,
    backoff_factor=2.0,
    max_interval=30.0,
    max_attempts=3,
    jitter=True,
    retry_on=lambda e: isinstance(e, (TimeoutError, RateLimitError))
)
```

The implementation in `_retry.py` shows:
- Configurable exception matching
- Exponential backoff with jitter
- Attempt counting with configurable limits
- Clean separation of sync/async versions

### 4. Interrupt and Resume

The `interrupt()` function (`types.py`) enables human-in-the-loop:

```python
from langgraph.types import interrupt, Command

def validate_function(state: CleaningState):
    """Optionally pause for human review."""
    if state["needs_review"]:
        answer = interrupt({
            "function": state["latest_function"],
            "question": "Approve this cleaning function?"
        })
        if answer == "reject":
            return {"regenerate": True}
    return {}
```

### 5. Error Handling Patterns

LangGraph uses exception hierarchy for control flow:
- `GraphBubbleUp`: Base for control exceptions
- `GraphInterrupt`: Pause execution (human-in-the-loop)
- `GraphRecursionError`: Hit max steps (our max_iterations analog)
- `InvalidUpdateError`: Bad state updates

This pattern of using exceptions for non-error control flow is clean and avoids sentinel values.

---

## Code Examples

### Example 1: Chunk Processing Graph

```python
from langgraph.graph import START, END, StateGraph
from langgraph.checkpoint.memory import InMemorySaver
from typing import Annotated, TypedDict
import operator

class CleaningState(TypedDict):
    file_path: str
    chunks: list[str]
    current_chunk_idx: int
    docstring_registry: Annotated[dict[str, str], lambda a, b: {**a, **b}]
    generated_code: Annotated[list[str], operator.add]
    iteration_count: int
    chunk_status: str

def load_chunk(state: CleaningState) -> dict:
    idx = state["current_chunk_idx"]
    return {
        "current_chunk": state["chunks"][idx],
        "iteration_count": 0,
        "chunk_status": "needs_work"
    }

def analyze_chunk(state: CleaningState) -> dict:
    # Call LLM with docstring_registry context
    response = llm.generate(
        prompt_with_registry(state["current_chunk"], state["docstring_registry"])
    )
    return parse_analysis(response)

def generate_function(state: CleaningState) -> dict:
    # Generate one function for first unsolved issue
    response = llm.generate(generate_prompt(state))
    func_code, docstring = parse_function(response)
    return {
        "generated_code": [func_code],
        "docstring_registry": {extract_name(func_code): docstring},
        "iteration_count": state["iteration_count"] + 1
    }

def should_continue(state: CleaningState) -> str:
    if state["chunk_status"] == "clean":
        return "advance"
    if state["iteration_count"] >= 5:
        return "advance"
    return "generate"

def advance_chunk(state: CleaningState) -> dict:
    new_idx = state["current_chunk_idx"] + 1
    if new_idx >= len(state["chunks"]):
        return {"finished": True}
    return {"current_chunk_idx": new_idx}

# Build graph
builder = StateGraph(CleaningState)
builder.add_node("load", load_chunk)
builder.add_node("analyze", analyze_chunk)
builder.add_node("generate", generate_function)
builder.add_node("advance", advance_chunk)

builder.add_edge(START, "load")
builder.add_edge("load", "analyze")
builder.add_conditional_edges("analyze", should_continue, {
    "generate": "generate",
    "advance": "advance"
})
builder.add_edge("generate", "analyze")  # Loop back
builder.add_conditional_edges("advance", 
    lambda s: END if s.get("finished") else "load",
    {END: END, "load": "load"}
)

# Compile with checkpointing
graph = builder.compile(checkpointer=InMemorySaver())
```

### Example 2: Custom Reducer for Docstring Registry

```python
def docstring_registry_reducer(
    current: dict[str, str], 
    new: dict[str, str]
) -> dict[str, str]:
    """
    Merge new docstrings into registry.
    
    - Preserves existing entries
    - Adds new entries
    - If function name collision, keeps newer (assumes improvement)
    """
    result = current.copy()
    for func_name, docstring in new.items():
        result[func_name] = docstring
    return result

class State(TypedDict):
    docstring_registry: Annotated[
        dict[str, str], 
        docstring_registry_reducer
    ]
```

### Example 3: Retry with Backoff

From `pregel/_retry.py`, simplified for our use:

```python
import time
import random
from dataclasses import dataclass

@dataclass
class RetryConfig:
    max_attempts: int = 3
    initial_interval: float = 0.5
    backoff_factor: float = 2.0
    max_interval: float = 30.0
    jitter: bool = True

def with_retry(func, config: RetryConfig):
    """Decorator for retry with exponential backoff."""
    def wrapper(*args, **kwargs):
        attempts = 0
        while True:
            try:
                return func(*args, **kwargs)
            except Exception as e:
                attempts += 1
                if attempts >= config.max_attempts:
                    raise
                
                interval = min(
                    config.max_interval,
                    config.initial_interval * (config.backoff_factor ** (attempts - 1))
                )
                if config.jitter:
                    interval += random.uniform(0, 1)
                
                time.sleep(interval)
    return wrapper
```

---

## Verdict: Build On vs. Borrow Patterns

### Recommendation: Borrow Patterns, Don't Build On

**Reasons NOT to build directly on LangGraph:**

1. **Dependency weight**: LangGraph pulls in `langchain-core` which brings significant dependencies. Our goal is a lightweight, focused library.

2. **Abstraction mismatch**: LangGraph is designed for conversational agents with tool use. Our pipeline is simpler: sequential chunk processing with accumulation.

3. **Complexity overhead**: The Pregel engine is powerful but overkill for our use case. We don't need:
   - Parallel node execution
   - Sub-graph composition
   - Dynamic task spawning (Send)
   - Complex namespace management

4. **User experience**: We want users to provide a simple LLM backend interface. LangGraph's integration with LangChain models adds friction.

**Patterns Worth Borrowing:**

| Pattern | LangGraph Location | Our Application |
|---------|-------------------|-----------------|
| State reducers | `channels/binop.py` | Docstring registry accumulation |
| Retry policy | `pregel/_retry.py`, `types.py` | LLM call retries |
| Checkpoint structure | `checkpoint/base/__init__.py` | Progress persistence |
| Conditional routing | `graph/_branch.py` | "Clean or continue" decision |
| Exception-based control | `errors.py` | Max iteration limits |
| TypedDict state | `graph/state.py` | Type-safe pipeline state |

### Implementation Approach

1. **Define typed state** using TypedDict with annotations for reducers
2. **Implement simple loop** instead of graph engine:
   ```python
   while chunk_index < total_chunks:
       state = process_chunk(state)  # Returns updated state
       if should_save_checkpoint(state):
           save_checkpoint(state)
   ```
3. **Borrow retry logic** from `_retry.py` verbatim (it's clean and well-tested)
4. **Use reducer pattern** for docstring registry accumulation
5. **Add optional checkpointing** with similar interface to `BaseCheckpointSaver`

### Concrete Takeaways

1. **State definition pattern**:
   ```python
   from typing import Annotated, TypedDict
   
   class PipelineState(TypedDict):
       # Accumulated across all chunks
       docstring_registry: Annotated[dict[str, str], merge_dicts]
       generated_functions: Annotated[list[str], operator.add]
       
       # Current chunk context
       current_chunk: str
       chunk_index: int
       iteration: int
   ```

2. **Reducer interface**:
   ```python
   Reducer = Callable[[T, T], T]  # (current, new) -> merged
   ```

3. **Checkpoint-like interface**:
   ```python
   class CheckpointSaver(Protocol):
       def save(self, state: PipelineState, step: int) -> None: ...
       def load(self, step: int | None = None) -> PipelineState | None: ...
       def list_steps(self) -> list[int]: ...
   ```

4. **Retry configuration** (copy from LangGraph):
   ```python
   @dataclass
   class RetryPolicy:
       initial_interval: float = 0.5
       backoff_factor: float = 2.0
       max_interval: float = 30.0
       max_attempts: int = 3
       jitter: bool = True
   ```

---

## Summary

LangGraph provides excellent patterns for stateful agent execution, but its full framework is overkill for our data cleaning pipeline. We should:

1. **Adopt**: TypedDict state, reducer pattern, retry logic, checkpoint interface
2. **Skip**: Graph engine, Pregel execution, LangChain integration, sub-graphs
3. **Simplify**: Use a straightforward loop instead of graph traversal

The key insight is that LangGraph solves a superset of our problems. We can cherry-pick the state management and retry patterns while avoiding the complexity of the full graph execution engine.

---

## References

- `libs/langgraph/langgraph/graph/state.py` - StateGraph implementation
- `libs/langgraph/langgraph/channels/binop.py` - Reducer pattern
- `libs/langgraph/langgraph/pregel/_retry.py` - Retry logic
- `libs/checkpoint/langgraph/checkpoint/base/__init__.py` - Checkpoint interface
- `libs/langgraph/langgraph/types.py` - RetryPolicy, Interrupt definitions

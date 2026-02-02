# LLM Agent Framework Analysis

This document analyzes three popular LLM agent frameworks to identify patterns and approaches that could benefit our Recursive Data Cleaning Pipeline project.

## Executive Summary

Our project generates Python data cleaning functions incrementally using LLMs, with docstrings as memory between iterations. After examining Microsoft AutoGen, CrewAI, and Pydantic AI, the most relevant patterns for our use case are:

1. **Pydantic AI's type-safe output validation** - Directly applicable to our XML parsing and code validation
2. **CrewAI's guardrail system** - Maps well to our chunk iteration validation
3. **AutoGen's memory abstraction** - Could enhance our docstring registry pattern

---

## Framework Overviews

### 1. Microsoft AutoGen

**Repository**: `docs/frameworks/autogen/`

**Core Philosophy**: Multi-agent orchestration framework with message-passing architecture. Designed for complex, distributed agent systems.

**Architecture Highlights**:
- **Layered design**: Core API (low-level) → AgentChat API (high-level) → Extensions API
- **Event-driven agents** with pub/sub messaging patterns
- **Runtime abstraction** supporting both local and distributed execution
- **Strong typing** with Protocol-based interfaces

**Key Components**:
```python
# Base agent pattern from autogen_core/_base_agent.py
class BaseAgent(ABC, Agent):
    async def on_message_impl(self, message: Any, ctx: MessageContext) -> Any: ...
    async def save_state(self) -> Mapping[str, Any]: ...
    async def load_state(self, state: Mapping[str, Any]) -> None: ...
```

**Memory System** (`autogen_core/memory/`):
- Abstract `Memory` base class with `query()`, `add()`, `update_context()` methods
- `MemoryContent` dataclass for typed memory items with MIME types
- Designed for RAG-style retrieval integration

**Error Handling**:
- Cancellation token pattern for async operation control
- Retry logic built into message handling
- Serialization-aware error recovery

---

### 2. CrewAI

**Repository**: `docs/frameworks/crewAI/`

**Core Philosophy**: Role-based agent collaboration with emphasis on autonomous task execution. Optimized for "Crews" of specialized agents.

**Architecture Highlights**:
- **Pydantic-based models** throughout (agents, tasks, crews)
- **Task-centric workflow** - explicit task definitions with expected outputs
- **Multiple memory types**: Short-term, Long-term, Entity memory
- **Event bus** for decoupled component communication

**Key Components**:
```python
# Task definition pattern from crewai/task.py
class Task(BaseModel):
    description: str
    expected_output: str
    agent: BaseAgent | None
    output_json: type[BaseModel] | None  # Structured output
    output_pydantic: type[BaseModel] | None
    guardrail: GuardrailType | None  # Validation
    guardrail_max_retries: int = 3
```

**Guardrail System** (`crewai/utilities/guardrail.py`):
```python
class GuardrailResult(BaseModel):
    success: bool
    result: Any | None
    error: str | None

def process_guardrail(output, guardrail, retry_count, ...) -> GuardrailResult:
    """Validate task output with retry support"""
```

**Memory System** (`crewai/memory/`):
- `ShortTermMemory`: RAG-based storage for current session
- `LongTermMemory`: Persistent across sessions
- `EntityMemory`: Track entities mentioned in conversations
- Event-driven save/search with timing metrics

---

### 3. Pydantic AI

**Repository**: `docs/frameworks/pydantic-ai/`

**Core Philosophy**: Type-safe, validation-first agent framework. Brings "FastAPI feeling" to LLM development.

**Architecture Highlights**:
- **Graph-based execution** with explicit state machines
- **Multiple output modes**: Text, Tool (structured), Native (provider-specific), Prompted
- **Dependency injection** pattern for tool functions
- **Comprehensive retry system** with tenacity integration

**Key Components**:
```python
# Output validation pattern from pydantic_ai/_output.py
@dataclass
class OutputValidator(Generic[AgentDepsT, OutputDataT_inv]):
    function: OutputValidatorFunc[AgentDepsT, OutputDataT_inv]
    
    async def validate(self, result, run_context, wrap_validation_errors=True):
        """Validate result, optionally wrap errors for retry"""
```

**Structured Output System** (`pydantic_ai/output.py`):
```python
class ToolOutput(Generic[OutputDataT]):
    """Marker for tool-based structured output"""
    output: OutputTypeOrFunction[OutputDataT]
    name: str | None
    description: str | None
    max_retries: int | None
    strict: bool | None

class NativeOutput(Generic[OutputDataT]):
    """Uses model's native structured output"""
    
class PromptedOutput(Generic[OutputDataT]):
    """Extract structure via prompting"""
```

**Exception Hierarchy** (`pydantic_ai/exceptions.py`):
```python
class ModelRetry(Exception):
    """Signal to retry with message to model"""
    message: str

class UserError(RuntimeError):
    """Developer usage mistake"""

class AgentRunError(RuntimeError):
    """Base for runtime errors"""

class UsageLimitExceeded(AgentRunError): ...
class UnexpectedModelBehavior(AgentRunError): ...
```

---

## Feature Comparison Table

| Feature | AutoGen | CrewAI | Pydantic AI | Our Project Needs |
|---------|---------|--------|-------------|-------------------|
| **Structured Output** | Protocol-based | Pydantic models | Multiple modes (Tool/Native/Prompted) | XML → Python extraction |
| **Output Validation** | Manual | Guardrails with retries | Type-validated with ModelRetry | Function syntax validation |
| **Memory/State** | Abstract Memory class | Short/Long/Entity memory | Run context + message history | Docstring registry |
| **Error Recovery** | Cancellation tokens | Retry with max count | Tenacity + ModelRetry exceptions | Max iterations per chunk |
| **Iteration Control** | Message-based | Task-level | Graph nodes with End states | Chunk "clean" status |
| **LLM Abstraction** | Model clients | LLM class wrapper | Provider-agnostic models | User-provided backend |
| **Type Safety** | Protocols + generics | Pydantic models | Full generic typing | Not prioritized |
| **Async Support** | First-class async | Async + sync | Async with sync wrappers | Sync preferred |

---

## Key Patterns We Could Adopt

### 1. Pydantic AI's Output Validation Pattern

**Current approach**: We parse XML responses manually and validate Python syntax.

**Recommended pattern**:
```python
from dataclasses import dataclass
from typing import Callable, Awaitable

@dataclass
class CleaningFunctionValidator:
    """Validates generated cleaning functions"""
    
    def __init__(self):
        self._validators: list[Callable] = [
            self._check_syntax,
            self._check_has_docstring,
            self._check_is_idempotent_hint,
        ]
    
    def validate(self, code: str) -> tuple[bool, str | None]:
        """Returns (is_valid, error_message)"""
        for validator in self._validators:
            result = validator(code)
            if not result.success:
                return False, result.error
        return True, None
```

**Why**: Separates validation logic, enables retry with specific error messages.

### 2. CrewAI's Guardrail System

**Current approach**: Check `<chunk_status>clean</chunk_status>` and iteration count.

**Recommended pattern**:
```python
@dataclass
class ChunkGuardrail:
    """Validates chunk processing results"""
    max_retries: int = 5
    
    def check(self, chunk_result: ChunkProcessingResult) -> GuardrailResult:
        if chunk_result.status == "clean":
            return GuardrailResult(success=True, result=chunk_result)
        
        if chunk_result.iteration >= self.max_retries:
            return GuardrailResult(
                success=False, 
                error=f"Max iterations ({self.max_retries}) reached for chunk"
            )
        
        # Check for valid function generation
        if chunk_result.function_code:
            syntax_ok, error = self.validate_syntax(chunk_result.function_code)
            if not syntax_ok:
                return GuardrailResult(success=False, error=error)
        
        return GuardrailResult(success=True, result=chunk_result)
```

**Why**: Centralizes validation logic, provides clear retry semantics.

### 3. AutoGen's Memory Interface Pattern

**Current approach**: Docstring registry is a dict/list of strings.

**Recommended pattern**:
```python
from abc import ABC, abstractmethod
from dataclasses import dataclass

@dataclass
class FunctionMemoryItem:
    name: str
    docstring: str
    code: str
    issues_solved: list[str]
    created_at: datetime

class FunctionRegistry(ABC):
    """Abstract interface for function memory"""
    
    @abstractmethod
    def add(self, item: FunctionMemoryItem) -> None: ...
    
    @abstractmethod
    def get_docstrings_for_prompt(self, max_items: int = 30) -> str: ...
    
    @abstractmethod
    def check_issue_solved(self, issue_description: str) -> bool: ...
    
    @abstractmethod
    def get_all_functions(self) -> list[FunctionMemoryItem]: ...
```

**Why**: Enables future enhancements (similarity search, persistence) without changing core logic.

### 4. Pydantic AI's Exception Hierarchy

**Current approach**: Not specified in CLAUDE.md.

**Recommended pattern**:
```python
class DataCleanerError(Exception):
    """Base exception for the pipeline"""
    message: str

class XMLParseError(DataCleanerError):
    """LLM response XML was malformed"""

class CodeGenerationError(DataCleanerError):
    """Generated Python code is invalid"""
    code: str
    syntax_error: str

class RetryableError(DataCleanerError):
    """Error that should trigger a retry with feedback"""
    retry_message: str  # Message to send back to LLM

class ChunkProcessingError(DataCleanerError):
    """Failed to process a chunk after max retries"""
    chunk_index: int
    attempts: int
```

**Why**: Clear error categorization enables appropriate handling (retry vs skip vs fail).

---

## Implementation Recommendations

### Priority 1: Adopt for Initial Implementation

1. **Exception hierarchy** (Pydantic AI pattern)
   - Low effort, high impact on error handling clarity
   - Enables "retry with feedback" pattern from CLAUDE.md

2. **Output validator pattern** (Pydantic AI pattern)
   - Separates XML parsing from validation
   - Makes validation rules explicit and testable

### Priority 2: Consider for v1.1

1. **Guardrail system** (CrewAI pattern)
   - Would clean up the chunk iteration loop
   - Good abstraction for "is this chunk done?" logic

2. **Memory interface** (AutoGen pattern)
   - Future-proofs docstring registry
   - Enables vector search for "is this issue already solved?"

### Priority 3: Future Considerations

1. **Type-safe generics** (Pydantic AI pattern)
   - Would improve IDE experience
   - Adds complexity for unclear benefit given our use case

2. **Event bus** (CrewAI pattern)
   - Useful if we add progress callbacks
   - Overkill for current scope

---

## Patterns to Avoid

1. **Multi-agent orchestration** (AutoGen's core feature)
   - Our pipeline is single-agent by design
   - Would add unnecessary complexity

2. **Native structured output** (Pydantic AI's NativeOutput)
   - We specifically chose XML to avoid JSON escaping issues
   - Provider-specific features reduce portability

3. **Distributed runtime** (AutoGen)
   - Single-threaded is a non-goal for our project
   - Simplicity over performance

---

## Conclusion

The three frameworks offer different value propositions:

- **AutoGen**: Best for complex multi-agent systems with distributed needs
- **CrewAI**: Best for role-based autonomous agent teams
- **Pydantic AI**: Best for type-safe, single-agent workflows with structured output

For our Recursive Data Cleaning Pipeline, **Pydantic AI's patterns are most applicable** due to:
1. Focus on structured output validation
2. Clean exception hierarchy for retry logic
3. Straightforward single-agent model

However, **CrewAI's guardrail pattern** and **AutoGen's memory abstraction** offer complementary value worth incorporating.

---

## Appendix: Source Files Examined

### AutoGen
- `python/packages/autogen-core/src/autogen_core/_base_agent.py`
- `python/packages/autogen-core/src/autogen_core/memory/_base_memory.py`
- `python/packages/autogen-core/src/autogen_core/tools/_base.py`

### CrewAI
- `lib/crewai/src/crewai/crew.py`
- `lib/crewai/src/crewai/task.py`
- `lib/crewai/src/crewai/agents/agent_builder/base_agent.py`
- `lib/crewai/src/crewai/memory/short_term/short_term_memory.py`
- `lib/crewai/src/crewai/utilities/guardrail.py`

### Pydantic AI
- `pydantic_ai_slim/pydantic_ai/_output.py`
- `pydantic_ai_slim/pydantic_ai/result.py`
- `pydantic_ai_slim/pydantic_ai/retries.py`
- `pydantic_ai_slim/pydantic_ai/exceptions.py`
- `pydantic_ai_slim/pydantic_ai/output.py`
- `pydantic_ai_slim/pydantic_ai/run.py`

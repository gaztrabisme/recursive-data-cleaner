# LangChain Framework Analysis

**Analysis Date**: 2026-01-13  
**Purpose**: Evaluate LangChain patterns for the Recursive Data Cleaning Pipeline project  
**LangChain Version**: Current (cloned from main branch)

---

## Overview

### What is LangChain?

LangChain is a Python framework for building applications powered by Large Language Models (LLMs). It provides:

1. **Composable abstractions** - A "Runnable" interface that allows chaining operations with the `|` operator
2. **Provider-agnostic design** - Abstractions for LLMs, embeddings, vector stores, etc.
3. **Built-in utilities** - Memory systems, output parsers, callback handlers, retry logic
4. **Agent framework** - Tools for building autonomous agents that can use tools

### Core Philosophy

LangChain follows a "Runnable" paradigm where everything is composable:

```python
# Everything is a Runnable with invoke/ainvoke, batch/abatch, stream/astream
chain = prompt | llm | output_parser

# Chains compose naturally
result = chain.invoke({"input": "hello"})
```

Key design principles:
- **Composability over inheritance** - Use the `|` operator to chain components
- **Async-first** - Every method has an async counterpart
- **Observable** - Callbacks/tracers for debugging and monitoring
- **Serializable** - Components can be saved/loaded

---

## Architecture Patterns

### 1. The Runnable Interface

The core abstraction in LangChain is `Runnable[Input, Output]`. Key methods:

```python
class Runnable(ABC, Generic[Input, Output]):
    def invoke(self, input: Input, config: RunnableConfig | None = None) -> Output
    async def ainvoke(self, input: Input, config: RunnableConfig | None = None) -> Output
    def batch(self, inputs: list[Input], ...) -> list[Output]
    def stream(self, input: Input, ...) -> Iterator[Output]
    
    # Composition
    def __or__(self, other: Runnable) -> RunnableSequence  # chain1 | chain2
    def with_retry(...) -> RunnableRetry
    def with_fallbacks(...) -> RunnableWithFallbacks
```

**Relevance to our project**: This pattern is elegant but may be overkill for our simpler pipeline. However, the `with_retry()` and `with_fallbacks()` patterns are directly applicable.

### 2. RunnableSequence - Chain Composition

Chains are built by piping Runnables together:

```python
from langchain_core.runnables import RunnableLambda

chain = (
    RunnableLambda(lambda x: x + 1) |
    RunnableLambda(lambda x: x * 2)
)
chain.invoke(1)  # Returns 4
```

**Relevance**: Our pipeline has a simpler linear flow (chunk -> analyze -> generate -> validate -> repeat). We don't need full composability but can borrow the pattern for our internal steps.

### 3. RunnableParallel - Concurrent Execution

For parallel operations:

```python
chain = RunnableLambda(lambda x: x + 1) | {
    "doubled": RunnableLambda(lambda x: x * 2),
    "squared": RunnableLambda(lambda x: x ** 2),
}
chain.invoke(1)  # {'doubled': 4, 'squared': 4}
```

**Relevance**: Limited for our use case since chunk processing is sequential by design (docstrings from previous chunks inform future ones).

---

## Memory Systems

LangChain's memory implementations are particularly relevant to our docstring registry approach.

### 1. ConversationBufferMemory

Simplest memory - stores everything:

```python
class ConversationBufferMemory(BaseChatMemory):
    def load_memory_variables(self, inputs: dict) -> dict:
        return {self.memory_key: self.buffer}
    
    def save_context(self, inputs: dict, outputs: dict) -> None:
        # Append to buffer
```

**Limitation**: Unbounded growth. Context window will eventually overflow.

### 2. ConversationTokenBufferMemory

Maintains a sliding window based on token count:

```python
class ConversationTokenBufferMemory(BaseChatMemory):
    max_token_limit: int = 2000
    
    def save_context(self, inputs, outputs):
        super().save_context(inputs, outputs)
        # Prune oldest messages until under token limit
        buffer = self.chat_memory.messages
        while self.llm.get_num_tokens_from_messages(buffer) > self.max_token_limit:
            buffer.pop(0)
```

**Relevance**: Direct inspiration for our docstring registry. We should:
- Track total tokens in docstring registry
- Remove oldest docstrings when limit exceeded
- Consider keeping a "summary" of removed docstrings

### 3. ConversationSummaryBufferMemory (Most Relevant)

Hybrid approach - summarizes old content, keeps recent content verbatim:

```python
class ConversationSummaryBufferMemory(BaseChatMemory, SummarizerMixin):
    max_token_limit: int = 2000
    moving_summary_buffer: str = ""
    
    def prune(self) -> None:
        buffer = self.chat_memory.messages
        curr_length = self.llm.get_num_tokens_from_messages(buffer)
        
        if curr_length > self.max_token_limit:
            pruned_memory = []
            while curr_length > self.max_token_limit:
                pruned_memory.append(buffer.pop(0))
                curr_length = self.llm.get_num_tokens_from_messages(buffer)
            
            # Summarize what was removed
            self.moving_summary_buffer = self.predict_new_summary(
                pruned_memory,
                self.moving_summary_buffer,
            )
```

**Key Insight for Our Project**: Instead of just dropping old docstrings, we could:
1. Summarize removed functions: "Previously generated: normalize_phone(), fix_dates(), remove_nulls() - handling phone formatting, date conversion, null value removal"
2. Keep recent N docstrings in full detail
3. Include summary of older functions in prompt

### 4. VectorStoreRetrieverMemory

Stores memories in a vector store, retrieves relevant ones based on current input:

```python
class VectorStoreRetrieverMemory(BaseMemory):
    retriever: VectorStoreRetriever
    
    def load_memory_variables(self, inputs):
        query = inputs[self.input_key]
        docs = self.retriever.invoke(query)  # Semantic search
        return {self.memory_key: docs}
```

**Relevance**: For large docstring registries (50+ functions), we could:
- Embed each docstring
- On each chunk, retrieve only the most semantically relevant docstrings
- This prevents context overflow while maintaining relevant context

---

## Output Parsers and Structured Output

### 1. XMLOutputParser

LangChain has a streaming XML parser that handles partial/malformed XML:

```python
class XMLOutputParser(BaseTransformOutputParser):
    tags: list[str] | None = None
    parser: Literal["defusedxml", "xml"] = "defusedxml"
    
    def parse(self, text: str) -> dict:
        # Uses streaming parser that handles partial XML
        # Can recover from junk at end of output
```

**Key Features**:
- Streaming support for real-time parsing
- Graceful handling of incomplete XML
- Security via `defusedxml` library
- Regular expression to find XML start (`<[a-zA-Z:_]`)

**Relevance**: We should adopt similar patterns:
- Use `defusedxml` for safety
- Implement streaming-friendly parsing
- Handle partial/malformed XML gracefully

### 2. OutputFixingParser - LLM-Powered Error Recovery

Wraps any parser and uses an LLM to fix parsing errors:

```python
class OutputFixingParser(BaseOutputParser[T]):
    parser: BaseOutputParser[T]
    retry_chain: RunnableSerializable  # prompt | llm | StrOutputParser
    max_retries: int = 1
    
    def parse(self, completion: str) -> T:
        retries = 0
        while retries <= self.max_retries:
            try:
                return self.parser.parse(completion)
            except OutputParserException as e:
                retries += 1
                # Ask LLM to fix the output
                completion = self.retry_chain.invoke({
                    "instructions": self.parser.get_format_instructions(),
                    "completion": completion,
                    "error": repr(e),
                })
        raise OutputParserException("Failed to parse")
```

**The fix prompt template**:
```
Instructions:
{instructions}

Completion:
{completion}

Above, the Completion did not satisfy the constraints.
Error: {error}
Please try again:
```

**Relevance**: Directly applicable. Our XML parser should:
1. Attempt to parse
2. On failure, call LLM with: "Your output was malformed. Error: {error}. Please regenerate in correct XML format."
3. Retry up to N times

### 3. RetryOutputParser - Retry Without Error Details

Similar to OutputFixingParser but doesn't include error details:

```python
NAIVE_COMPLETION_RETRY = """Prompt:
{prompt}
Completion:
{completion}

Above, the Completion did not satisfy the constraints given in the Prompt.
Please try again:"""
```

**Trade-off**: Simpler prompt but LLM has less context to fix the issue.

---

## Error Handling, Retries, and Fallbacks

### 1. RunnableRetry

Built-in retry logic with exponential backoff and jitter:

```python
class RunnableRetry(RunnableBindingBase[Input, Output]):
    retry_exception_types: tuple[type[BaseException], ...] = (Exception,)
    wait_exponential_jitter: bool = True
    exponential_jitter_params: ExponentialJitterParams | None = None
    max_attempt_number: int = 3
    
    def _invoke(self, input_, run_manager, config, **kwargs) -> Output:
        for attempt in self._sync_retrying(reraise=True):
            with attempt:
                result = super().invoke(input_, ...)
            if not attempt.retry_state.outcome.failed:
                attempt.retry_state.set_result(result)
        return result
```

Uses the `tenacity` library under the hood:
```python
from tenacity import (
    AsyncRetrying, Retrying,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential_jitter,
)
```

**Usage Pattern**:
```python
runnable.with_retry(
    retry_if_exception_type=(ValueError, ConnectionError),
    stop_after_attempt=3,
    wait_exponential_jitter=True,
    exponential_jitter_params={"initial": 1.0, "max": 10.0}
)
```

**Relevance**: We should use `tenacity` directly in our project for:
- LLM API retries (rate limits, transient errors)
- XML parsing retries
- Code validation retries

### 2. RunnableWithFallbacks

Chain of fallbacks when primary runnable fails:

```python
class RunnableWithFallbacks(RunnableSerializable[Input, Output]):
    runnable: Runnable[Input, Output]
    fallbacks: Sequence[Runnable[Input, Output]]
    exceptions_to_handle: tuple[type[BaseException], ...] = (Exception,)
    exception_key: str | None = None  # Pass exception to fallback
    
    def invoke(self, input, config=None, **kwargs) -> Output:
        for runnable in [self.runnable, *self.fallbacks]:
            try:
                if self.exception_key and last_error:
                    input[self.exception_key] = last_error
                return runnable.invoke(input, config, **kwargs)
            except self.exceptions_to_handle as e:
                last_error = e
        raise last_error
```

**Usage**:
```python
chain = (
    prompt | primary_llm | parser
).with_fallbacks([
    prompt | fallback_llm | parser,
    RunnableLambda(lambda x: default_response)
])
```

**Relevance**: For our project, we could have:
1. Primary: Preferred LLM backend
2. Fallback 1: Alternative LLM 
3. Fallback 2: Skip chunk and log warning

---

## Tool/Function Calling Abstractions

### BaseTool Interface

```python
class BaseTool(ABC):
    name: str
    description: str
    
    @abstractmethod
    def _run(self, *args, **kwargs) -> Any: ...
    
    async def _arun(self, *args, **kwargs) -> Any: ...
    
    def invoke(self, input, config=None) -> Any:
        return self._run(input)
```

### StructuredTool - From Function

```python
@tool
def search(query: str) -> str:
    """Search for information."""
    return search_api(query)

# Creates a StructuredTool with:
# - name: "search"  
# - description: "Search for information."
# - args_schema: inferred from type hints
```

**Relevance**: Limited for our use case. We're not building an agent with tools; we're generating cleaning functions.

---

## Applicable Concepts

### High Priority - Should Adopt

1. **Retry with Tenacity**
   - Use `tenacity` library for exponential backoff
   - Apply to: LLM calls, XML parsing, code validation

2. **Output Fixing Pattern**
   - On parse failure, send error back to LLM with: "Your output was invalid: {error}. Please fix."
   - Max 3 retries before giving up on chunk

3. **Summary Buffer Memory Pattern**
   - When docstring registry exceeds token limit:
     - Summarize oldest N docstrings into a brief description
     - Keep recent M docstrings in full
   - Prevents context overflow while maintaining awareness

4. **Structured Exceptions**
   - Create `CleaningPipelineException` hierarchy
   - `OutputParserException` - XML parsing failed
   - `CodeValidationException` - Generated code invalid
   - `ChunkProcessingException` - Chunk couldn't be cleaned

5. **Callback/Tracing Pattern**
   - Simple callbacks for logging: `on_chunk_start`, `on_function_generated`, `on_error`
   - Enables progress tracking without tight coupling

### Medium Priority - Consider

6. **Vector Store Memory**
   - For 50+ generated functions, embed docstrings
   - Retrieve top-K relevant docstrings per chunk
   - Requires vector store dependency (e.g., FAISS, ChromaDB)

7. **Fallback Chain**
   - Primary LLM fails -> try alternative LLM
   - All LLMs fail -> skip chunk with warning
   - Useful for production resilience

### Low Priority - Skip

8. **Full Runnable Composition** - Overkill for our linear pipeline
9. **Agent Framework** - We're not building an agent
10. **Streaming Parsers** - Not needed for batch processing
11. **Dynamic Configuration** - Our config is static per run

---

## Code Examples

### 1. Retry Logic with Tenacity

```python
from tenacity import (
    retry, stop_after_attempt, wait_exponential_jitter,
    retry_if_exception_type
)

class DataCleaner:
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential_jitter(initial=1, max=30),
        retry=retry_if_exception_type((ConnectionError, TimeoutError)),
    )
    def _call_llm(self, prompt: str) -> str:
        return self.llm_backend.generate(prompt)
```

### 2. Output Fixing Pattern

```python
class XMLParserWithFix:
    def __init__(self, llm_backend, max_retries: int = 3):
        self.llm_backend = llm_backend
        self.max_retries = max_retries
    
    def parse(self, xml_text: str, original_prompt: str) -> dict:
        for attempt in range(self.max_retries + 1):
            try:
                return self._parse_xml(xml_text)
            except XMLParseError as e:
                if attempt == self.max_retries:
                    raise
                
                fix_prompt = f"""Your previous response was not valid XML.

Original request:
{original_prompt}

Your response:
{xml_text}

Error: {e}

Please provide your response again in valid XML format."""
                
                xml_text = self.llm_backend.generate(fix_prompt)
        
        raise XMLParseError("Failed to get valid XML after retries")
```

### 3. Summary Buffer for Docstring Registry

```python
class DocstringRegistry:
    def __init__(self, llm_backend, max_tokens: int = 4000):
        self.llm_backend = llm_backend
        self.max_tokens = max_tokens
        self.summary: str = ""
        self.recent_docstrings: list[str] = []
    
    def add(self, function_name: str, docstring: str):
        self.recent_docstrings.append(f"## {function_name}\n{docstring}")
        self._prune_if_needed()
    
    def _prune_if_needed(self):
        total_tokens = self._count_tokens()
        
        if total_tokens > self.max_tokens:
            # Move oldest docstrings to summary
            to_summarize = []
            while total_tokens > self.max_tokens * 0.7:  # Target 70% capacity
                if not self.recent_docstrings:
                    break
                to_summarize.append(self.recent_docstrings.pop(0))
                total_tokens = self._count_tokens()
            
            if to_summarize:
                self._update_summary(to_summarize)
    
    def _update_summary(self, docstrings: list[str]):
        prompt = f"""Summarize these cleaning function descriptions into a brief paragraph.
Focus on what types of issues they handle.

Previous summary:
{self.summary or "(none)"}

New functions to summarize:
{chr(10).join(docstrings)}

Provide a concise 2-3 sentence summary:"""
        
        self.summary = self.llm_backend.generate(prompt)
    
    def get_context(self) -> str:
        parts = []
        if self.summary:
            parts.append(f"Summary of earlier functions: {self.summary}")
        if self.recent_docstrings:
            parts.append("Recent cleaning functions:\n" + "\n\n".join(self.recent_docstrings))
        return "\n\n".join(parts)
```

### 4. Callback System

```python
from abc import ABC, abstractmethod
from typing import Any

class CleanerCallback(ABC):
    def on_run_start(self, file_path: str, total_chunks: int): pass
    def on_chunk_start(self, chunk_index: int, chunk_data: Any): pass
    def on_function_generated(self, name: str, docstring: str): pass
    def on_chunk_complete(self, chunk_index: int, iterations: int): pass
    def on_error(self, error: Exception, context: dict): pass
    def on_run_complete(self, total_functions: int, output_path: str): pass

class LoggingCallback(CleanerCallback):
    def __init__(self, log_file: str):
        self.log_file = log_file
    
    def on_function_generated(self, name: str, docstring: str):
        with open(self.log_file, 'a') as f:
            f.write(f"Generated: {name}\n")
    
    def on_error(self, error: Exception, context: dict):
        with open(self.log_file, 'a') as f:
            f.write(f"Error in chunk {context.get('chunk_index')}: {error}\n")

class DataCleaner:
    def __init__(self, callbacks: list[CleanerCallback] = None):
        self.callbacks = callbacks or []
    
    def _emit(self, event: str, **kwargs):
        for cb in self.callbacks:
            getattr(cb, event)(**kwargs)
```

---

## Verdict

### Build on top of LangChain?

**No.** LangChain is heavyweight and brings unnecessary complexity for our use case:

1. **Dependency bloat** - LangChain has many dependencies we don't need
2. **Abstraction overhead** - The Runnable pattern is elegant but overkill for a linear pipeline
3. **Learning curve** - Users would need to understand LangChain to modify our code
4. **Version churn** - LangChain has rapid version changes (note the deprecation warnings throughout)
5. **Our core principle** - Users bring their own LLM backend; LangChain assumes specific integrations

### Borrow Patterns?

**Yes.** Several patterns are directly applicable:

| Pattern | Priority | Effort | Value |
|---------|----------|--------|-------|
| Tenacity retry logic | High | Low | High - handles transient failures |
| Output fixing with LLM | High | Medium | High - recovers from bad outputs |
| Summary buffer memory | High | Medium | High - solves context overflow |
| Structured exceptions | High | Low | Medium - better error handling |
| Callback system | Medium | Low | Medium - enables logging/monitoring |
| Fallback chain | Medium | Low | Medium - production resilience |
| Vector store memory | Low | High | Low - only needed at scale |

### Recommended Approach

1. **Keep our simple architecture** - Single `DataCleaner` class, linear flow
2. **Add `tenacity` dependency** - For retry logic (lightweight, focused library)
3. **Implement summary buffer** - Port the pattern for docstring registry management
4. **Add output fixing** - On XML parse failure, ask LLM to fix
5. **Add simple callbacks** - For logging without coupling
6. **Skip LangChain dependency** - Too heavy, too many abstractions

### Final Implementation Checklist

- [ ] Add `tenacity` to dependencies
- [ ] Create `CleanerException` hierarchy
- [ ] Implement `DocstringRegistry` with summary buffer pattern
- [ ] Add retry decorator to LLM calls
- [ ] Implement XML parser with auto-fix on failure
- [ ] Add optional callback hooks for logging
- [ ] Consider `defusedxml` for secure XML parsing

---

## References

- LangChain Core: `libs/core/langchain_core/`
- Memory implementations: `libs/langchain/langchain_classic/memory/`
- Output parsers: `libs/langchain/langchain_classic/output_parsers/`
- Retry logic: `libs/core/langchain_core/runnables/retry.py`
- Fallbacks: `libs/core/langchain_core/runnables/fallbacks.py`

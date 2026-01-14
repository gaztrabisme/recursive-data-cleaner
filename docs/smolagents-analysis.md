# smolagents Framework Analysis

**Research Date**: 2026-01-13  
**Repository**: https://github.com/huggingface/smolagents  
**Version Analyzed**: Latest (cloned to `docs/frameworks/smolagents/`)

---

## Overview

### What it is

smolagents is HuggingFace's lightweight agent framework that enables LLM-powered agents to execute multi-step tasks. The core innovation is **CodeAgent** - agents that express their actions as Python code rather than structured JSON/tool calls.

### Core Philosophy

1. **Simplicity First**: The entire agent logic fits in ~1,000 lines of code (`agents.py`)
2. **Code as Action**: LLMs write Python code snippets as actions, which are then executed. This approach uses 30% fewer steps than traditional JSON-based tool calling.
3. **Model Agnostic**: Supports any LLM backend (transformers, Ollama, OpenAI, Anthropic, LiteLLM)
4. **Security-Conscious**: Multiple sandboxing options (E2B, Docker, Blaxel, Modal, local interpreter with restrictions)

### Key Statistics
- Main agents.py: ~1,800 lines (including ToolCallingAgent and CodeAgent)
- Memory system: ~300 lines
- Tool validation: ~200 lines
- Local Python executor: ~1,500 lines (safe execution sandbox)

---

## Architecture Patterns (Relevant to Our Use Case)

### 1. Multi-Step Agent Loop (ReAct Pattern)

The `MultiStepAgent` base class implements the ReAct (Reason + Act) loop:

```python
# From agents.py - _run_stream method
while not returned_final_answer and self.step_number <= max_steps:
    # Optional planning step at intervals
    if self.planning_interval and (self.step_number == 1 or (self.step_number - 1) % self.planning_interval == 0):
        yield from self._generate_planning_step(task, is_first_step, step)
    
    # Execute one action step
    action_step = ActionStep(step_number=self.step_number, ...)
    try:
        for output in self._step_stream(action_step):
            yield output
            if isinstance(output, ActionOutput) and output.is_final_answer:
                returned_final_answer = True
    except AgentError as e:
        action_step.error = e  # Errors are captured, not raised
    finally:
        self._finalize_step(action_step)
        self.memory.steps.append(action_step)
        self.step_number += 1
```

**Relevance to our project**: Our chunk processing loop is similar - iterate until "clean" or max iterations. We should adopt:
- The `max_steps` hard limit pattern
- Error capture without breaking the loop
- Step finalization with callbacks

### 2. Memory System (AgentMemory)

smolagents uses a structured memory system with typed step objects:

```python
# memory.py
@dataclass
class ActionStep(MemoryStep):
    step_number: int
    timing: Timing
    model_input_messages: list[ChatMessage] | None = None
    tool_calls: list[ToolCall] | None = None
    error: AgentError | None = None
    observations: str | None = None
    action_output: Any = None
    is_final_answer: bool = False
    
    def to_messages(self, summary_mode: bool = False) -> list[ChatMessage]:
        # Converts step to chat messages for context window
        ...

class AgentMemory:
    def __init__(self, system_prompt: str):
        self.system_prompt = SystemPromptStep(system_prompt=system_prompt)
        self.steps: list[TaskStep | ActionStep | PlanningStep] = []
    
    def reset(self):
        self.steps = []
    
    def write_memory_to_messages(self, summary_mode: bool = False) -> list[ChatMessage]:
        # Replay all steps as chat messages
        ...
```

**Relevance to our project**: Our docstring registry serves a similar purpose. We could adopt:
- The `to_messages()` pattern for converting our function registry to prompt format
- The `summary_mode` concept for truncating old context when registry grows large
- Structured step types (AnalysisStep, FunctionGenerationStep, etc.)

### 3. Tool Definition Pattern

Tools are defined as classes with strict validation:

```python
# tools.py
class Tool(BaseTool):
    name: str
    description: str
    inputs: dict[str, dict[str, str | type | bool]]
    output_type: str
    
    def __init__(self, *args, **kwargs):
        self.is_initialized = False
    
    def validate_arguments(self):
        # Validates all required attributes exist
        # Validates input types against AUTHORIZED_TYPES
        # Validates name is valid Python identifier
        ...
    
    @abstractmethod
    def forward(self, *args, **kwargs) -> Any:
        """Actual tool implementation"""
        ...
```

**Relevance to our project**: We could model our generated cleaning functions as "tools" with:
- Structured inputs (data chunk format)
- Validation of generated code before execution
- Clear docstrings/descriptions for the registry

### 4. Error Hierarchy

smolagents defines a clear error taxonomy:

```python
# utils.py
class AgentError(Exception):
    """Base class for other agent-related exceptions"""
    def __init__(self, message, logger):
        super().__init__(message)
        self.message = message
        logger.log_error(message)

class AgentParsingError(AgentError):
    """Exception raised for errors in parsing LLM output"""
    pass

class AgentExecutionError(AgentError):
    """Exception raised for errors in execution"""
    pass

class AgentMaxStepsError(AgentError):
    """Exception raised when max steps reached"""
    pass

class AgentToolCallError(AgentExecutionError):
    """Incorrect arguments passed to tool"""
    pass

class AgentToolExecutionError(AgentExecutionError):
    """Error during tool execution"""
    pass

class AgentGenerationError(AgentError):
    """Error in LLM generation"""
    pass
```

**Relevance to our project**: We should adopt a similar hierarchy:
- `CleanerParsingError` - XML parsing failures
- `CleanerCodeGenerationError` - Invalid Python in LLM response
- `CleanerExecutionError` - Generated function fails on data
- `CleanerMaxIterationsError` - Chunk never marked clean

### 5. Prompt Template System

Uses Jinja2 templates stored in YAML files:

```yaml
# prompts/code_agent.yaml
system_prompt: |-
  You are an expert assistant who can solve any task using code blobs.
  ...
  Here are a few examples using notional tools:
  ---
  Task: "..."
  Thought: I will proceed step by step...
  {{code_block_opening_tag}}
  answer = document_qa(document=document, question="...")
  print(answer)
  {{code_block_closing_tag}}
  Observation: "..."
  ...
  
  Above examples were using notional tools. You only have access to:
  {{code_block_opening_tag}}
  {%- for tool in tools.values() %}
  {{ tool.to_code_prompt() }}
  {% endfor %}
  {{code_block_closing_tag}}
```

```python
# agents.py
def populate_template(template: str, variables: dict[str, Any]) -> str:
    compiled_template = Template(template, undefined=StrictUndefined)
    return compiled_template.render(**variables)
```

**Relevance to our project**: We should adopt:
- Jinja2 for template rendering (safer than f-strings, supports conditionals)
- YAML storage for prompts (easier to edit than inline strings)
- The `StrictUndefined` setting to catch missing variables

### 6. Code Execution Sandbox

The `LocalPythonExecutor` implements a restricted Python interpreter:

```python
# local_python_executor.py
DANGEROUS_MODULES = ["builtins", "io", "os", "pathlib", "subprocess", "sys", ...]
DANGEROUS_FUNCTIONS = ["builtins.compile", "builtins.eval", "builtins.exec", ...]

class LocalPythonExecutor:
    def __init__(self, additional_authorized_imports, max_print_outputs_length=None):
        self.authorized_imports = sorted(set(BASE_BUILTIN_MODULES) | set(additional_authorized_imports))
        ...
    
    def __call__(self, code: str) -> CodeOutput:
        # Parse AST
        # Check for dangerous imports/functions
        # Execute in restricted namespace
        ...
```

**Relevance to our project**: Critical for security when executing LLM-generated code:
- Restrict imports to safe modules
- Block dangerous function calls
- Capture print outputs separately from return values

### 7. Final Answer Validation

Supports custom validation functions before accepting final answers:

```python
# agents.py
class MultiStepAgent:
    def __init__(self, ..., final_answer_checks: list[Callable] | None = None):
        self.final_answer_checks = final_answer_checks if final_answer_checks else []
    
    def _validate_final_answer(self, final_answer: Any):
        for check_function in self.final_answer_checks:
            try:
                assert check_function(final_answer, self.memory, agent=self)
            except Exception as e:
                raise AgentError(f"Check {check_function.__name__} failed: {e}")
```

**Relevance to our project**: We could validate generated functions:
- Syntax check (AST parsing)
- Type hint validation
- Test execution on sample data

---

## Applicable Concepts (What We Should Adopt)

### 1. Structured Memory with Step Types

Instead of a flat list of docstrings, use typed dataclasses:

```python
@dataclass
class ChunkAnalysisStep:
    chunk_id: int
    iteration: int
    issues_detected: list[Issue]
    function_generated: GeneratedFunction | None
    chunk_status: Literal["clean", "needs_more_work"]
    timing: Timing
    
    def to_prompt_context(self) -> str:
        """Convert to text for LLM prompt"""
        ...

@dataclass 
class GeneratedFunction:
    name: str
    docstring: str
    code: str
    issues_solved: list[str]
```

### 2. Callback System for Extensibility

Allow users to hook into the processing loop:

```python
class CallbackRegistry:
    def register(self, step_cls: Type[MemoryStep], callback: Callable):
        ...
    
    def callback(self, memory_step, **kwargs):
        for cb in self._callbacks.get(type(memory_step), []):
            cb(memory_step, **kwargs)

# Usage
cleaner.callbacks.register(ChunkAnalysisStep, my_progress_logger)
cleaner.callbacks.register(GeneratedFunction, my_code_validator)
```

### 3. Planning Intervals

Run periodic "planning" steps to reassess strategy:

```python
# In our context: every N chunks, ask LLM to review all generated functions
# and suggest consolidation or identify patterns
if chunk_number % planning_interval == 0:
    consolidation_prompt = build_consolidation_prompt(function_registry)
    suggestions = llm.generate(consolidation_prompt)
    # Potentially merge similar functions
```

### 4. Error Recovery Pattern

```python
try:
    for output in self._process_chunk(chunk, step):
        yield output
except CleanerParsingError as e:
    # Log error, retry with clarified prompt
    step.error = e
    step.retry_count += 1
    if step.retry_count < MAX_RETRIES:
        continue
except CleanerExecutionError as e:
    # Log error, skip this function, continue
    step.error = e
finally:
    self._finalize_step(step)
```

### 5. Model Protocol

```python
from typing import Protocol

class LLMBackend(Protocol):
    def generate(self, prompt: str, **kwargs) -> str:
        """Return raw text response from LLM"""
        ...
    
    def generate_stream(self, prompt: str, **kwargs) -> Generator[str, None, None]:
        """Optional: stream response tokens"""
        ...
```

---

## Code Examples (Specific Implementations to Reference)

### Example 1: Agent Memory to Messages Conversion

```python
# From memory.py - Key pattern for building context
def write_memory_to_messages(self, summary_mode: bool = False) -> list[ChatMessage]:
    messages = self.memory.system_prompt.to_messages(summary_mode=summary_mode)
    for memory_step in self.memory.steps:
        messages.extend(memory_step.to_messages(summary_mode=summary_mode))
    return messages
```

**Our equivalent:**
```python
def build_docstring_registry(self, max_functions: int = 30) -> str:
    """Build the docstring registry section for prompts"""
    functions = self.function_registry[-max_functions:]  # Most recent N
    registry = "=== EXISTING CLEANING FUNCTIONS ===\n"
    for func in functions:
        registry += f"\n## {func.name}\n{func.docstring}\n"
    return registry
```

### Example 2: Code Parsing with Error Recovery

```python
# From agents.py - CodeAgent._step_stream
try:
    if self._use_structured_outputs_internally:
        code_action = json.loads(output_text)["code"]
        code_action = extract_code_from_text(code_action, self.code_block_tags) or code_action
    else:
        code_action = parse_code_blobs(output_text, self.code_block_tags)
    code_action = fix_final_answer_code(code_action)
    memory_step.code_action = code_action
except Exception as e:
    error_msg = f"Error in code parsing:\n{e}\nMake sure to provide correct code blobs."
    raise AgentParsingError(error_msg, self.logger)
```

**Our equivalent:**
```python
def parse_cleaning_response(self, response: str) -> CleaningAnalysis:
    try:
        root = ET.fromstring(f"<root>{response}</root>")
        issues = self._parse_issues(root.find("issues_detected"))
        function = self._parse_function(root.find("function_to_generate"))
        status = root.find("chunk_status").text
        return CleaningAnalysis(issues=issues, function=function, status=status)
    except ET.ParseError as e:
        raise CleanerParsingError(f"Invalid XML in LLM response: {e}")
    except AttributeError as e:
        raise CleanerParsingError(f"Missing required XML element: {e}")
```

### Example 3: Tool Validation Pattern

```python
# From tool_validation.py - MethodChecker
class MethodChecker(ast.NodeVisitor):
    """Checks that a method only uses defined names and contains no local imports"""
    
    def __init__(self, class_attributes: set[str], check_imports: bool = True):
        self.undefined_names = set()
        self.imports = {}
        self.errors = []
        ...
    
    def visit_Import(self, node):
        for name in node.names:
            actual_name = name.asname or name.name
            self.imports[actual_name] = name.name
    
    def visit_Name(self, node):
        if isinstance(node.ctx, ast.Load):
            if not (node.id in _BUILTIN_NAMES or node.id in self.imports or ...):
                self.errors.append(f"Name '{node.id}' is undefined.")
```

**Our equivalent for validating generated functions:**
```python
def validate_generated_function(self, code: str) -> list[str]:
    """Validate generated Python code, return list of errors"""
    errors = []
    try:
        tree = ast.parse(code)
    except SyntaxError as e:
        return [f"Syntax error: {e}"]
    
    checker = FunctionChecker(allowed_imports=self.safe_imports)
    checker.visit(tree)
    return checker.errors
```

### Example 4: Step Callback System

```python
# From agents.py
def _finalize_step(self, memory_step: ActionStep | PlanningStep | FinalAnswerStep):
    if not isinstance(memory_step, FinalAnswerStep):
        memory_step.timing.end_time = time.time()
    self.step_callbacks.callback(memory_step, agent=self)

# From memory.py
class CallbackRegistry:
    def callback(self, memory_step, **kwargs):
        for callback in self._callbacks.get(type(memory_step), []):
            try:
                callback(memory_step, **kwargs)
            except Exception as e:
                logger.exception(f"Error in callback: {e}")
```

---

## Verdict: Build on Top of It vs. Borrow Patterns

### Recommendation: **Borrow Patterns, Do Not Build On Top**

#### Reasons NOT to build on smolagents:

1. **Different Core Abstraction**: smolagents is built around the concept of "tools" that an agent calls. Our use case is fundamentally different - we're building a code *generator*, not a code *executor* that calls predefined tools.

2. **Overhead for Our Use Case**: smolagents includes significant infrastructure we don't need:
   - Multi-modal support (images, audio)
   - Remote execution (E2B, Docker, Modal)
   - Hub integration for sharing agents
   - Gradio UI generation
   - MCP server support

3. **Tight Coupling to Chat Format**: smolagents assumes a chat-based interaction model with role-based messages. Our XML-structured prompts don't fit this model cleanly.

4. **Different Execution Model**: smolagents executes code in a sandbox to get results. We generate code to be saved and run later by the user.

#### Patterns to Borrow:

| Pattern | smolagents Location | Our Implementation Priority |
|---------|---------------------|----------------------------|
| Typed memory steps | `memory.py` | HIGH - Structure our function registry |
| Error hierarchy | `utils.py` | HIGH - Better error handling |
| Step callbacks | `memory.py`, `agents.py` | MEDIUM - Progress/logging hooks |
| Jinja2 templates | `agents.py` | MEDIUM - Cleaner prompt building |
| AST-based validation | `tool_validation.py` | HIGH - Validate generated code |
| Max steps pattern | `agents.py` | HIGH - Already planned |
| Planning intervals | `agents.py` | LOW - Function consolidation |
| Code block parsing | `utils.py` | MEDIUM - Already using XML |

#### Implementation Plan:

1. **Phase 1 (Critical)**:
   - Adopt error hierarchy pattern
   - Implement typed step dataclasses for memory
   - Add AST-based code validation

2. **Phase 2 (Important)**:
   - Add callback system for extensibility
   - Switch to Jinja2 for prompt templates
   - Implement summary mode for large registries

3. **Phase 3 (Nice to Have)**:
   - Planning intervals for function consolidation
   - Streaming support for long operations

---

## Summary

smolagents is an excellent reference implementation for agent patterns, but it solves a different problem than ours. We should:

1. **Study** their memory system, error handling, and validation patterns
2. **Adopt** specific implementation patterns (dataclasses, callbacks, AST validation)
3. **Not** use it as a dependency or base class
4. **Keep** our simpler, focused architecture

The key insight from smolagents is that good agent systems need:
- Clear separation between memory, execution, and orchestration
- Robust error handling that doesn't break the loop
- Flexible extension points (callbacks, custom tools)
- Strong validation before execution

These principles apply directly to our data cleaning pipeline.

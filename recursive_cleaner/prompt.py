"""Prompt template for the data cleaning pipeline."""

from typing import Literal

SATURATION_CHECK_TEMPLATE = '''You are assessing whether data cleaning pattern discovery has saturated.

=== CLEANING FUNCTIONS GENERATED SO FAR ({count}) ===
{function_summaries}

=== RECENT ACTIVITY ===
Chunks processed: {total_chunks}
Functions from last {recent_window} chunks: {recent_new_functions}

=== TASK ===
Assess whether we've likely seen all major data quality patterns, or if processing more chunks would discover new issues.

=== OUTPUT FORMAT ===
<saturation_assessment>
  <saturated>true|false</saturated>
  <confidence>high|medium|low</confidence>
  <reasoning>
    Explanation of why patterns are/aren't saturated
  </reasoning>
  <recommendation>stop|continue</recommendation>
</saturation_assessment>

Consider:
- If recent chunks produced few/no new functions, patterns may be saturated
- If functions cover diverse issues (dates, phones, emails, etc.), likely saturated
- If all functions target same issue type, more variety may exist
'''

CONSOLIDATION_TEMPLATE = '''You are reviewing cleaning functions for consolidation.

=== FUNCTIONS TO REVIEW ({count} functions) ===
{functions}

=== TASK ===
1. Identify functions that handle the SAME type of data quality issue
2. Merge redundant functions into fewer, more general ones
3. Keep functions that are truly unique

=== OUTPUT FORMAT ===
<consolidation_result>
  <merged_functions>
    <function>
      <name>merged_function_name</name>
      <original_names>func1, func2</original_names>
      <docstring>
      Combined description covering all cases.
      Tags: tag1, tag2
      </docstring>
      <code>
```python
def merged_function_name(record):
    ...
```
      </code>
    </function>
  </merged_functions>

  <kept_unchanged>
    <function_name>unique_func1</function_name>
  </kept_unchanged>

  <self_assessment>
    <complete>true|false</complete>
    <remaining_issues>Description of any remaining redundancy, or "none"</remaining_issues>
    <confidence>high|medium|low</confidence>
  </self_assessment>
</consolidation_result>

RULES:
- Merged function must handle ALL cases from originals
- If unsure whether to merge, keep separate
- Always include self_assessment
- <complete>true</complete> means no more consolidation needed
'''

# Renamed from PROMPT_TEMPLATE to be explicit about structured mode
STRUCTURED_PROMPT_TEMPLATE = '''You are a data cleaning expert. Analyze data and generate Python functions to fix issues.

=== USER'S CLEANING GOALS ===
{instructions}

=== EXISTING FUNCTIONS (DO NOT RECREATE) ===
{context}
{schema_section}
=== DATA CHUNK ===
{chunk}

=== TASK ===
1. List ALL data quality issues you find in the chunk
2. Mark each as solved="true" if an existing function handles it
3. Generate code for ONLY the FIRST unsolved issue
4. Use this EXACT format:

<cleaning_analysis>
  <issues_detected>
    <issue id="1" solved="true|false">Description of issue</issue>
  </issues_detected>

  <function_to_generate>
    <name>function_name</name>
    <docstring>
What it does, edge cases handled.
Tags: domain, action, detail
    </docstring>
    <code>
```python
def function_name(data):
    # Complete implementation
    pass
```
    </code>
  </function_to_generate>

  <chunk_status>clean|needs_more_work</chunk_status>
</cleaning_analysis>

RULES:
- ONE function per response
- If all issues solved: <chunk_status>clean</chunk_status>, omit <function_to_generate>
- Include imports inside the function or document needed imports in docstring
- Function must be idempotent (safe to run multiple times)
- Use ```python markdown blocks for code
- Include 2-5 tags in the docstring describing what the function handles
- Format: "Tags: tag1, tag2, tag3" on its own line at end of docstring
- Use lowercase single words: domain terms (date, phone, email) and action terms (normalize, validate, fix)'''

# Backward compatibility alias
PROMPT_TEMPLATE = STRUCTURED_PROMPT_TEMPLATE

TEXT_PROMPT_TEMPLATE = '''You are a text cleaning expert. Analyze text and generate Python functions to fix issues.

=== USER'S CLEANING GOALS ===
{instructions}

=== EXISTING FUNCTIONS (DO NOT RECREATE) ===
{context}

=== TEXT CHUNK ===
{chunk}

=== TASK ===
1. List ALL text quality issues (artifacts, spacing, OCR errors, formatting)
2. Mark each as solved="true" if an existing function handles it
3. Generate code for ONLY the FIRST unsolved issue
4. Use this EXACT format:

<cleaning_analysis>
  <issues_detected>
    <issue id="1" solved="true|false">Description of issue</issue>
  </issues_detected>

  <function_to_generate>
    <name>function_name</name>
    <docstring>
What it does, edge cases handled.
Tags: domain, action, detail
    </docstring>
    <code>
```python
def function_name(text: str) -> str:
    # Complete implementation
    return text
```
    </code>
  </function_to_generate>

  <chunk_status>clean|needs_more_work</chunk_status>
</cleaning_analysis>

RULES:
- ONE function per response
- Function takes text string, returns cleaned text string
- If all issues solved: <chunk_status>clean</chunk_status>, omit <function_to_generate>
- Function must be idempotent (safe to run multiple times)
- Use ```python markdown blocks for code
- Include 2-5 tags in the docstring describing what the function handles
- Format: "Tags: tag1, tag2, tag3" on its own line at end of docstring
- Use lowercase single words: domain terms (date, phone, email) and action terms (normalize, validate, fix)'''


def build_prompt(
    instructions: str,
    context: str,
    chunk: str,
    schema: str = "",
    mode: Literal["structured", "text"] = "structured",
) -> str:
    """
    Build the full prompt for the LLM.

    Args:
        instructions: User's cleaning goals
        context: Existing function docstrings
        chunk: Data chunk to analyze
        schema: Data schema (only used for structured mode)
        mode: "structured" for JSON/CSV data, "text" for prose

    Returns:
        Formatted prompt string
    """
    if mode == "text":
        return TEXT_PROMPT_TEMPLATE.format(
            instructions=instructions,
            context=context,
            chunk=chunk,
        )
    else:
        schema_section = f"\n=== DATA SCHEMA ===\n{schema}\n\n" if schema else "\n"
        return STRUCTURED_PROMPT_TEMPLATE.format(
            instructions=instructions,
            context=context,
            schema_section=schema_section,
            chunk=chunk,
        )

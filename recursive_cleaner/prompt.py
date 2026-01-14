"""Prompt template for the data cleaning pipeline."""

from typing import Literal

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
    <docstring>What it does, edge cases handled</docstring>
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
- Use ```python markdown blocks for code'''

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
    <docstring>What it does, edge cases handled</docstring>
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
- Use ```python markdown blocks for code'''


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

"""Prompt template for the data cleaning pipeline."""

PROMPT_TEMPLATE = '''You are a data cleaning expert. Analyze data and generate Python functions to fix issues.

=== USER'S CLEANING GOALS ===
{instructions}

=== EXISTING FUNCTIONS (DO NOT RECREATE) ===
{context}

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


def build_prompt(instructions: str, context: str, chunk: str) -> str:
    """Build the full prompt for the LLM."""
    return PROMPT_TEMPLATE.format(
        instructions=instructions,
        context=context,
        chunk=chunk
    )

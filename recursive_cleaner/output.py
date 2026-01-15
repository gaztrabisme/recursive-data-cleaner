"""Output generation for cleaning functions."""

import ast
from pathlib import Path

from recursive_cleaner.dependencies import resolve_dependencies
from recursive_cleaner.errors import OutputValidationError


def extract_imports(code: str) -> list[str]:
    """Extract import statements from code."""
    imports = []
    for line in code.split('\n'):
        stripped = line.strip()
        if stripped.startswith('import ') or stripped.startswith('from '):
            imports.append(stripped)
    return imports


def remove_imports_from_code(code: str) -> str:
    """Remove import statements from code, keeping the rest."""
    lines = []
    for line in code.split('\n'):
        stripped = line.strip()
        if not (stripped.startswith('import ') or stripped.startswith('from ')):
            lines.append(line)
    # Remove leading empty lines
    while lines and not lines[0].strip():
        lines.pop(0)
    return '\n'.join(lines)


def consolidate_imports(imports: list[str]) -> list[str]:
    """
    Consolidate and deduplicate imports.

    - Duplicate `import x` → single `import x`
    - `from x import a` + `from x import b` → `from x import a, b`
    - `import x` + `from x import y` → both kept (different forms)

    Args:
        imports: Raw import statements from all functions

    Returns:
        Consolidated, sorted import statements
    """
    # Track regular imports (import x, import x.y)
    regular_imports: set[str] = set()

    # Track from imports: module -> set of names
    from_imports: dict[str, set[str]] = {}

    for imp in imports:
        imp = imp.strip()
        if imp.startswith("from "):
            # Parse: from module import name1, name2
            try:
                # Split "from module import names"
                rest = imp[5:]  # Remove "from "
                module, names_part = rest.split(" import ", 1)
                module = module.strip()
                # Parse names (handle "a, b, c" and "a as alias")
                names = [n.strip() for n in names_part.split(",")]
                if module not in from_imports:
                    from_imports[module] = set()
                from_imports[module].update(names)
            except ValueError:
                # Malformed import, keep as-is
                regular_imports.add(imp)
        elif imp.startswith("import "):
            regular_imports.add(imp)

    # Build result
    result = []

    # Add regular imports (sorted)
    result.extend(sorted(regular_imports))

    # Add consolidated from imports (sorted by module, then by names)
    for module in sorted(from_imports.keys()):
        names = sorted(from_imports[module])
        result.append(f"from {module} import {', '.join(names)}")

    return result


def generate_clean_data_function(function_names: list[str]) -> str:
    """Generate the clean_data() entrypoint that calls all functions."""
    if not function_names:
        return '''
def clean_data(data):
    """Apply all cleaning functions to data."""
    return data
'''

    calls = '\n    '.join(f'data = {name}(data)' for name in function_names)
    return f'''
def clean_data(data):
    """
    Apply all cleaning functions to data.

    Functions applied (in order):
{chr(10).join(f'    - {name}' for name in function_names)}
    """
    {calls}
    return data
'''


def deduplicate_functions(functions: list[dict]) -> list[dict]:
    """
    Remove duplicate functions by name, keeping the first occurrence.

    Args:
        functions: List of function dicts with 'name' key

    Returns:
        Deduplicated list of functions
    """
    seen_names = set()
    result = []
    for f in functions:
        if f['name'] not in seen_names:
            seen_names.add(f['name'])
            result.append(f)
        else:
            print(f"  Warning: Skipping duplicate function '{f['name']}'")
    return result


def write_cleaning_file(
    functions: list[dict],
    output_path: str = "cleaning_functions.py"
) -> None:
    """
    Write all generated functions to a Python file.

    Args:
        functions: List of dicts with 'name', 'docstring', 'code' keys
        output_path: Path to output file

    Raises:
        OutputValidationError: If the combined output has invalid Python syntax
    """
    if not functions:
        # Write empty file with just clean_data passthrough
        content = '"""Auto-generated data cleaning functions."""\n'
        content += generate_clean_data_function([])
        Path(output_path).write_text(content)
        return

    # Deduplicate functions by name (keep first occurrence)
    functions = deduplicate_functions(functions)

    # Resolve dependencies to order functions correctly (callees before callers)
    functions = resolve_dependencies(functions)

    # Collect all imports (excluding problematic __main__ imports)
    all_imports = []
    for f in functions:
        imports = extract_imports(f['code'])
        # Filter out __main__ imports which are invalid cross-function references
        imports = [i for i in imports if '__main__' not in i]
        all_imports.extend(imports)

    unique_imports = consolidate_imports(all_imports)

    # Build file content
    lines = ['"""Auto-generated data cleaning functions."""', '']

    if unique_imports:
        lines.extend(unique_imports)
        lines.append('')
        lines.append('')

    # Add each function (with imports removed)
    for f in functions:
        code_without_imports = remove_imports_from_code(f['code'])
        lines.append(code_without_imports)
        lines.append('')
        lines.append('')

    # Add clean_data entrypoint
    function_names = [f['name'] for f in functions]
    lines.append(generate_clean_data_function(function_names))

    content = '\n'.join(lines)

    # Final validation: ensure combined output is valid Python
    try:
        ast.parse(content)
    except SyntaxError as e:
        raise OutputValidationError(
            f"Generated output has invalid Python syntax at line {e.lineno}: {e.msg}"
        )

    Path(output_path).write_text(content)

"""Dependency resolution for generated cleaning functions."""

import ast


def detect_calls(code: str, known_functions: set[str]) -> set[str]:
    """Use AST to find function calls within code that match known functions."""
    try:
        tree = ast.parse(code)
    except SyntaxError:
        return set()

    calls = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
            if node.func.id in known_functions:
                calls.add(node.func.id)
    return calls


def resolve_dependencies(functions: list[dict]) -> list[dict]:
    """
    Reorder functions based on call dependencies.
    Returns topologically sorted list (callees before callers).
    Cycles are handled by preserving original order for cycle members.
    """
    if not functions:
        return []

    by_name = {f["name"]: f for f in functions}
    known = set(by_name.keys())
    deps = {f["name"]: detect_calls(f["code"], known) for f in functions}

    # Kahn's algorithm: in_degree = number of dependencies for each function
    in_degree = {name: sum(1 for c in called if c != name) for name, called in deps.items()}
    original_order = {f["name"]: i for i, f in enumerate(functions)}

    # Start with functions that have no dependencies
    queue = sorted([n for n in known if in_degree[n] == 0], key=lambda n: original_order[n])
    result, visited = [], set()

    while queue:
        name = queue.pop(0)
        if name in visited:
            continue
        visited.add(name)
        result.append(by_name[name])

        # Update in-degrees for callers of this function
        for caller, callees in deps.items():
            if name in callees and caller not in visited:
                in_degree[caller] -= 1
                if in_degree[caller] == 0:
                    queue.append(caller)
                    queue.sort(key=lambda n: original_order[n])

    # Handle cycles: append remaining functions in original order
    result.extend(f for f in functions if f["name"] not in visited)
    return result

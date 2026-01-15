"""Tests for output generation."""

import ast
import pytest
from pathlib import Path
from recursive_cleaner.output import (
    extract_imports,
    remove_imports_from_code,
    consolidate_imports,
    generate_clean_data_function,
    write_cleaning_file,
)


def test_extract_imports():
    """Extract import statements from code."""
    code = '''import re
from typing import List

def foo():
    pass
'''
    imports = extract_imports(code)
    assert 'import re' in imports
    assert 'from typing import List' in imports
    assert len(imports) == 2


def test_remove_imports_from_code():
    """Remove imports, keep function."""
    code = '''import re

def foo():
    return re.match("a", "a")
'''
    result = remove_imports_from_code(code)
    assert 'import re' not in result
    assert 'def foo():' in result


def test_consolidate_imports_deduplicates():
    """Remove duplicate imports."""
    imports = ['import re', 'import json', 'import re', 'from typing import List']
    result = consolidate_imports(imports)
    assert result.count('import re') == 1
    assert len(result) == 3


def test_consolidate_imports_merges_from_imports():
    """Merge from imports from same module."""
    imports = [
        'from typing import List',
        'from typing import Dict',
        'from typing import Optional',
    ]
    result = consolidate_imports(imports)
    assert len(result) == 1
    assert 'from typing import' in result[0]
    assert 'Dict' in result[0]
    assert 'List' in result[0]
    assert 'Optional' in result[0]


def test_consolidate_imports_keeps_different_forms():
    """Keep both import x and from x import y."""
    imports = [
        'import json',
        'from json import dumps',
    ]
    result = consolidate_imports(imports)
    assert len(result) == 2
    assert 'import json' in result
    assert 'from json import dumps' in result


def test_consolidate_imports_sorts_alphabetically():
    """Imports are sorted alphabetically."""
    imports = [
        'import re',
        'import json',
        'import ast',
        'from typing import Dict',
        'from collections import OrderedDict',
    ]
    result = consolidate_imports(imports)
    # Regular imports come first, sorted
    assert result[0] == 'import ast'
    assert result[1] == 'import json'
    assert result[2] == 'import re'
    # From imports come after, sorted by module
    assert 'from collections' in result[3]
    assert 'from typing' in result[4]


def test_consolidate_imports_handles_aliased_imports():
    """Handle 'import x as y' and 'from x import y as z'."""
    imports = [
        'from typing import List as L',
        'from typing import Dict',
    ]
    result = consolidate_imports(imports)
    assert len(result) == 1
    # Both should be in the merged import
    assert 'Dict' in result[0]
    assert 'List as L' in result[0]


def test_generate_clean_data_empty():
    """Empty function list generates passthrough."""
    result = generate_clean_data_function([])
    assert 'def clean_data(data):' in result
    assert 'return data' in result


def test_generate_clean_data_with_functions():
    """Function list generates chained calls."""
    result = generate_clean_data_function(['func_a', 'func_b'])
    assert 'data = func_a(data)' in result
    assert 'data = func_b(data)' in result


def test_write_cleaning_file_empty(tmp_path):
    """Empty functions list creates valid file."""
    output = tmp_path / "clean.py"
    write_cleaning_file([], str(output))

    content = output.read_text()
    assert 'def clean_data' in content
    # Verify valid Python
    ast.parse(content)


def test_write_cleaning_file_with_functions(tmp_path):
    """Functions are written correctly."""
    functions = [
        {
            'name': 'fix_phones',
            'docstring': 'Fix phone numbers',
            'code': '''import re

def fix_phones(data):
    return data
'''
        },
        {
            'name': 'fix_dates',
            'docstring': 'Fix dates',
            'code': '''from datetime import datetime

def fix_dates(data):
    return data
'''
        }
    ]

    output = tmp_path / "clean.py"
    write_cleaning_file(functions, str(output))

    content = output.read_text()

    # Check imports consolidated at top
    assert 'import re' in content
    assert 'from datetime import datetime' in content

    # Check functions present
    assert 'def fix_phones(data):' in content
    assert 'def fix_dates(data):' in content

    # Check clean_data entrypoint
    assert 'def clean_data(data):' in content
    assert 'data = fix_phones(data)' in content
    assert 'data = fix_dates(data)' in content

    # Verify valid Python
    ast.parse(content)


def test_write_cleaning_file_deduplicates_imports(tmp_path):
    """Duplicate imports are consolidated."""
    functions = [
        {'name': 'f1', 'docstring': 'd1', 'code': 'import re\ndef f1(d): pass'},
        {'name': 'f2', 'docstring': 'd2', 'code': 'import re\ndef f2(d): pass'},
    ]

    output = tmp_path / "clean.py"
    write_cleaning_file(functions, str(output))

    content = output.read_text()
    # Should only have one 'import re'
    assert content.count('import re') == 1


def test_write_cleaning_file_deduplicates_functions(tmp_path):
    """Duplicate function names are filtered out (keep first)."""
    functions = [
        {'name': 'normalize', 'docstring': 'First version', 'code': 'def normalize(d): return d'},
        {'name': 'other_func', 'docstring': 'Other', 'code': 'def other_func(d): return d'},
        {'name': 'normalize', 'docstring': 'Second version', 'code': 'def normalize(d): return d * 2'},
    ]

    output = tmp_path / "clean.py"
    write_cleaning_file(functions, str(output))

    content = output.read_text()
    # Should only have one 'def normalize'
    assert content.count('def normalize(d):') == 1
    # clean_data should only call normalize once
    assert content.count('data = normalize(data)') == 1
    # Verify valid Python
    ast.parse(content)


def test_write_cleaning_file_filters_main_imports(tmp_path):
    """__main__ imports are filtered out."""
    functions = [
        {
            'name': 'func_with_main',
            'docstring': 'Has __main__ import',
            'code': '''from __main__ import something
import re

def func_with_main(d):
    return d
'''
        },
    ]

    output = tmp_path / "clean.py"
    write_cleaning_file(functions, str(output))

    content = output.read_text()
    # Should NOT have __main__ import
    assert '__main__' not in content
    # Should still have valid import
    assert 'import re' in content
    # Verify valid Python
    ast.parse(content)


def test_write_cleaning_file_raises_on_invalid_combined_output(tmp_path):
    """OutputValidationError raised when combined output is invalid Python."""
    from recursive_cleaner.errors import OutputValidationError

    # Create a function with code that's individually valid but becomes
    # invalid when combined (e.g., unclosed bracket that spans functions)
    # This is tricky, so let's use a simpler approach - mock the scenario
    # by creating code that will fail final ast.parse

    functions = [
        {
            'name': 'broken',
            'docstring': 'Has syntax error',
            'code': '''def broken(d):
    try:
    except:
        pass
'''
        },
    ]

    output = tmp_path / "clean.py"
    with pytest.raises(OutputValidationError):
        write_cleaning_file(functions, str(output))

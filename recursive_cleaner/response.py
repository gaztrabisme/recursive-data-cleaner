"""Response parsing utilities for LLM output."""

import ast
import re
import xml.etree.ElementTree as ET

from recursive_cleaner.errors import ParseError


def parse_response(text: str) -> dict:
    """
    Extract structured data from LLM response.

    Args:
        text: Raw LLM response containing XML with cleaning analysis

    Returns:
        Dictionary with keys: issues, name, docstring, code, status

    Raises:
        ParseError: If XML is malformed or Python code is invalid
    """
    try:
        # Wrap in root to handle multiple top-level elements
        root = ET.fromstring(f"<root>{text}</root>")
    except ET.ParseError as e:
        raise ParseError(f"Invalid XML: {e}")

    # Find the cleaning_analysis element
    analysis = root.find(".//cleaning_analysis")
    if analysis is None:
        # Try parsing the text directly as cleaning_analysis
        try:
            analysis = ET.fromstring(text)
            if analysis.tag != "cleaning_analysis":
                analysis = analysis.find(".//cleaning_analysis")
        except ET.ParseError:
            pass

    if analysis is None:
        raise ParseError("No <cleaning_analysis> element found")

    # Parse issues
    issues = _parse_issues(analysis)

    # Parse function details
    func_elem = analysis.find(".//function_to_generate")
    name = ""
    docstring = ""
    code = ""

    if func_elem is not None:
        name = (func_elem.findtext("name") or "").strip()
        docstring = (func_elem.findtext("docstring") or "").strip()

        code_elem = func_elem.find("code")
        if code_elem is not None and code_elem.text:
            code = extract_python_block(code_elem.text)

            # Validate Python syntax
            try:
                ast.parse(code)
            except SyntaxError as e:
                raise ParseError(f"Invalid Python syntax: {e}")

            # Reject code that tries to import from __main__ (invalid cross-function reference)
            if '__main__' in code:
                raise ParseError(
                    "Code contains invalid __main__ import. "
                    "Functions should be self-contained."
                )

    # Parse status
    status = (analysis.findtext("chunk_status") or "needs_more_work").strip()

    return {
        "issues": issues,
        "name": name,
        "docstring": docstring,
        "code": code,
        "status": status,
    }


def _parse_issues(root: ET.Element) -> list[dict]:
    """Parse issue elements from the XML."""
    issues = []
    for issue in root.findall(".//issue"):
        issue_id = issue.get("id", "")
        solved = issue.get("solved", "false").lower() == "true"
        description = (issue.text or "").strip()
        issues.append({
            "id": issue_id,
            "solved": solved,
            "description": description,
        })
    return issues


def extract_python_block(text: str) -> str:
    """
    Extract code from ```python ... ``` markdown block.

    Args:
        text: Text potentially containing a markdown code block

    Returns:
        Extracted Python code, or stripped text if no block found
    """
    match = re.search(r"```python\s*(.*?)\s*```", text, re.DOTALL)
    if match:
        return match.group(1).strip()
    return text.strip()

"""Response parsing utilities for LLM output."""

import ast
import re
import xml.etree.ElementTree as ET
from dataclasses import dataclass

from recursive_cleaner.errors import ParseError


@dataclass
class AgentAssessment:
    """LLM's self-assessment of consolidation completeness."""

    complete: bool
    remaining_issues: str
    confidence: str  # "high", "medium", "low"


@dataclass
class SaturationAssessment:
    """LLM's assessment of whether pattern discovery has saturated."""

    saturated: bool
    confidence: str  # "high", "medium", "low"
    reasoning: str
    recommendation: str  # "stop", "continue"


@dataclass
class ConsolidationResult:
    """Result of parsing a consolidation LLM response."""

    merged_functions: list[dict]  # [{name, docstring, code, original_names}]
    kept_unchanged: list[str]  # function names to keep
    assessment: AgentAssessment


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


def parse_consolidation_response(text: str) -> ConsolidationResult:
    """
    Parse consolidation LLM response.

    Args:
        text: Raw LLM response containing consolidation_result XML

    Returns:
        ConsolidationResult with merged functions, kept functions, and assessment

    Raises:
        ParseError: If XML is malformed or code is invalid
    """
    try:
        # Wrap in root to handle multiple top-level elements
        root = ET.fromstring(f"<root>{text}</root>")
    except ET.ParseError as e:
        raise ParseError(f"Invalid XML: {e}")

    # Find the consolidation_result element
    result = root.find(".//consolidation_result")
    if result is None:
        # Try parsing the text directly
        try:
            result = ET.fromstring(text)
            if result.tag != "consolidation_result":
                result = result.find(".//consolidation_result")
        except ET.ParseError:
            pass

    if result is None:
        raise ParseError("No <consolidation_result> element found")

    # Parse merged functions
    merged_functions = []
    for func_elem in result.findall(".//merged_functions/function"):
        name = (func_elem.findtext("name") or "").strip()
        original_names = (func_elem.findtext("original_names") or "").strip()
        docstring = (func_elem.findtext("docstring") or "").strip()

        code_elem = func_elem.find("code")
        code = ""
        if code_elem is not None and code_elem.text:
            code = extract_python_block(code_elem.text)

            # Validate Python syntax
            try:
                ast.parse(code)
            except SyntaxError as e:
                raise ParseError(f"Invalid Python syntax in merged function '{name}': {e}")

        merged_functions.append({
            "name": name,
            "docstring": docstring,
            "code": code,
            "original_names": original_names,
        })

    # Parse kept_unchanged
    kept_unchanged = []
    for name_elem in result.findall(".//kept_unchanged/function_name"):
        name = (name_elem.text or "").strip()
        if name:
            kept_unchanged.append(name)

    # Parse self_assessment
    assessment_elem = result.find(".//self_assessment")
    if assessment_elem is None:
        # Default assessment if not provided
        assessment = AgentAssessment(
            complete=False,
            remaining_issues="Assessment not provided",
            confidence="low",
        )
    else:
        complete_text = (assessment_elem.findtext("complete") or "false").strip().lower()
        complete = complete_text == "true"
        remaining_issues = (assessment_elem.findtext("remaining_issues") or "none").strip()
        confidence = (assessment_elem.findtext("confidence") or "medium").strip().lower()
        # Validate confidence value
        if confidence not in ("high", "medium", "low"):
            confidence = "medium"
        assessment = AgentAssessment(
            complete=complete,
            remaining_issues=remaining_issues,
            confidence=confidence,
        )

    return ConsolidationResult(
        merged_functions=merged_functions,
        kept_unchanged=kept_unchanged,
        assessment=assessment,
    )


def parse_saturation_response(text: str) -> SaturationAssessment:
    """
    Parse saturation check LLM response.

    Args:
        text: Raw LLM response containing saturation_assessment XML

    Returns:
        SaturationAssessment with saturated, confidence, reasoning, recommendation

    Raises:
        ParseError: If XML is malformed
    """
    try:
        # Wrap in root to handle multiple top-level elements
        root = ET.fromstring(f"<root>{text}</root>")
    except ET.ParseError as e:
        raise ParseError(f"Invalid XML: {e}")

    # Find the saturation_assessment element
    assessment = root.find(".//saturation_assessment")
    if assessment is None:
        # Try parsing the text directly
        try:
            assessment = ET.fromstring(text)
            if assessment.tag != "saturation_assessment":
                assessment = assessment.find(".//saturation_assessment")
        except ET.ParseError:
            pass

    if assessment is None:
        raise ParseError("No <saturation_assessment> element found")

    # Parse fields
    saturated_text = (assessment.findtext("saturated") or "false").strip().lower()
    saturated = saturated_text == "true"

    confidence = (assessment.findtext("confidence") or "medium").strip().lower()
    if confidence not in ("high", "medium", "low"):
        confidence = "medium"

    reasoning = (assessment.findtext("reasoning") or "").strip()

    recommendation = (assessment.findtext("recommendation") or "continue").strip().lower()
    if recommendation not in ("stop", "continue"):
        recommendation = "continue"

    return SaturationAssessment(
        saturated=saturated,
        confidence=confidence,
        reasoning=reasoning,
        recommendation=recommendation,
    )

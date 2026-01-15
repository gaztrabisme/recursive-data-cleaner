"""Tests for optimizer module - tag extraction and function grouping."""

import ast
import pytest
from math import log

from recursive_cleaner.optimizer import (
    extract_tags,
    group_by_salience,
    _calculate_idf,
    _fallback_from_name,
    _rebalance_groups,
    format_functions_for_review,
    consolidate_group,
    consolidate_with_agency,
)
from recursive_cleaner.response import (
    parse_consolidation_response,
    AgentAssessment,
    ConsolidationResult,
)
from recursive_cleaner.errors import ParseError


class MockBackend:
    """Mock LLM backend for testing consolidation."""

    def __init__(self, responses: list[str]):
        self.responses = responses
        self.call_count = 0
        self.prompts: list[str] = []

    def generate(self, prompt: str) -> str:
        self.prompts.append(prompt)
        response = self.responses[min(self.call_count, len(self.responses) - 1)]
        self.call_count += 1
        return response


class TestExtractTags:
    """Tests for extract_tags() function."""

    def test_basic_extraction(self):
        """Basic tag extraction from docstring."""
        docstring = """Normalize phone numbers to E.164 format.
Handles: +1-555-1234, (555) 123-4567, raw digits
Tags: phone, normalize, format"""
        result = extract_tags(docstring)
        assert result == {"phone", "normalize", "format"}

    def test_no_tags(self):
        """Docstring without tags returns empty set."""
        docstring = "Just a simple docstring with no tags."
        result = extract_tags(docstring)
        assert result == set()

    def test_empty_tags(self):
        """Empty tags line returns empty set."""
        docstring = """Some description.
Tags: """
        result = extract_tags(docstring)
        assert result == set()

    def test_whitespace_handling(self):
        """Extra whitespace in tags is stripped."""
        docstring = """Description here.
Tags:  phone , normalize  , format  """
        result = extract_tags(docstring)
        assert result == {"phone", "normalize", "format"}

    def test_case_normalization(self):
        """Tags are lowercased."""
        docstring = """Some function.
Tags: Phone, NORMALIZE, Format"""
        result = extract_tags(docstring)
        assert result == {"phone", "normalize", "format"}

    def test_tags_mid_docstring(self):
        """Tags in the middle of docstring are extracted."""
        docstring = """Description of what this does.
Tags: date, parse, iso
More text after the tags line."""
        result = extract_tags(docstring)
        assert result == {"date", "parse", "iso"}

    def test_empty_docstring(self):
        """Empty docstring returns empty set."""
        assert extract_tags("") == set()
        assert extract_tags(None) == set()  # type: ignore

    def test_single_tag(self):
        """Single tag is handled correctly."""
        docstring = """Fix dates.
Tags: date"""
        result = extract_tags(docstring)
        assert result == {"date"}

    def test_tags_with_trailing_commas(self):
        """Trailing commas don't create empty tags."""
        docstring = """Description.
Tags: a, b, c,"""
        result = extract_tags(docstring)
        assert result == {"a", "b", "c"}

    def test_tags_case_insensitive_keyword(self):
        """Tags keyword is case insensitive."""
        docstring = """Description.
TAGS: phone, email"""
        result = extract_tags(docstring)
        assert result == {"phone", "email"}


class TestCalculateIdf:
    """Tests for _calculate_idf() function."""

    def test_basic_idf(self):
        """IDF is higher for rarer tags."""
        func_tags = [
            {"common", "rare"},
            {"common"},
            {"common"},
        ]
        idf = _calculate_idf(func_tags, 3)
        # "common" appears in 3/3 docs: IDF = log(3/3) = 0
        # "rare" appears in 1/3 docs: IDF = log(3/1) = log(3) > 0
        assert idf["common"] == pytest.approx(log(3 / 3))
        assert idf["rare"] == pytest.approx(log(3 / 1))
        assert idf["rare"] > idf["common"]

    def test_empty_tags_list(self):
        """Empty tag list returns empty dict."""
        assert _calculate_idf([], 0) == {}

    def test_all_same_tags(self):
        """When all functions have same tag, IDF is 0."""
        func_tags = [{"tag"}, {"tag"}, {"tag"}]
        idf = _calculate_idf(func_tags, 3)
        assert idf["tag"] == pytest.approx(0.0)


class TestFallbackFromName:
    """Tests for _fallback_from_name() function."""

    def test_phone_extraction(self):
        """Extract 'phone' from function name."""
        assert _fallback_from_name("normalize_phone_format") == "phone"

    def test_date_extraction(self):
        """Extract 'date' from function name."""
        assert _fallback_from_name("fix_date_parsing") == "date"

    def test_email_extraction(self):
        """Extract 'email' from function name."""
        assert _fallback_from_name("validate_email_address") == "email"

    def test_no_domain_word(self):
        """Returns 'misc' when no domain word found."""
        assert _fallback_from_name("do_something_special") == "misc"

    def test_first_match_wins(self):
        """First domain word in name is used."""
        assert _fallback_from_name("date_phone_email") == "date"

    def test_case_insensitive(self):
        """Name is lowercased for matching."""
        assert _fallback_from_name("NORMALIZE_PHONE") == "phone"


class TestRebalanceGroups:
    """Tests for _rebalance_groups() function."""

    def test_merge_small_groups(self):
        """Groups smaller than min_size are merged."""
        groups = {
            "big": [{"name": "f1", "docstring": "Tags: big"}] * 5,
            "tiny": [{"name": "f2", "docstring": "Tags: big"}],  # Only 1
        }
        result = _rebalance_groups(groups, min_size=2, max_size=40)
        # "tiny" should be merged into "big" due to tag overlap
        assert "tiny" not in result
        assert len(result["big"]) == 6

    def test_split_large_groups(self):
        """Groups larger than max_size are split."""
        large_funcs = [{"name": f"f{i}", "docstring": ""} for i in range(50)]
        groups = {"large": large_funcs}
        result = _rebalance_groups(groups, min_size=2, max_size=40)
        # Should be split into "large" (40) and "large_2" (10)
        assert "large" in result
        assert len(result["large"]) == 40
        assert "large_2" in result
        assert len(result["large_2"]) == 10

    def test_no_rebalance_needed(self):
        """Groups within bounds are unchanged."""
        groups = {
            "a": [{"name": "f1", "docstring": ""}] * 5,
            "b": [{"name": "f2", "docstring": ""}] * 10,
        }
        result = _rebalance_groups(groups, min_size=2, max_size=40)
        assert len(result["a"]) == 5
        assert len(result["b"]) == 10

    def test_all_orphans_creates_misc(self):
        """When all groups are too small, creates misc group."""
        groups = {
            "a": [{"name": "f1", "docstring": ""}],
            "b": [{"name": "f2", "docstring": ""}],
        }
        result = _rebalance_groups(groups, min_size=3, max_size=40)
        assert "misc" in result
        assert len(result["misc"]) == 2


class TestGroupBySalience:
    """Tests for group_by_salience() function."""

    def test_basic_grouping(self):
        """Functions with different primary tags go to different groups."""
        functions = [
            {"name": "f1", "docstring": "Fix phones.\nTags: phone, normalize"},
            {"name": "f2", "docstring": "Fix dates.\nTags: date, normalize"},
            {"name": "f3", "docstring": "More phones.\nTags: phone, normalize"},
        ]
        result = group_by_salience(functions, min_group=1, max_group=40)
        # "normalize" appears 3 times, so phone/date have higher IDF
        # Should have phone and date groups
        assert len(result) == 2
        # Check functions are in correct groups
        phone_names = {f["name"] for f in result.get("phone", [])}
        date_names = {f["name"] for f in result.get("date", [])}
        assert phone_names == {"f1", "f3"}
        assert date_names == {"f2"}

    def test_idf_selects_rare_tag(self):
        """Function with tags [common, rare] groups under 'rare'."""
        functions = [
            {"name": "f1", "docstring": "Desc.\nTags: common, rare"},
            {"name": "f2", "docstring": "Desc.\nTags: common"},
            {"name": "f3", "docstring": "Desc.\nTags: common"},
        ]
        result = group_by_salience(functions, min_group=1, max_group=40)
        # "rare" has higher IDF than "common", so f1 should be grouped under "rare"
        assert "rare" in result
        assert result["rare"][0]["name"] == "f1"

    def test_fallback_from_name(self):
        """Function without tags uses name extraction."""
        functions = [
            {"name": "normalize_phone_format", "docstring": "No tags here."},
            {"name": "fix_phone_number", "docstring": "Also no tags."},
        ]
        result = group_by_salience(functions, min_group=1, max_group=40)
        assert "phone" in result
        assert len(result["phone"]) == 2

    def test_rebalance_merges_small(self):
        """Groups with 1 function get merged."""
        functions = [
            {"name": "f1", "docstring": "Desc.\nTags: big, common"},
            {"name": "f2", "docstring": "Desc.\nTags: big, common"},
            {"name": "f3", "docstring": "Desc.\nTags: tiny, common"},  # Will be orphan
        ]
        result = group_by_salience(functions, min_group=2, max_group=40)
        # "tiny" group has only 1 function, should be merged
        assert "tiny" not in result
        # All functions should be in result somewhere
        total = sum(len(funcs) for funcs in result.values())
        assert total == 3

    def test_rebalance_splits_large(self):
        """Groups with 50+ functions get split."""
        functions = [
            {"name": f"f{i}", "docstring": "Same tag.\nTags: same"}
            for i in range(50)
        ]
        result = group_by_salience(functions, min_group=2, max_group=40)
        # Should be split into multiple groups
        total = sum(len(funcs) for funcs in result.values())
        assert total == 50
        # No group should exceed max_group
        for funcs in result.values():
            assert len(funcs) <= 40

    def test_empty_functions_list(self):
        """Returns empty dict for empty input."""
        assert group_by_salience([]) == {}

    def test_all_same_tags(self):
        """All functions have identical tags - still works."""
        functions = [
            {"name": f"f{i}", "docstring": "Desc.\nTags: same, identical"}
            for i in range(5)
        ]
        result = group_by_salience(functions, min_group=1, max_group=40)
        # All should be in one group (IDF scores are equal, so first tag alphabetically or by order)
        total = sum(len(funcs) for funcs in result.values())
        assert total == 5

    def test_no_tags_anywhere(self):
        """All functions use fallback."""
        functions = [
            {"name": "normalize_phone", "docstring": "No tags."},
            {"name": "fix_date", "docstring": "No tags."},
            {"name": "validate_email", "docstring": "No tags."},
        ]
        result = group_by_salience(functions, min_group=1, max_group=40)
        # Each should be in its own group (or merged if < min_group)
        total = sum(len(funcs) for funcs in result.values())
        assert total == 3

    def test_mixed_tagged_and_untagged(self):
        """Mix of tagged and untagged functions."""
        functions = [
            {"name": "f1", "docstring": "Has tags.\nTags: phone, common"},
            {"name": "normalize_phone", "docstring": "No tags here."},
            {"name": "f2", "docstring": "Has tags.\nTags: date, common"},
        ]
        result = group_by_salience(functions, min_group=1, max_group=40)
        # "common" appears twice, phone/date appear once (higher IDF)
        # f1 should go to "phone", normalize_phone also uses "phone" fallback
        phone_funcs = result.get("phone", [])
        assert len(phone_funcs) == 2

    def test_preserves_function_data(self):
        """Functions in result contain all original data."""
        functions = [
            {"name": "f1", "docstring": "Desc.\nTags: tag", "code": "def f1(): pass"},
        ]
        result = group_by_salience(functions, min_group=1, max_group=40)
        func = list(result.values())[0][0]
        assert func["name"] == "f1"
        assert func["code"] == "def f1(): pass"
        assert "Desc." in func["docstring"]


class TestFormatFunctionsForReview:
    """Tests for format_functions_for_review() function."""

    def test_basic_formatting(self):
        """Functions formatted correctly for prompt."""
        functions = [
            {
                "name": "normalize_phone",
                "docstring": "Normalize phones.\nTags: phone, normalize",
                "code": "def normalize_phone(r): pass",
            },
            {
                "name": "fix_dates",
                "docstring": "Fix dates.\nTags: date, fix",
                "code": "def fix_dates(r): pass",
            },
        ]
        result = format_functions_for_review(functions)
        assert "### Function 1: normalize_phone" in result
        assert "### Function 2: fix_dates" in result
        assert "Normalize phones." in result
        assert "def normalize_phone(r): pass" in result

    def test_empty_list(self):
        """Empty function list returns empty string."""
        result = format_functions_for_review([])
        assert result == ""

    def test_missing_fields(self):
        """Handles functions with missing fields."""
        functions = [{"name": "only_name"}]
        result = format_functions_for_review(functions)
        assert "only_name" in result


class TestParseConsolidationResponse:
    """Tests for parse_consolidation_response() function."""

    def test_basic_parsing(self):
        """Basic consolidation response parsed correctly."""
        xml = """
<consolidation_result>
  <merged_functions>
    <function>
      <name>merged_phone_handler</name>
      <original_names>phone_v1, phone_v2</original_names>
      <docstring>Handle all phone formats.
Tags: phone, normalize</docstring>
      <code>
```python
def merged_phone_handler(record):
    return record
```
      </code>
    </function>
  </merged_functions>

  <kept_unchanged>
    <function_name>unique_func</function_name>
  </kept_unchanged>

  <self_assessment>
    <complete>true</complete>
    <remaining_issues>none</remaining_issues>
    <confidence>high</confidence>
  </self_assessment>
</consolidation_result>
"""
        result = parse_consolidation_response(xml)
        assert len(result.merged_functions) == 1
        assert result.merged_functions[0]["name"] == "merged_phone_handler"
        assert result.merged_functions[0]["original_names"] == "phone_v1, phone_v2"
        assert "phone" in result.merged_functions[0]["docstring"].lower()
        assert result.kept_unchanged == ["unique_func"]
        assert result.assessment.complete is True
        assert result.assessment.remaining_issues == "none"
        assert result.assessment.confidence == "high"

    def test_multiple_merged_functions(self):
        """Parses multiple merged functions."""
        xml = """
<consolidation_result>
  <merged_functions>
    <function>
      <name>func1</name>
      <original_names>a, b</original_names>
      <docstring>Desc 1</docstring>
      <code>```python
def func1(): pass
```</code>
    </function>
    <function>
      <name>func2</name>
      <original_names>c, d</original_names>
      <docstring>Desc 2</docstring>
      <code>```python
def func2(): pass
```</code>
    </function>
  </merged_functions>
  <kept_unchanged></kept_unchanged>
  <self_assessment>
    <complete>false</complete>
    <remaining_issues>More work needed</remaining_issues>
    <confidence>medium</confidence>
  </self_assessment>
</consolidation_result>
"""
        result = parse_consolidation_response(xml)
        assert len(result.merged_functions) == 2
        assert result.assessment.complete is False
        assert result.assessment.confidence == "medium"

    def test_no_consolidation_result_raises(self):
        """Raises ParseError when no consolidation_result element."""
        with pytest.raises(ParseError, match="No <consolidation_result>"):
            parse_consolidation_response("<other>content</other>")

    def test_invalid_xml_raises(self):
        """Raises ParseError on malformed XML."""
        with pytest.raises(ParseError, match="Invalid XML"):
            parse_consolidation_response("<unclosed")

    def test_invalid_python_raises(self):
        """Raises ParseError when merged code has syntax error."""
        xml = """
<consolidation_result>
  <merged_functions>
    <function>
      <name>bad_func</name>
      <original_names>a</original_names>
      <docstring>Bad</docstring>
      <code>```python
def bad_func(
    # missing closing paren
```</code>
    </function>
  </merged_functions>
  <kept_unchanged></kept_unchanged>
  <self_assessment>
    <complete>true</complete>
    <remaining_issues>none</remaining_issues>
    <confidence>high</confidence>
  </self_assessment>
</consolidation_result>
"""
        with pytest.raises(ParseError, match="Invalid Python syntax"):
            parse_consolidation_response(xml)

    def test_default_assessment_when_missing(self):
        """Uses default assessment when self_assessment missing."""
        xml = """
<consolidation_result>
  <merged_functions></merged_functions>
  <kept_unchanged></kept_unchanged>
</consolidation_result>
"""
        result = parse_consolidation_response(xml)
        assert result.assessment.complete is False
        assert result.assessment.confidence == "low"

    def test_invalid_confidence_defaults_to_medium(self):
        """Invalid confidence value defaults to medium."""
        xml = """
<consolidation_result>
  <merged_functions></merged_functions>
  <kept_unchanged></kept_unchanged>
  <self_assessment>
    <complete>true</complete>
    <remaining_issues>none</remaining_issues>
    <confidence>invalid_value</confidence>
  </self_assessment>
</consolidation_result>
"""
        result = parse_consolidation_response(xml)
        assert result.assessment.confidence == "medium"


class TestConsolidateGroup:
    """Tests for consolidate_group() function."""

    def test_empty_functions_returns_empty(self):
        """Empty input returns empty list."""
        backend = MockBackend([])
        result, _ = consolidate_group([], backend)
        assert result == []
        assert backend.call_count == 0

    def test_calls_backend_with_prompt(self):
        """Backend receives properly formatted prompt."""
        response = """
<consolidation_result>
  <merged_functions></merged_functions>
  <kept_unchanged>
    <function_name>func1</function_name>
  </kept_unchanged>
  <self_assessment>
    <complete>true</complete>
    <remaining_issues>none</remaining_issues>
    <confidence>high</confidence>
  </self_assessment>
</consolidation_result>
"""
        backend = MockBackend([response])
        functions = [{"name": "func1", "docstring": "Desc", "code": "def func1(): pass"}]
        consolidate_group(functions, backend)
        assert backend.call_count == 1
        assert "func1" in backend.prompts[0]
        assert "1 functions" in backend.prompts[0]

    def test_keeps_unchanged_functions(self):
        """Functions marked as kept_unchanged are preserved."""
        response = """
<consolidation_result>
  <merged_functions></merged_functions>
  <kept_unchanged>
    <function_name>unique_func</function_name>
  </kept_unchanged>
  <self_assessment>
    <complete>true</complete>
    <remaining_issues>none</remaining_issues>
    <confidence>high</confidence>
  </self_assessment>
</consolidation_result>
"""
        backend = MockBackend([response])
        functions = [
            {"name": "unique_func", "docstring": "Unique", "code": "def unique_func(): pass"}
        ]
        result, _ = consolidate_group(functions, backend)
        assert len(result) == 1
        assert result[0]["name"] == "unique_func"


class TestConsolidateWithAgency:
    """Tests for consolidate_with_agency() function."""

    def test_terminates_on_complete_true(self):
        """Loop stops when assessment.complete is true."""
        response = """
<consolidation_result>
  <merged_functions></merged_functions>
  <kept_unchanged>
    <function_name>func1</function_name>
  </kept_unchanged>
  <self_assessment>
    <complete>true</complete>
    <remaining_issues>none</remaining_issues>
    <confidence>high</confidence>
  </self_assessment>
</consolidation_result>
"""
        backend = MockBackend([response])
        functions = [{"name": "func1", "docstring": "Desc", "code": "def func1(): pass"}]
        result = consolidate_with_agency(functions, backend, max_rounds=5)
        assert backend.call_count == 1  # Only one call, stopped immediately
        assert len(result) == 1

    def test_respects_max_rounds(self):
        """Loop stops at max_rounds even if not complete."""
        response = """
<consolidation_result>
  <merged_functions>
    <function>
      <name>merged</name>
      <original_names>a, b</original_names>
      <docstring>Merged</docstring>
      <code>```python
def merged(): pass
```</code>
    </function>
  </merged_functions>
  <kept_unchanged></kept_unchanged>
  <self_assessment>
    <complete>false</complete>
    <remaining_issues>Still more to merge</remaining_issues>
    <confidence>medium</confidence>
  </self_assessment>
</consolidation_result>
"""
        backend = MockBackend([response])
        functions = [
            {"name": "a", "docstring": "A", "code": "def a(): pass"},
            {"name": "b", "docstring": "B", "code": "def b(): pass"},
        ]
        result = consolidate_with_agency(functions, backend, max_rounds=3)
        # Should stop after checking that functions didn't decrease (stalled)
        # or after max_rounds
        assert backend.call_count <= 3

    def test_empty_input_returns_empty(self):
        """Empty input returns empty list without LLM call."""
        backend = MockBackend([])
        result = consolidate_with_agency([], backend)
        assert result == []
        assert backend.call_count == 0

    def test_merged_functions_have_valid_syntax(self):
        """Merged functions in result have valid Python syntax."""
        response = """
<consolidation_result>
  <merged_functions>
    <function>
      <name>merged_handler</name>
      <original_names>f1, f2</original_names>
      <docstring>Combined handler.
Tags: handler, merge</docstring>
      <code>```python
def merged_handler(record):
    value = record.get("field", "")
    return value.strip().lower()
```</code>
    </function>
  </merged_functions>
  <kept_unchanged></kept_unchanged>
  <self_assessment>
    <complete>true</complete>
    <remaining_issues>none</remaining_issues>
    <confidence>high</confidence>
  </self_assessment>
</consolidation_result>
"""
        backend = MockBackend([response])
        functions = [
            {"name": "f1", "docstring": "F1", "code": "def f1(): pass"},
            {"name": "f2", "docstring": "F2", "code": "def f2(): pass"},
        ]
        result = consolidate_with_agency(functions, backend)
        assert len(result) == 1
        # Verify the merged code is valid Python
        ast.parse(result[0]["code"])

    def test_preserves_original_on_error(self):
        """Returns original functions if LLM response causes error."""
        # Invalid response that will fail parsing
        backend = MockBackend(["not valid xml at all"])
        functions = [
            {"name": "safe_func", "docstring": "Safe", "code": "def safe_func(): pass"}
        ]
        result = consolidate_with_agency(functions, backend)
        # Should return original functions, not lose data
        assert len(result) == 1
        assert result[0]["name"] == "safe_func"

    def test_multi_round_consolidation(self):
        """Multiple rounds of consolidation work correctly."""
        # First round: merge f1 and f2 into merged1
        response1 = """
<consolidation_result>
  <merged_functions>
    <function>
      <name>merged1</name>
      <original_names>f1, f2</original_names>
      <docstring>Merged 1</docstring>
      <code>```python
def merged1(): pass
```</code>
    </function>
  </merged_functions>
  <kept_unchanged>
    <function_name>f3</function_name>
  </kept_unchanged>
  <self_assessment>
    <complete>false</complete>
    <remaining_issues>merged1 and f3 could be combined</remaining_issues>
    <confidence>medium</confidence>
  </self_assessment>
</consolidation_result>
"""
        # Second round: complete
        response2 = """
<consolidation_result>
  <merged_functions>
    <function>
      <name>final_merged</name>
      <original_names>merged1, f3</original_names>
      <docstring>Final merged</docstring>
      <code>```python
def final_merged(): pass
```</code>
    </function>
  </merged_functions>
  <kept_unchanged></kept_unchanged>
  <self_assessment>
    <complete>true</complete>
    <remaining_issues>none</remaining_issues>
    <confidence>high</confidence>
  </self_assessment>
</consolidation_result>
"""
        backend = MockBackend([response1, response2])
        functions = [
            {"name": "f1", "docstring": "F1", "code": "def f1(): pass"},
            {"name": "f2", "docstring": "F2", "code": "def f2(): pass"},
            {"name": "f3", "docstring": "F3", "code": "def f3(): pass"},
        ]
        result = consolidate_with_agency(functions, backend, max_rounds=5)
        # Should have done 2 rounds
        assert backend.call_count == 2
        assert len(result) == 1
        assert result[0]["name"] == "final_merged"


class TestAgentAssessmentDataclass:
    """Tests for AgentAssessment dataclass."""

    def test_dataclass_fields(self):
        """AgentAssessment has correct fields."""
        assessment = AgentAssessment(
            complete=True,
            remaining_issues="none",
            confidence="high",
        )
        assert assessment.complete is True
        assert assessment.remaining_issues == "none"
        assert assessment.confidence == "high"


class TestConsolidationResultDataclass:
    """Tests for ConsolidationResult dataclass."""

    def test_dataclass_fields(self):
        """ConsolidationResult has correct fields."""
        assessment = AgentAssessment(True, "none", "high")
        result = ConsolidationResult(
            merged_functions=[{"name": "merged"}],
            kept_unchanged=["kept1", "kept2"],
            assessment=assessment,
        )
        assert len(result.merged_functions) == 1
        assert result.kept_unchanged == ["kept1", "kept2"]
        assert result.assessment.complete is True


class TestDataCleanerIntegration:
    """Integration tests for DataCleaner with optimization."""

    def test_optimize_disabled_by_default(self, tmp_path):
        """optimize=False doesn't call optimizer."""
        # Create a simple test file
        test_file = tmp_path / "test.jsonl"
        test_file.write_text('{"name": "test"}\n')

        # Mock backend that returns "clean" immediately
        clean_response = """
<cleaning_analysis>
  <issues_detected></issues_detected>
  <chunk_status>clean</chunk_status>
</cleaning_analysis>
"""
        backend = MockBackend([clean_response])

        from recursive_cleaner.cleaner import DataCleaner

        cleaner = DataCleaner(
            llm_backend=backend,
            file_path=str(test_file),
            chunk_size=50,
            optimize=False,  # Default
        )
        cleaner.run()

        # No optimization callbacks should be fired
        # Just verify no errors occurred and optimization wasn't triggered
        assert cleaner.optimize is False

    def test_optimize_enabled_calls_optimizer(self, tmp_path):
        """optimize=True triggers optimization after chunks."""
        test_file = tmp_path / "test.jsonl"
        test_file.write_text('{"name": "test"}\n')

        # First call: generate 5 functions (one per iteration), then clean
        function_response = """
<cleaning_analysis>
  <issues_detected>
    <issue id="1" solved="false">Missing field</issue>
  </issues_detected>
  <function_to_generate>
    <name>fix_field_{n}</name>
    <docstring>Fix fields.
Tags: field, fix</docstring>
    <code>
```python
def fix_field_{n}(record):
    return record
```
    </code>
  </function_to_generate>
  <chunk_status>needs_more_work</chunk_status>
</cleaning_analysis>
"""
        clean_response = """
<cleaning_analysis>
  <issues_detected></issues_detected>
  <chunk_status>clean</chunk_status>
</cleaning_analysis>
"""
        # Consolidation response
        consolidation_response = """
<consolidation_result>
  <merged_functions>
    <function>
      <name>fix_all_fields</name>
      <original_names>fix_field_0, fix_field_1</original_names>
      <docstring>Fix all fields.
Tags: field, fix</docstring>
      <code>```python
def fix_all_fields(record):
    return record
```</code>
    </function>
  </merged_functions>
  <kept_unchanged></kept_unchanged>
  <self_assessment>
    <complete>true</complete>
    <remaining_issues>none</remaining_issues>
    <confidence>high</confidence>
  </self_assessment>
</consolidation_result>
"""
        # Create responses: 5 function generations + clean + consolidation
        responses = [function_response.replace("{n}", str(i)) for i in range(5)]
        responses.append(clean_response)
        responses.append(consolidation_response)

        backend = MockBackend(responses)

        from recursive_cleaner.cleaner import DataCleaner

        cleaner = DataCleaner(
            llm_backend=backend,
            file_path=str(test_file),
            chunk_size=50,
            max_iterations=6,  # Allow 6 iterations to generate 5 funcs + clean
            optimize=True,
            optimize_threshold=5,  # Lowered threshold to 5
            validate_runtime=False,
        )
        cleaner.run()

        # Should have fewer functions after optimization
        assert len(cleaner.functions) == 1
        assert cleaner.functions[0]["name"] == "fix_all_fields"

    def test_optimize_skipped_below_threshold(self, tmp_path):
        """<10 functions doesn't trigger optimization."""
        test_file = tmp_path / "test.jsonl"
        test_file.write_text('{"name": "test"}\n')

        # Generate only 5 functions, then clean
        function_response = """
<cleaning_analysis>
  <issues_detected>
    <issue id="1" solved="false">Missing field</issue>
  </issues_detected>
  <function_to_generate>
    <name>fix_field_{n}</name>
    <docstring>Fix fields.
Tags: field, fix</docstring>
    <code>
```python
def fix_field_{n}(record):
    return record
```
    </code>
  </function_to_generate>
  <chunk_status>needs_more_work</chunk_status>
</cleaning_analysis>
"""
        clean_response = """
<cleaning_analysis>
  <issues_detected></issues_detected>
  <chunk_status>clean</chunk_status>
</cleaning_analysis>
"""
        responses = [function_response.replace("{n}", str(i)) for i in range(5)]
        responses.append(clean_response)

        backend = MockBackend(responses)

        from recursive_cleaner.cleaner import DataCleaner

        cleaner = DataCleaner(
            llm_backend=backend,
            file_path=str(test_file),
            chunk_size=50,
            optimize=True,
            optimize_threshold=10,  # Threshold is 10, we only have 5
            validate_runtime=False,
        )
        cleaner.run()

        # Should still have 5 functions (no optimization)
        assert len(cleaner.functions) == 5

    def test_optimize_callbacks_fired(self, tmp_path):
        """Progress callbacks include optimize events."""
        test_file = tmp_path / "test.jsonl"
        test_file.write_text('{"name": "test"}\n')

        # Generate 5 functions + clean + consolidation
        function_response = """
<cleaning_analysis>
  <issues_detected>
    <issue id="1" solved="false">Missing field</issue>
  </issues_detected>
  <function_to_generate>
    <name>fix_field_{n}</name>
    <docstring>Fix fields.
Tags: field, fix</docstring>
    <code>
```python
def fix_field_{n}(record):
    return record
```
    </code>
  </function_to_generate>
  <chunk_status>needs_more_work</chunk_status>
</cleaning_analysis>
"""
        clean_response = """
<cleaning_analysis>
  <issues_detected></issues_detected>
  <chunk_status>clean</chunk_status>
</cleaning_analysis>
"""
        consolidation_response = """
<consolidation_result>
  <merged_functions>
    <function>
      <name>fix_all</name>
      <original_names>all</original_names>
      <docstring>Fix all.
Tags: field</docstring>
      <code>```python
def fix_all(record):
    return record
```</code>
    </function>
  </merged_functions>
  <kept_unchanged></kept_unchanged>
  <self_assessment>
    <complete>true</complete>
    <remaining_issues>none</remaining_issues>
    <confidence>high</confidence>
  </self_assessment>
</consolidation_result>
"""
        responses = [function_response.replace("{n}", str(i)) for i in range(5)]
        responses.append(clean_response)
        responses.append(consolidation_response)

        backend = MockBackend(responses)

        events = []

        def on_progress(event):
            events.append(event)

        from recursive_cleaner.cleaner import DataCleaner

        cleaner = DataCleaner(
            llm_backend=backend,
            file_path=str(test_file),
            chunk_size=50,
            max_iterations=6,  # Allow 6 iterations to generate 5 funcs + clean
            optimize=True,
            optimize_threshold=5,  # Lowered threshold to 5
            validate_runtime=False,
            on_progress=on_progress,
        )
        cleaner.run()

        # Check that optimize events were fired
        event_types = [e["type"] for e in events]
        assert "optimize_start" in event_types
        assert "optimize_group" in event_types
        assert "optimize_complete" in event_types

        # Check optimize_start has function_count
        optimize_start = next(e for e in events if e["type"] == "optimize_start")
        assert optimize_start["function_count"] == 5

        # Check optimize_complete has original and final
        optimize_complete = next(e for e in events if e["type"] == "optimize_complete")
        assert optimize_complete["original"] == 5
        assert optimize_complete["final"] == 1

    def test_optimize_reduces_function_count(self, tmp_path):
        """End-to-end: functions actually consolidated."""
        test_file = tmp_path / "test.jsonl"
        test_file.write_text('{"phone": "555-1234"}\n{"phone": "555-5678"}\n')

        # Generate functions for phone handling
        phone_func1 = """
<cleaning_analysis>
  <issues_detected>
    <issue id="1" solved="false">Phone format issue 1</issue>
  </issues_detected>
  <function_to_generate>
    <name>normalize_phone_v1</name>
    <docstring>Normalize phones version 1.
Tags: phone, normalize</docstring>
    <code>
```python
def normalize_phone_v1(record):
    return record
```
    </code>
  </function_to_generate>
  <chunk_status>needs_more_work</chunk_status>
</cleaning_analysis>
"""
        phone_funcs = []
        for i in range(5):
            phone_funcs.append(phone_func1.replace("v1", f"v{i}").replace("version 1", f"version {i}"))

        clean_response = """
<cleaning_analysis>
  <issues_detected></issues_detected>
  <chunk_status>clean</chunk_status>
</cleaning_analysis>
"""
        # Consolidation merges all phone functions into one
        consolidation_response = """
<consolidation_result>
  <merged_functions>
    <function>
      <name>normalize_phone_all</name>
      <original_names>all phone funcs</original_names>
      <docstring>Normalize all phone formats.
Tags: phone, normalize</docstring>
      <code>```python
def normalize_phone_all(record):
    phone = record.get("phone", "")
    return {**record, "phone": phone.replace("-", "")}
```</code>
    </function>
  </merged_functions>
  <kept_unchanged></kept_unchanged>
  <self_assessment>
    <complete>true</complete>
    <remaining_issues>none</remaining_issues>
    <confidence>high</confidence>
  </self_assessment>
</consolidation_result>
"""
        responses = phone_funcs + [clean_response, consolidation_response]
        backend = MockBackend(responses)

        from recursive_cleaner.cleaner import DataCleaner

        cleaner = DataCleaner(
            llm_backend=backend,
            file_path=str(test_file),
            chunk_size=50,
            max_iterations=6,  # Allow 6 iterations to generate 5 funcs + clean
            optimize=True,
            optimize_threshold=5,  # Lowered threshold to 5
            validate_runtime=False,
        )
        cleaner.run()

        # Should have consolidated to 1 function
        assert len(cleaner.functions) == 1
        assert "phone" in cleaner.functions[0]["name"]

    def test_optimize_state_serialization(self, tmp_path):
        """State file includes optimize parameters."""
        import json

        test_file = tmp_path / "test.jsonl"
        test_file.write_text('{"name": "test"}\n')
        state_file = tmp_path / "state.json"

        clean_response = """
<cleaning_analysis>
  <issues_detected></issues_detected>
  <chunk_status>clean</chunk_status>
</cleaning_analysis>
"""
        backend = MockBackend([clean_response])

        from recursive_cleaner.cleaner import DataCleaner

        cleaner = DataCleaner(
            llm_backend=backend,
            file_path=str(test_file),
            chunk_size=50,
            optimize=True,
            optimize_threshold=15,
            state_file=str(state_file),
        )
        cleaner.run()

        # Check state file
        with open(state_file) as f:
            state = json.load(f)

        assert state["optimize"] is True
        assert state["optimize_threshold"] == 15
        assert state["version"] == "0.5.0"


class TestParseSaturationResponse:
    """Tests for parse_saturation_response() function."""

    def test_basic_parsing(self):
        """Basic saturation response parsed correctly."""
        from recursive_cleaner.response import parse_saturation_response

        xml = """
<saturation_assessment>
  <saturated>true</saturated>
  <confidence>high</confidence>
  <reasoning>Last 20 chunks produced only 1 new function</reasoning>
  <recommendation>stop</recommendation>
</saturation_assessment>
"""
        result = parse_saturation_response(xml)
        assert result.saturated is True
        assert result.confidence == "high"
        assert "20 chunks" in result.reasoning
        assert result.recommendation == "stop"

    def test_not_saturated(self):
        """Parse response indicating not saturated."""
        from recursive_cleaner.response import parse_saturation_response

        xml = """
<saturation_assessment>
  <saturated>false</saturated>
  <confidence>medium</confidence>
  <reasoning>Still seeing new patterns</reasoning>
  <recommendation>continue</recommendation>
</saturation_assessment>
"""
        result = parse_saturation_response(xml)
        assert result.saturated is False
        assert result.confidence == "medium"
        assert result.recommendation == "continue"

    def test_invalid_xml_raises(self):
        """Raises ParseError on malformed XML."""
        from recursive_cleaner.response import parse_saturation_response

        with pytest.raises(ParseError, match="Invalid XML"):
            parse_saturation_response("<unclosed")

    def test_missing_element_raises(self):
        """Raises ParseError when no saturation_assessment element."""
        from recursive_cleaner.response import parse_saturation_response

        with pytest.raises(ParseError, match="No <saturation_assessment>"):
            parse_saturation_response("<other>content</other>")

    def test_defaults_for_missing_fields(self):
        """Uses defaults for missing fields."""
        from recursive_cleaner.response import parse_saturation_response

        xml = """
<saturation_assessment>
  <saturated>true</saturated>
</saturation_assessment>
"""
        result = parse_saturation_response(xml)
        assert result.saturated is True
        assert result.confidence == "medium"  # default
        assert result.reasoning == ""  # default
        assert result.recommendation == "continue"  # default

    def test_invalid_confidence_defaults_to_medium(self):
        """Invalid confidence value defaults to medium."""
        from recursive_cleaner.response import parse_saturation_response

        xml = """
<saturation_assessment>
  <saturated>false</saturated>
  <confidence>invalid_value</confidence>
  <reasoning>Test</reasoning>
  <recommendation>continue</recommendation>
</saturation_assessment>
"""
        result = parse_saturation_response(xml)
        assert result.confidence == "medium"

    def test_invalid_recommendation_defaults_to_continue(self):
        """Invalid recommendation defaults to continue."""
        from recursive_cleaner.response import parse_saturation_response

        xml = """
<saturation_assessment>
  <saturated>true</saturated>
  <confidence>high</confidence>
  <reasoning>Test</reasoning>
  <recommendation>invalid_value</recommendation>
</saturation_assessment>
"""
        result = parse_saturation_response(xml)
        assert result.recommendation == "continue"


class TestEarlyTermination:
    """Tests for early termination (saturation detection)."""

    def test_saturation_check_disabled_by_default(self, tmp_path):
        """early_termination=False doesn't check saturation."""
        test_file = tmp_path / "test.jsonl"
        # Create 30 records to have enough chunks
        test_file.write_text("\n".join(['{"name": "test"}'] * 30))

        clean_response = """
<cleaning_analysis>
  <issues_detected></issues_detected>
  <chunk_status>clean</chunk_status>
</cleaning_analysis>
"""
        backend = MockBackend([clean_response] * 30)

        from recursive_cleaner.cleaner import DataCleaner

        events = []
        cleaner = DataCleaner(
            llm_backend=backend,
            file_path=str(test_file),
            chunk_size=1,  # 1 record per chunk = 30 chunks
            early_termination=False,  # Disabled
            saturation_check_interval=5,
            on_progress=lambda e: events.append(e),
        )
        cleaner.run()

        # No saturation_check events should be fired
        event_types = [e["type"] for e in events]
        assert "saturation_check" not in event_types
        assert "early_termination" not in event_types

    def test_saturation_check_at_interval(self, tmp_path):
        """Saturation check runs every N chunks when enabled."""
        test_file = tmp_path / "test.jsonl"
        # Create 25 records
        test_file.write_text("\n".join(['{"name": "test"}'] * 25))

        clean_response = """
<cleaning_analysis>
  <issues_detected></issues_detected>
  <chunk_status>clean</chunk_status>
</cleaning_analysis>
"""
        # Response for saturation check - not saturated
        saturation_response = """
<saturation_assessment>
  <saturated>false</saturated>
  <confidence>medium</confidence>
  <reasoning>More patterns may exist</reasoning>
  <recommendation>continue</recommendation>
</saturation_assessment>
"""
        # Need responses for chunks + saturation checks at intervals
        # With chunk_size=1 and 25 records, we have 25 chunks
        # With interval=10, check at chunk 10 and 20
        responses = []
        for i in range(25):
            responses.append(clean_response)
            # Add saturation check responses after chunk 9 (index 10) and 19 (index 20)
            if (i + 1) % 10 == 0 and i > 0:
                responses.append(saturation_response)

        backend = MockBackend(responses)

        from recursive_cleaner.cleaner import DataCleaner

        events = []
        cleaner = DataCleaner(
            llm_backend=backend,
            file_path=str(test_file),
            chunk_size=1,
            early_termination=True,
            saturation_check_interval=10,
            on_progress=lambda e: events.append(e),
        )
        cleaner.run()

        # Should have saturation_check events
        saturation_events = [e for e in events if e["type"] == "saturation_check"]
        assert len(saturation_events) == 2  # At chunk 10 and 20

    def test_early_stop_on_saturated(self, tmp_path):
        """Processing stops when saturated=true with high confidence."""
        test_file = tmp_path / "test.jsonl"
        # Create 50 records
        test_file.write_text("\n".join(['{"name": "test"}'] * 50))

        clean_response = """
<cleaning_analysis>
  <issues_detected></issues_detected>
  <chunk_status>clean</chunk_status>
</cleaning_analysis>
"""
        # Response for saturation check - saturated!
        saturation_response = """
<saturation_assessment>
  <saturated>true</saturated>
  <confidence>high</confidence>
  <reasoning>No new functions in last 10 chunks</reasoning>
  <recommendation>stop</recommendation>
</saturation_assessment>
"""
        # First 10 chunks clean, then saturation check says stop
        responses = [clean_response] * 10 + [saturation_response]

        backend = MockBackend(responses)

        from recursive_cleaner.cleaner import DataCleaner

        events = []
        cleaner = DataCleaner(
            llm_backend=backend,
            file_path=str(test_file),
            chunk_size=1,
            early_termination=True,
            saturation_check_interval=10,
            on_progress=lambda e: events.append(e),
        )
        cleaner.run()

        # Should have early_termination event
        event_types = [e["type"] for e in events]
        assert "early_termination" in event_types

        # Should have stopped at chunk 10 (not processed all 50)
        chunk_done_events = [e for e in events if e["type"] == "chunk_done"]
        assert len(chunk_done_events) < 50

    def test_continue_on_not_saturated(self, tmp_path):
        """Processing continues when saturated=false."""
        test_file = tmp_path / "test.jsonl"
        # Create 25 records
        test_file.write_text("\n".join(['{"name": "test"}'] * 25))

        clean_response = """
<cleaning_analysis>
  <issues_detected></issues_detected>
  <chunk_status>clean</chunk_status>
</cleaning_analysis>
"""
        # Response for saturation check - not saturated
        saturation_response = """
<saturation_assessment>
  <saturated>false</saturated>
  <confidence>high</confidence>
  <reasoning>Still seeing variation</reasoning>
  <recommendation>continue</recommendation>
</saturation_assessment>
"""
        # Interleave responses
        responses = []
        for i in range(25):
            responses.append(clean_response)
            if (i + 1) % 10 == 0 and i > 0:
                responses.append(saturation_response)

        backend = MockBackend(responses)

        from recursive_cleaner.cleaner import DataCleaner

        events = []
        cleaner = DataCleaner(
            llm_backend=backend,
            file_path=str(test_file),
            chunk_size=1,
            early_termination=True,
            saturation_check_interval=10,
            on_progress=lambda e: events.append(e),
        )
        cleaner.run()

        # Should NOT have early_termination event
        event_types = [e["type"] for e in events]
        assert "early_termination" not in event_types

        # Should have processed all 25 chunks
        chunk_start_events = [e for e in events if e["type"] == "chunk_start"]
        assert len(chunk_start_events) == 25

    def test_low_confidence_does_not_stop(self, tmp_path):
        """Saturated=true with low confidence continues processing."""
        test_file = tmp_path / "test.jsonl"
        test_file.write_text("\n".join(['{"name": "test"}'] * 25))

        clean_response = """
<cleaning_analysis>
  <issues_detected></issues_detected>
  <chunk_status>clean</chunk_status>
</cleaning_analysis>
"""
        # Response for saturation check - saturated but LOW confidence
        saturation_response = """
<saturation_assessment>
  <saturated>true</saturated>
  <confidence>low</confidence>
  <reasoning>Not sure, too little data</reasoning>
  <recommendation>stop</recommendation>
</saturation_assessment>
"""
        responses = []
        for i in range(25):
            responses.append(clean_response)
            if (i + 1) % 10 == 0 and i > 0:
                responses.append(saturation_response)

        backend = MockBackend(responses)

        from recursive_cleaner.cleaner import DataCleaner

        events = []
        cleaner = DataCleaner(
            llm_backend=backend,
            file_path=str(test_file),
            chunk_size=1,
            early_termination=True,
            saturation_check_interval=10,
            on_progress=lambda e: events.append(e),
        )
        cleaner.run()

        # Should NOT have early_termination event (low confidence)
        event_types = [e["type"] for e in events]
        assert "early_termination" not in event_types

        # Should have processed all 25 chunks
        chunk_start_events = [e for e in events if e["type"] == "chunk_start"]
        assert len(chunk_start_events) == 25

    def test_state_includes_early_termination_params(self, tmp_path):
        """State file includes early_termination parameters."""
        import json

        test_file = tmp_path / "test.jsonl"
        test_file.write_text('{"name": "test"}\n')
        state_file = tmp_path / "state.json"

        clean_response = """
<cleaning_analysis>
  <issues_detected></issues_detected>
  <chunk_status>clean</chunk_status>
</cleaning_analysis>
"""
        backend = MockBackend([clean_response])

        from recursive_cleaner.cleaner import DataCleaner

        cleaner = DataCleaner(
            llm_backend=backend,
            file_path=str(test_file),
            chunk_size=50,
            early_termination=True,
            saturation_check_interval=15,
            state_file=str(state_file),
        )
        cleaner.run()

        # Check state file
        with open(state_file) as f:
            state = json.load(f)

        assert state["early_termination"] is True
        assert state["saturation_check_interval"] == 15

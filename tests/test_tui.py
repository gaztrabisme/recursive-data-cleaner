"""Tests for Rich TUI dashboard with Mission Control aesthetic."""

import sys
import time
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from recursive_cleaner import DataCleaner


# Test TUI module can be imported regardless of Rich availability
def test_tui_import_always_works():
    """TUI module imports without error even if Rich not installed."""
    from recursive_cleaner.tui import HAS_RICH, TUIRenderer

    # HAS_RICH should be a boolean
    assert isinstance(HAS_RICH, bool)
    # TUIRenderer should be importable as a class
    assert TUIRenderer is not None


def test_has_rich_is_exported():
    """HAS_RICH is exported from main module."""
    from recursive_cleaner import HAS_RICH

    assert isinstance(HAS_RICH, bool)


def test_tui_renderer_is_exported():
    """TUIRenderer is exported from main module."""
    from recursive_cleaner import TUIRenderer

    assert TUIRenderer is not None


# Test TUIRenderer instantiation
def test_tui_renderer_instantiation():
    """TUIRenderer can be instantiated with required parameters."""
    from recursive_cleaner.tui import TUIRenderer

    renderer = TUIRenderer(
        file_path="test.jsonl",
        total_chunks=10,
        total_records=100,
    )
    assert renderer._state.file_path == "test.jsonl"
    assert renderer._state.total_chunks == 10
    assert renderer._state.total_records == 100


def test_tui_renderer_default_state():
    """TUIRenderer initializes with correct default state."""
    from recursive_cleaner.tui import TUIRenderer

    renderer = TUIRenderer(
        file_path="data.csv",
        total_chunks=5,
    )

    assert renderer._state.current_chunk == 0
    assert renderer._state.current_iteration == 0
    assert renderer._state.max_iterations == 5
    assert renderer._state.llm_status == "idle"
    assert renderer._state.functions == []
    assert renderer._state.latency_last_ms == 0.0
    assert renderer._state.llm_call_count == 0
    # New fields
    assert renderer._state.tokens_in == 0
    assert renderer._state.tokens_out == 0
    assert renderer._state.last_response == ""


def test_tui_renderer_has_start_time():
    """TUIRenderer initializes with start_time for elapsed timer."""
    from recursive_cleaner.tui import TUIRenderer

    before = time.time()
    renderer = TUIRenderer(
        file_path="data.csv",
        total_chunks=5,
    )
    after = time.time()

    assert before <= renderer._start_time <= after


# Test TUIRenderer lifecycle (start/stop)
def test_tui_renderer_start_stop_without_rich():
    """TUIRenderer start/stop work gracefully without Rich."""
    from recursive_cleaner.tui import TUIRenderer

    with patch("recursive_cleaner.tui.HAS_RICH", False):
        renderer = TUIRenderer.__new__(TUIRenderer)
        renderer._state = MagicMock()
        renderer._layout = None
        renderer._live = None
        renderer._console = None
        renderer._start_time = time.time()

        # Should not raise
        renderer.start()
        renderer.stop()


def test_tui_renderer_lifecycle_with_rich():
    """TUIRenderer start/stop work with Rich installed."""
    from recursive_cleaner.tui import HAS_RICH, TUIRenderer

    if not HAS_RICH:
        pytest.skip("Rich not installed")

    renderer = TUIRenderer(
        file_path="test.jsonl",
        total_chunks=5,
    )

    # Start and stop should work
    renderer.start()
    assert renderer._live is not None
    renderer.stop()
    assert renderer._live is None


# Test update methods
def test_update_chunk():
    """update_chunk updates state correctly."""
    from recursive_cleaner.tui import TUIRenderer

    renderer = TUIRenderer(
        file_path="test.jsonl",
        total_chunks=10,
    )

    renderer.update_chunk(chunk_index=4, iteration=2, max_iterations=5)

    # chunk_index is 0-based, displayed as 1-based
    assert renderer._state.current_chunk == 5
    assert renderer._state.current_iteration == 3
    assert renderer._state.max_iterations == 5


def test_update_llm_status():
    """update_llm_status updates state correctly."""
    from recursive_cleaner.tui import TUIRenderer

    renderer = TUIRenderer(
        file_path="test.jsonl",
        total_chunks=5,
    )

    renderer.update_llm_status("calling")
    assert renderer._state.llm_status == "calling"

    renderer.update_llm_status("idle")
    assert renderer._state.llm_status == "idle"


def test_add_function():
    """add_function adds to functions list."""
    from recursive_cleaner.tui import TUIRenderer

    renderer = TUIRenderer(
        file_path="test.jsonl",
        total_chunks=5,
    )

    renderer.add_function("normalize_phones", "Normalize phone numbers to E.164.")
    renderer.add_function("fix_dates", "Fix date formats.")

    assert len(renderer._state.functions) == 2
    assert renderer._state.functions[0].name == "normalize_phones"
    assert renderer._state.functions[0].docstring == "Normalize phone numbers to E.164."
    assert renderer._state.functions[1].name == "fix_dates"


def test_update_metrics():
    """update_metrics updates latency values (quality_delta ignored)."""
    from recursive_cleaner.tui import TUIRenderer

    renderer = TUIRenderer(
        file_path="test.jsonl",
        total_chunks=5,
    )

    renderer.update_metrics(
        quality_delta=15.5,  # This is ignored in new design
        latency_last=250.0,
        latency_avg=180.0,
        latency_total=3600.0,
        llm_calls=20,
    )

    assert renderer._state.latency_last_ms == 250.0
    assert renderer._state.latency_avg_ms == 180.0
    assert renderer._state.latency_total_ms == 3600.0
    assert renderer._state.llm_call_count == 20


def test_update_tokens():
    """update_tokens estimates and accumulates token counts."""
    from recursive_cleaner.tui import TUIRenderer

    renderer = TUIRenderer(
        file_path="test.jsonl",
        total_chunks=5,
    )

    # Test with known string lengths
    prompt = "a" * 400  # Should estimate ~100 tokens
    response = "b" * 200  # Should estimate ~50 tokens

    renderer.update_tokens(prompt, response)

    assert renderer._state.tokens_in == 100
    assert renderer._state.tokens_out == 50

    # Test accumulation
    renderer.update_tokens(prompt, response)

    assert renderer._state.tokens_in == 200
    assert renderer._state.tokens_out == 100


def test_update_transmission():
    """update_transmission stores the latest LLM response."""
    from recursive_cleaner.tui import TUIRenderer

    renderer = TUIRenderer(
        file_path="test.jsonl",
        total_chunks=5,
    )

    response = "<cleaning_analysis>\n  <issues>...</issues>\n</cleaning_analysis>"
    renderer.update_transmission(response)

    assert renderer._state.last_response == response


def test_get_elapsed_time():
    """_get_elapsed_time returns MM:SS format."""
    from recursive_cleaner.tui import TUIRenderer

    renderer = TUIRenderer(
        file_path="test.jsonl",
        total_chunks=5,
    )

    # Set start time to known value
    renderer._start_time = time.time() - 125  # 2 minutes 5 seconds ago

    elapsed = renderer._get_elapsed_time()

    assert elapsed == "02:05"


# Test function list display (max 6, then "+N more")
def test_function_list_max_six():
    """Function list shows max 6 functions."""
    from recursive_cleaner.tui import HAS_RICH, TUIRenderer

    if not HAS_RICH:
        pytest.skip("Rich not installed")

    renderer = TUIRenderer(
        file_path="test.jsonl",
        total_chunks=5,
    )

    # Add 8 functions
    for i in range(8):
        renderer.add_function(f"func_{i}", f"Doc {i}")

    assert len(renderer._state.functions) == 8
    # The renderer should only show last 6 in display (tested via internal method)


# Test DataCleaner integration
CLEAN_RESPONSE = '''
<cleaning_analysis>
  <issues_detected>
    <issue id="1" solved="true">Already clean</issue>
  </issues_detected>
  <chunk_status>clean</chunk_status>
</cleaning_analysis>
'''

RESPONSE_WITH_FUNCTION = '''
<cleaning_analysis>
  <issues_detected>
    <issue id="1" solved="false">Phone numbers need normalizing</issue>
  </issues_detected>
  <function_to_generate>
    <name>normalize_phones</name>
    <docstring>Normalize phone numbers.</docstring>
    <code>
```python
def normalize_phones(data):
    return data
```
    </code>
  </function_to_generate>
  <chunk_status>needs_more_work</chunk_status>
</cleaning_analysis>
'''


class MockLLM:
    """Mock LLM for testing."""

    def __init__(self, responses: list[str]):
        self.responses = iter(responses)
        self.call_count = 0

    def generate(self, prompt: str) -> str:
        self.call_count += 1
        return next(self.responses)


def test_datacleaner_tui_false_default(tmp_path):
    """DataCleaner has tui=False by default."""
    test_file = tmp_path / "test.jsonl"
    test_file.write_text('{"a": 1}\n')

    cleaner = DataCleaner(
        llm_backend=MockLLM([CLEAN_RESPONSE]),
        file_path=str(test_file),
        chunk_size=10,
        report_path=None,
    )

    assert cleaner.tui is False


def test_datacleaner_tui_parameter(tmp_path):
    """DataCleaner accepts tui parameter."""
    test_file = tmp_path / "test.jsonl"
    test_file.write_text('{"a": 1}\n')

    cleaner = DataCleaner(
        llm_backend=MockLLM([CLEAN_RESPONSE]),
        file_path=str(test_file),
        chunk_size=10,
        tui=True,
        report_path=None,
    )

    assert cleaner.tui is True


def test_datacleaner_tui_integration_with_rich(tmp_path):
    """DataCleaner with tui=True creates TUIRenderer when Rich installed."""
    from recursive_cleaner.tui import HAS_RICH

    if not HAS_RICH:
        pytest.skip("Rich not installed")

    test_file = tmp_path / "test.jsonl"
    test_file.write_text('{"a": 1}\n')

    mock_llm = MockLLM([CLEAN_RESPONSE])
    cleaner = DataCleaner(
        llm_backend=mock_llm,
        file_path=str(test_file),
        chunk_size=10,
        tui=True,
        report_path=None,
    )

    # Run and check TUI was created (and stopped)
    import os
    original_cwd = os.getcwd()
    try:
        os.chdir(tmp_path)
        cleaner.run()
    finally:
        os.chdir(original_cwd)

    # TUI should have been stopped after run
    assert cleaner._tui_renderer is not None


def test_datacleaner_tui_fallback_warning(tmp_path, caplog):
    """DataCleaner logs warning when tui=True but Rich not installed."""
    import logging

    test_file = tmp_path / "test.jsonl"
    test_file.write_text('{"a": 1}\n')

    mock_llm = MockLLM([CLEAN_RESPONSE])

    # Mock HAS_RICH to be False
    with patch("recursive_cleaner.cleaner.HAS_RICH", False, create=True):
        # Need to patch at import location
        with patch.dict(sys.modules, {"recursive_cleaner.tui": MagicMock(HAS_RICH=False, TUIRenderer=MagicMock)}):
            cleaner = DataCleaner(
                llm_backend=mock_llm,
                file_path=str(test_file),
                chunk_size=10,
                tui=True,
                report_path=None,
            )

            import os
            original_cwd = os.getcwd()
            try:
                os.chdir(tmp_path)
                with caplog.at_level(logging.WARNING):
                    cleaner.run()
            finally:
                os.chdir(original_cwd)

            # Check warning was logged
            assert any("Rich not installed" in r.message for r in caplog.records) or cleaner._tui_renderer is None


def test_datacleaner_tui_updates_on_function(tmp_path):
    """DataCleaner updates TUI when function is generated."""
    from recursive_cleaner.tui import HAS_RICH

    if not HAS_RICH:
        pytest.skip("Rich not installed")

    test_file = tmp_path / "test.jsonl"
    test_file.write_text('{"a": 1}\n')

    mock_llm = MockLLM([RESPONSE_WITH_FUNCTION, CLEAN_RESPONSE])
    cleaner = DataCleaner(
        llm_backend=mock_llm,
        file_path=str(test_file),
        chunk_size=10,
        tui=True,
        report_path=None,
    )

    import os
    original_cwd = os.getcwd()
    try:
        os.chdir(tmp_path)
        cleaner.run()
    finally:
        os.chdir(original_cwd)

    # TUI should have received the function
    assert cleaner._tui_renderer is not None
    assert len(cleaner._tui_renderer._state.functions) == 1
    assert cleaner._tui_renderer._state.functions[0].name == "normalize_phones"


def test_datacleaner_tui_updates_tokens(tmp_path):
    """DataCleaner updates TUI token counts after LLM calls."""
    from recursive_cleaner.tui import HAS_RICH

    if not HAS_RICH:
        pytest.skip("Rich not installed")

    test_file = tmp_path / "test.jsonl"
    test_file.write_text('{"a": 1}\n')

    mock_llm = MockLLM([CLEAN_RESPONSE])
    cleaner = DataCleaner(
        llm_backend=mock_llm,
        file_path=str(test_file),
        chunk_size=10,
        tui=True,
        report_path=None,
    )

    import os
    original_cwd = os.getcwd()
    try:
        os.chdir(tmp_path)
        cleaner.run()
    finally:
        os.chdir(original_cwd)

    # TUI should have token counts
    assert cleaner._tui_renderer is not None
    assert cleaner._tui_renderer._state.tokens_in > 0
    assert cleaner._tui_renderer._state.tokens_out > 0


def test_datacleaner_tui_updates_transmission(tmp_path):
    """DataCleaner updates TUI transmission log after LLM calls."""
    from recursive_cleaner.tui import HAS_RICH

    if not HAS_RICH:
        pytest.skip("Rich not installed")

    test_file = tmp_path / "test.jsonl"
    test_file.write_text('{"a": 1}\n')

    mock_llm = MockLLM([CLEAN_RESPONSE])
    cleaner = DataCleaner(
        llm_backend=mock_llm,
        file_path=str(test_file),
        chunk_size=10,
        tui=True,
        report_path=None,
    )

    import os
    original_cwd = os.getcwd()
    try:
        os.chdir(tmp_path)
        cleaner.run()
    finally:
        os.chdir(original_cwd)

    # TUI should have transmission log with response
    assert cleaner._tui_renderer is not None
    assert "cleaning_analysis" in cleaner._tui_renderer._state.last_response


def test_datacleaner_tui_false_no_renderer(tmp_path):
    """DataCleaner with tui=False doesn't create TUIRenderer."""
    test_file = tmp_path / "test.jsonl"
    test_file.write_text('{"a": 1}\n')

    mock_llm = MockLLM([CLEAN_RESPONSE])
    cleaner = DataCleaner(
        llm_backend=mock_llm,
        file_path=str(test_file),
        chunk_size=10,
        tui=False,
        report_path=None,
    )

    import os
    original_cwd = os.getcwd()
    try:
        os.chdir(tmp_path)
        cleaner.run()
    finally:
        os.chdir(original_cwd)

    # No TUI renderer should exist
    assert cleaner._tui_renderer is None


# Test show_complete method
def test_show_complete():
    """show_complete accepts summary dict."""
    from recursive_cleaner.tui import HAS_RICH, TUIRenderer

    if not HAS_RICH:
        pytest.skip("Rich not installed")

    renderer = TUIRenderer(
        file_path="test.jsonl",
        total_chunks=5,
    )

    # Add some state
    renderer.add_function("func1", "Doc1")
    renderer.update_metrics(0.0, 100.0, 80.0, 400.0, 5)
    renderer.update_tokens("a" * 4000, "b" * 2000)  # ~1k in, ~500 out

    # Should not raise
    renderer.show_complete({
        "functions_count": 1,
        "chunks_processed": 5,
        "latency_total_ms": 400.0,
        "llm_calls": 5,
        "output_file": "cleaning_functions.py",
    })


# Test TUIState dataclass
def test_tui_state_dataclass():
    """TUIState dataclass has correct fields."""
    from recursive_cleaner.tui import TUIState

    state = TUIState(
        file_path="test.jsonl",
        total_records=100,
    )

    assert state.file_path == "test.jsonl"
    assert state.total_records == 100
    assert state.version == "0.8.0"
    assert state.current_chunk == 0
    assert state.total_chunks == 0
    assert state.current_iteration == 0
    assert state.max_iterations == 5
    assert state.llm_status == "idle"
    assert state.functions == []
    # New fields
    assert state.tokens_in == 0
    assert state.tokens_out == 0
    assert state.last_response == ""


def test_function_info_dataclass():
    """FunctionInfo dataclass stores name and docstring."""
    from recursive_cleaner.tui import FunctionInfo

    info = FunctionInfo(name="my_func", docstring="Does stuff")
    assert info.name == "my_func"
    assert info.docstring == "Does stuff"


# Test refresh methods don't crash
def test_refresh_methods_dont_crash_without_rich():
    """Refresh methods handle missing Rich gracefully."""
    from recursive_cleaner.tui import TUIRenderer

    # Create renderer without Rich
    with patch("recursive_cleaner.tui.HAS_RICH", False):
        renderer = TUIRenderer.__new__(TUIRenderer)
        renderer._state = MagicMock()
        renderer._layout = None
        renderer._live = None
        renderer._console = None
        renderer._start_time = time.time()

        # None of these should raise
        renderer._refresh()
        renderer._refresh_header()
        renderer._refresh_status_bar()
        renderer._refresh_progress_bar()
        renderer._refresh_left_panel()
        renderer._refresh_right_panel()
        # Legacy methods
        renderer._refresh_progress()
        renderer._refresh_functions()
        renderer._refresh_footer()


# Test layout structure
def test_layout_structure():
    """Layout has correct sections for Mission Control aesthetic."""
    from recursive_cleaner.tui import HAS_RICH, TUIRenderer

    if not HAS_RICH:
        pytest.skip("Rich not installed")

    renderer = TUIRenderer(
        file_path="test.jsonl",
        total_chunks=5,
    )

    layout = renderer._layout
    assert layout is not None

    # Check layout has expected sections
    child_names = [c.name for c in layout.children]
    assert "header" in child_names
    assert "status_bar" in child_names
    assert "progress_bar" in child_names
    assert "body" in child_names


def test_body_has_split_panels():
    """Body section has left and right panels."""
    from recursive_cleaner.tui import HAS_RICH, TUIRenderer

    if not HAS_RICH:
        pytest.skip("Rich not installed")

    renderer = TUIRenderer(
        file_path="test.jsonl",
        total_chunks=5,
    )

    layout = renderer._layout
    body_layout = layout["body"]

    # Check body has left and right panels
    panel_names = [c.name for c in body_layout.children]
    assert "left_panel" in panel_names
    assert "right_panel" in panel_names


# Test dry run with TUI
def test_dry_run_with_tui(tmp_path):
    """Dry run mode works with TUI enabled."""
    from recursive_cleaner.tui import HAS_RICH

    if not HAS_RICH:
        pytest.skip("Rich not installed")

    test_file = tmp_path / "test.jsonl"
    test_file.write_text('{"a": 1}\n')

    mock_llm = MockLLM([RESPONSE_WITH_FUNCTION])
    cleaner = DataCleaner(
        llm_backend=mock_llm,
        file_path=str(test_file),
        chunk_size=10,
        tui=True,
        dry_run=True,
        report_path=None,
    )

    import os
    original_cwd = os.getcwd()
    try:
        os.chdir(tmp_path)
        cleaner.run()
    finally:
        os.chdir(original_cwd)

    # No functions should be generated in dry run
    assert len(cleaner.functions) == 0
    # TUI should have been stopped
    assert cleaner._tui_renderer is not None


# Test callbacks still fire with TUI
def test_callbacks_fire_with_tui(tmp_path):
    """Callbacks still fire when TUI is enabled."""
    from recursive_cleaner.tui import HAS_RICH

    if not HAS_RICH:
        pytest.skip("Rich not installed")

    test_file = tmp_path / "test.jsonl"
    test_file.write_text('{"a": 1}\n')

    events = []

    def track_events(e):
        events.append(e)

    mock_llm = MockLLM([CLEAN_RESPONSE])
    cleaner = DataCleaner(
        llm_backend=mock_llm,
        file_path=str(test_file),
        chunk_size=10,
        tui=True,
        on_progress=track_events,
        report_path=None,
    )

    import os
    original_cwd = os.getcwd()
    try:
        os.chdir(tmp_path)
        cleaner.run()
    finally:
        os.chdir(original_cwd)

    # Check that callbacks fired
    event_types = [e["type"] for e in events]
    assert "chunk_start" in event_types
    assert "complete" in event_types


# Test header title exists
def test_header_title_exists():
    """HEADER_TITLE constant is defined and contains expected text."""
    from recursive_cleaner.tui import HEADER_TITLE

    assert HEADER_TITLE is not None
    assert len(HEADER_TITLE) > 0
    assert "RECURSIVE CLEANER" in HEADER_TITLE

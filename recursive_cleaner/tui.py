"""Rich TUI dashboard with Mission Control retro aesthetic."""

import time
from dataclasses import dataclass, field
from typing import Literal

# Graceful import - TUI features only available when Rich is installed
try:
    from rich.box import DOUBLE
    from rich.console import Console, Group
    from rich.layout import Layout
    from rich.live import Live
    from rich.panel import Panel
    from rich.progress import BarColumn, Progress, SpinnerColumn, TextColumn
    from rich.spinner import Spinner
    from rich.table import Table
    from rich.text import Text

    HAS_RICH = True
except ImportError:
    HAS_RICH = False


# ASCII art banner - chunky block style
ASCII_BANNER = """
██████╗ ███████╗ ██████╗██╗   ██╗██████╗ ███████╗██╗██╗   ██╗███████╗
██╔══██╗██╔════╝██╔════╝██║   ██║██╔══██╗██╔════╝██║██║   ██║██╔════╝
██████╔╝█████╗  ██║     ██║   ██║██████╔╝███████╗██║██║   ██║█████╗
██╔══██╗██╔══╝  ██║     ██║   ██║██╔══██╗╚════██║██║╚██╗ ██╔╝██╔══╝
██║  ██║███████╗╚██████╗╚██████╔╝██║  ██║███████║██║ ╚████╔╝ ███████╗
╚═╝  ╚═╝╚══════╝ ╚═════╝ ╚═════╝ ╚═╝  ╚═╝╚══════╝╚═╝  ╚═══╝  ╚══════╝
 ██████╗██╗     ███████╗ █████╗ ███╗   ██╗███████╗██████╗
██╔════╝██║     ██╔════╝██╔══██╗████╗  ██║██╔════╝██╔══██╗
██║     ██║     █████╗  ███████║██╔██╗ ██║█████╗  ██████╔╝
██║     ██║     ██╔══╝  ██╔══██║██║╚██╗██║██╔══╝  ██╔══██╗
╚██████╗███████╗███████╗██║  ██║██║ ╚████║███████╗██║  ██║
 ╚═════╝╚══════╝╚══════╝╚═╝  ╚═╝╚═╝  ╚═══╝╚══════╝╚═╝  ╚═╝
""".strip()

# Keep HEADER_TITLE for backwards compatibility with tests
HEADER_TITLE = "RECURSIVE CLEANER"


# Sparkline block characters (8 levels, low to high)
SPARK_BLOCKS = "▁▂▃▄▅▆▇█"

# Phase definitions for the pipeline stage indicator
PHASES = ["ANALYZE", "GENERATE", "VALIDATE"]


@dataclass
class FunctionInfo:
    """Info about a generated cleaning function."""

    name: str
    docstring: str


@dataclass
class TUIState:
    """Dashboard display state."""

    # Header
    file_path: str
    total_records: int
    version: str = "0.8.0"

    # Progress
    current_chunk: int = 0
    total_chunks: int = 0
    current_iteration: int = 0
    max_iterations: int = 5

    # LLM Status
    llm_status: Literal["idle", "calling"] = "idle"

    # Phase tracking
    phase: str = "IDLE"

    # Functions
    functions: list[FunctionInfo] = field(default_factory=list)

    # Function flash effect - timestamp of last function acquisition
    last_function_time: float = 0.0

    # Latency metrics
    latency_last_ms: float = 0.0
    latency_avg_ms: float = 0.0
    latency_total_ms: float = 0.0
    llm_call_count: int = 0

    # Latency history for sparkline (last N values in seconds)
    latency_history: list[float] = field(default_factory=list)

    # Token estimation
    tokens_in: int = 0
    tokens_out: int = 0

    # Transmission log
    last_response: str = ""

    # Activity log (ring buffer of recent events)
    activity_log: list[str] = field(default_factory=list)


class TUIRenderer:
    """
    Rich-based terminal dashboard with Mission Control retro aesthetic.

    Shows live updates during cleaning runs with:
    - ASCII art banner header
    - Mission timer and status indicator
    - Progress bar and chunk/iteration counters
    - List of generated functions with checkmarks
    - Token estimation and latency metrics
    - Transmission log showing latest LLM response
    """

    def __init__(self, file_path: str, total_chunks: int, total_records: int = 0):
        """
        Initialize TUI renderer.

        Args:
            file_path: Path to the data file being cleaned
            total_chunks: Total number of chunks to process
            total_records: Total number of records in the file
        """
        self._state = TUIState(
            file_path=file_path,
            total_chunks=total_chunks,
            total_records=total_records,
        )
        self._start_time = time.time()
        self._layout = self._make_layout() if HAS_RICH else None
        self._live: "Live | None" = None
        self._console = Console() if HAS_RICH else None

    def _make_layout(self) -> "Layout":
        """Create the dashboard layout structure.

        Layout:
        - header (size=5)       - ASCII art banner "RECURSIVE CLEANER"
        - status_bar (size=3)   - MISSION | TIME | STATUS
        - progress_bar (size=3) - CHUNK X/Y + progress bar
        - body (size=computed)  - Split horizontally, FIXED size to prevent infinite expansion
            - left_panel        - FUNCTIONS ACQUIRED, tokens, latency
            - right_panel       - Parsed transmission log

        CRITICAL: Body uses fixed `size=` not `ratio=` to prevent panels from
        expanding infinitely and pushing header off screen on large terminals.
        Works on terminals as small as 80x24.
        """
        if not HAS_RICH:
            return None

        from rich.console import Console

        console = Console()
        term_height = console.height or 24  # Default to 24 if unknown

        # Fixed heights for top sections
        header_height = 14  # ASCII banner (12 lines + border)
        status_height = 4  # Status + phase rows + border
        progress_height = 3
        fixed_total = header_height + status_height + progress_height

        # Body gets remaining space with a FIXED size (not ratio)
        # Cap at 18 rows max to keep it tight
        body_height = min(18, max(10, term_height - fixed_total - 2))

        layout = Layout()
        layout.split_column(
            Layout(name="header", size=header_height),
            Layout(name="status_bar", size=status_height),
            Layout(name="progress_bar", size=progress_height),
            Layout(name="body", size=body_height),  # FIXED size, not ratio
        )
        layout["body"].split_row(
            Layout(name="left_panel", ratio=1),
            Layout(name="right_panel", ratio=1),
        )
        return layout

    def start(self) -> None:
        """Start the live TUI display."""
        if not HAS_RICH or self._layout is None:
            return

        self._start_time = time.time()
        self._refresh()
        self._live = Live(
            self._layout,
            console=self._console,
            refresh_per_second=4,
            vertical_overflow="crop",
        )
        self._live.start()

    def stop(self) -> None:
        """Stop the live TUI display."""
        if self._live:
            self._live.stop()
            self._live = None

    def update_chunk(self, chunk_index: int, iteration: int, max_iterations: int) -> None:
        """
        Update progress for current chunk and iteration.

        Args:
            chunk_index: Current chunk index (0-based)
            iteration: Current iteration within chunk (0-based)
            max_iterations: Maximum iterations per chunk
        """
        self._state.current_chunk = chunk_index + 1  # Convert to 1-based for display
        self._state.current_iteration = iteration + 1
        self._state.max_iterations = max_iterations
        self._state.phase = "ANALYZE"
        self.add_activity(f"Chunk {chunk_index + 1}/{self._state.total_chunks} pass {iteration + 1}")
        self._refresh()

    def update_llm_status(self, status: Literal["calling", "idle"]) -> None:
        """
        Update LLM call status.

        Args:
            status: "calling" when LLM is being called, "idle" otherwise
        """
        self._state.llm_status = status
        if status == "calling":
            self._state.phase = "ANALYZE"
        self._refresh()

    def update_phase(self, phase: str) -> None:
        """
        Update the current pipeline phase.

        Args:
            phase: One of "ANALYZE", "GENERATE", "VALIDATE", or "IDLE"
        """
        self._state.phase = phase
        self._refresh()

    def add_function(self, name: str, docstring: str) -> None:
        """
        Add a newly generated function to the display.

        Args:
            name: Function name
            docstring: Function docstring
        """
        self._state.functions.append(FunctionInfo(name=name, docstring=docstring))
        self._state.last_function_time = time.time()
        self._state.phase = "VALIDATE"
        self.add_activity(f"Acquired: {name}")
        self._refresh()

    def add_activity(self, message: str) -> None:
        """
        Add an event to the activity log.

        Keeps a ring buffer of the most recent 8 events.

        Args:
            message: Short description of the event
        """
        elapsed = self._get_elapsed_time()
        entry = f"[{elapsed}] {message}"
        self._state.activity_log.append(entry)
        # Ring buffer: keep last 8 entries
        if len(self._state.activity_log) > 8:
            self._state.activity_log = self._state.activity_log[-8:]

    def update_metrics(
        self,
        quality_delta: float,
        latency_last: float,
        latency_avg: float,
        latency_total: float,
        llm_calls: int,
    ) -> None:
        """
        Update latency metrics.

        Args:
            quality_delta: Quality improvement percentage (ignored, kept for compatibility)
            latency_last: Last LLM call latency in ms
            latency_avg: Average LLM call latency in ms
            latency_total: Total LLM call time in ms
            llm_calls: Total number of LLM calls
        """
        self._state.latency_last_ms = latency_last
        self._state.latency_avg_ms = latency_avg
        self._state.latency_total_ms = latency_total
        self._state.llm_call_count = llm_calls
        # Track latency history for sparkline (store in seconds)
        self._state.latency_history.append(latency_last / 1000.0)
        if len(self._state.latency_history) > 15:
            self._state.latency_history = self._state.latency_history[-15:]
        self._refresh()

    def update_tokens(self, prompt: str, response: str) -> None:
        """
        Update token estimates.

        Rough estimate: len(text) // 4

        Args:
            prompt: The prompt sent to the LLM
            response: The response received from the LLM
        """
        self._state.tokens_in += len(prompt) // 4
        self._state.tokens_out += len(response) // 4
        self._refresh()

    def update_transmission(self, response: str) -> None:
        """
        Update the transmission log with latest LLM response.

        Args:
            response: The latest LLM response text
        """
        self._state.last_response = response
        # Update phase based on response content
        if "<name>" in response and "<code>" in response:
            self._state.phase = "GENERATE"
        self._refresh()

    def _get_elapsed_time(self) -> str:
        """Get elapsed time as MM:SS string."""
        elapsed = int(time.time() - self._start_time)
        minutes = elapsed // 60
        seconds = elapsed % 60
        return f"{minutes:02d}:{seconds:02d}"

    def show_complete(self, summary: dict) -> None:
        """
        Show completion summary panel.

        Args:
            summary: Dictionary with completion stats including:
                - functions_count: Number of functions generated
                - chunks_processed: Number of chunks processed
                - latency_total_ms: Total LLM time in ms
                - llm_calls: Number of LLM calls
                - output_file: Path to output file
        """
        if not HAS_RICH or self._layout is None:
            return

        self._state.phase = "IDLE"

        # Build completion panel content
        content = Table.grid(padding=(0, 2))
        content.add_column(justify="left")
        content.add_column(justify="left")

        func_count = summary.get("functions_count", len(self._state.functions))
        chunks = summary.get("chunks_processed", self._state.total_chunks)
        elapsed = self._get_elapsed_time()

        # Token stats
        tokens_in_k = self._state.tokens_in / 1000
        tokens_out_k = self._state.tokens_out / 1000

        content.add_row(
            Text("Functions Acquired:", style="bold"),
            Text(str(func_count), style="green bold"),
        )
        content.add_row(
            Text("Chunks Processed:", style="bold"),
            Text(str(chunks)),
        )
        content.add_row(
            Text("Total Time:", style="bold"),
            Text(elapsed),
        )
        content.add_row(
            Text("Tokens:", style="bold"),
            Text(f"~{tokens_in_k:.1f}k in / ~{tokens_out_k:.1f}k out"),
        )

        # Latency sparkline in summary
        sparkline = self._build_sparkline()
        if sparkline:
            content.add_row(
                Text("Latency Profile:", style="bold"),
                Text(sparkline, style="cyan"),
            )

        content.add_row(Text(""), Text(""))  # Spacer
        content.add_row(
            Text("Output:", style="bold"),
            Text(summary.get("output_file", "cleaning_functions.py"), style="cyan bold"),
        )

        # Build the complete panel with box drawing
        complete_panel = Panel(
            content,
            title="[bold green]\u2713 MISSION COMPLETE \u2713[/bold green]",
            border_style="green",
            box=DOUBLE,
        )

        # Replace entire layout with completion panel
        self._layout.split_column(
            Layout(complete_panel, name="complete"),
        )

        if self._live:
            self._live.update(self._layout)

    def _refresh(self) -> None:
        """Refresh all panels with current state."""
        if not HAS_RICH or self._layout is None:
            return

        self._refresh_header()
        self._refresh_status_bar()
        self._refresh_progress_bar()
        self._refresh_left_panel()
        self._refresh_right_panel()

        if self._live:
            self._live.update(self._layout)

    def _refresh_header(self) -> None:
        """Refresh the header panel with ASCII art banner."""
        if not HAS_RICH or self._layout is None:
            return

        banner_text = Text(ASCII_BANNER, style="bold cyan")
        header_panel = Panel(
            banner_text,
            border_style="cyan",
            box=DOUBLE,
            padding=(0, 1),
        )
        self._layout["header"].update(header_panel)

    def _build_phase_indicator(self) -> Text:
        """Build the phase pipeline indicator: ANALYZE > GENERATE > VALIDATE."""
        text = Text()
        current = self._state.phase
        for i, phase in enumerate(PHASES):
            if i > 0:
                text.append(" \u25b8 ", style="dim")  # Small right triangle separator
            if phase == current:
                text.append(phase, style="bold bright_white on blue")
            else:
                text.append(phase, style="dim")
        return text

    def _refresh_status_bar(self) -> None:
        """Refresh the status bar with mission info, timer, status, and phase."""
        if not HAS_RICH or self._layout is None:
            return

        # Truncate file path if too long
        file_path = self._state.file_path
        if len(file_path) > 30:
            file_path = "..." + file_path[-27:]

        elapsed = self._get_elapsed_time()

        # Build status bar content
        status_table = Table.grid(padding=(0, 2), expand=True)
        status_table.add_column(justify="left", ratio=2)
        status_table.add_column(justify="center", ratio=1)
        status_table.add_column(justify="right", ratio=1)

        mission_text = Text()
        mission_text.append("MISSION: ", style="bold")
        mission_text.append(file_path, style="cyan")

        time_text = Text()
        time_text.append("TIME: ", style="bold")
        time_text.append(elapsed, style="cyan")

        # Status with animated spinner when active
        if self._state.llm_status == "calling":
            status_renderable = Text()
            status_renderable.append("STATUS: ", style="bold")
            # We use a spinner character sequence for animation feel
            # Rich Spinner needs to be rendered separately, so we embed it in the Group
            spinner = Spinner("dots", text="ACTIVE", style="bold green")
            status_table.add_row(mission_text, time_text, spinner)
        else:
            status_combined = Text()
            status_combined.append("STATUS: ", style="bold")
            status_combined.append("\u25cb ", style="dim")  # Empty circle
            status_combined.append("IDLE", style="dim")
            status_table.add_row(mission_text, time_text, status_combined)

        # Phase indicator row
        phase_table = Table.grid(padding=(0, 2), expand=True)
        phase_table.add_column(justify="left", ratio=1)
        phase_table.add_column(justify="right", ratio=1)
        phase_text = Text()
        phase_text.append("PHASE: ", style="bold")
        phase_text.append_text(self._build_phase_indicator())

        # Functions per minute rate
        rate_text = Text()
        func_count = len(self._state.functions)
        elapsed_secs = time.time() - self._start_time
        if func_count > 0 and elapsed_secs > 0:
            rate = func_count / (elapsed_secs / 60.0)
            rate_text.append("RATE: ", style="bold")
            rate_text.append(f"{rate:.1f} func/min", style="cyan")
        phase_table.add_row(phase_text, rate_text)

        status_panel = Panel(
            Group(status_table, phase_table),
            border_style="cyan",
            box=DOUBLE,
            padding=(0, 1),
        )
        self._layout["status_bar"].update(status_panel)

    def _refresh_progress_bar(self) -> None:
        """Refresh the progress bar panel with chunk and iteration progress."""
        if not HAS_RICH or self._layout is None:
            return

        # Calculate progress percentage
        progress_pct = 0
        if self._state.total_chunks > 0:
            progress_pct = int((self._state.current_chunk / self._state.total_chunks) * 100)

        # Iteration indicator: PASS 2/5
        iteration_str = ""
        if self._state.current_iteration > 0:
            iteration_str = f"  \u2022  PASS {self._state.current_iteration}/{self._state.max_iterations}"

        # Build progress bar using Rich Progress
        progress = Progress(
            TextColumn("[bold cyan]\u25ba[/bold cyan]"),
            TextColumn(f"CHUNK {self._state.current_chunk}/{self._state.total_chunks}"),
            BarColumn(bar_width=30, complete_style="cyan", finished_style="green"),
            TextColumn(f"{progress_pct}%"),
            TextColumn(f"[dim]{iteration_str}[/dim]"),
            expand=False,
        )
        task = progress.add_task("", total=self._state.total_chunks, completed=self._state.current_chunk)

        progress_panel = Panel(
            progress,
            border_style="cyan",
            box=DOUBLE,
            padding=(0, 1),
        )
        self._layout["progress_bar"].update(progress_panel)

    def _build_sparkline(self) -> str:
        """Build a Unicode sparkline from latency history.

        Returns:
            String of Unicode block characters representing latency trend.
        """
        history = self._state.latency_history
        if not history:
            return ""
        if len(history) == 1:
            return SPARK_BLOCKS[3]  # Middle height for single value
        min_val = min(history)
        max_val = max(history)
        span = max_val - min_val
        if span == 0:
            return SPARK_BLOCKS[3] * len(history)
        return "".join(
            SPARK_BLOCKS[min(7, int((v - min_val) / span * 7))]
            for v in history
        )

    def _refresh_left_panel(self) -> None:
        """Refresh the left panel with functions list, sparkline, and metrics."""
        if not HAS_RICH or self._layout is None:
            return

        func_count = len(self._state.functions)
        now = time.time()
        # Flash effect: highlight last function for 1.5 seconds after acquisition
        flash_active = (now - self._state.last_function_time) < 1.5 if self._state.last_function_time > 0 else False

        # Build function tree
        content = Table.grid(padding=(0, 0))
        content.add_column()

        # Show max 6 functions with tree structure
        max_display = 6
        display_funcs = self._state.functions[-max_display:] if func_count > max_display else self._state.functions

        for i, func in enumerate(display_funcs):
            is_last = i == len(display_funcs) - 1
            func_text = Text()
            # Tree-style prefix
            if is_last:
                func_text.append("\u2514\u2500 ", style="dim cyan")  # Corner
            else:
                func_text.append("\u251c\u2500 ", style="dim cyan")  # Tee

            # Flash the newest function with bright highlight
            if is_last and flash_active:
                func_text.append(func.name, style="bold bright_green")
                func_text.append(" \u2713 NEW", style="bold bright_green")
            else:
                func_text.append(func.name, style="bold")
                func_text.append(" \u2713", style="green")  # Checkmark

            content.add_row(func_text)

        # Show "+N more" if truncated
        if func_count > max_display:
            hidden_count = func_count - max_display
            content.add_row(Text(f"   (+{hidden_count} more)", style="dim italic"))

        # Add spacing
        content.add_row(Text(""))

        # Token stats
        tokens_in_k = self._state.tokens_in / 1000
        tokens_out_k = self._state.tokens_out / 1000
        tokens_text = Text()
        tokens_text.append("TOKENS: ", style="bold")
        tokens_text.append(f"~{tokens_in_k:.1f}k in / ~{tokens_out_k:.1f}k out", style="dim")
        content.add_row(tokens_text)

        # Latency stats with sparkline
        latency_text = Text()
        latency_text.append("LATENCY: ", style="bold")
        if self._state.llm_call_count > 0:
            latency_text.append(f"{self._state.latency_last_ms / 1000:.1f}s ", style="cyan")
            sparkline = self._build_sparkline()
            if sparkline:
                latency_text.append(sparkline, style="cyan")
                latency_text.append(" ", style="")
            latency_text.append(f"(avg {self._state.latency_avg_ms / 1000:.1f}s)", style="dim")
        else:
            latency_text.append("\u2014", style="dim")  # Em dash
        content.add_row(latency_text)

        left_panel = Panel(
            content,
            title=f"[bold cyan]FUNCTIONS ACQUIRED [{func_count}][/bold cyan]",
            border_style="cyan",
            box=DOUBLE,
        )
        self._layout["left_panel"].update(left_panel)

    def _colorize_transmission(self, response: str) -> "Text":
        """Parse LLM XML response into colorized Rich Text for transmission log.

        Color scheme:
        - Issues (solved): dim
        - Issues (unsolved): bright_white with cycling accent (blue/magenta/cyan/yellow)
        - Function names: green
        - Docstrings: italic
        - Status clean: green
        - Status needs_more_work: yellow

        Args:
            response: Raw LLM response text (XML format)

        Returns:
            Rich Text object with colors applied.
        """
        import re

        ISSUE_COLORS = ["blue", "magenta", "cyan", "yellow"]
        text = Text()
        unsolved_index = 0

        try:
            # Find all issues
            issue_pattern = r'<issue[^>]*id="(\d+)"[^>]*solved="(true|false)"[^>]*>([^<]+)</issue>'
            issues = re.findall(issue_pattern, response, re.DOTALL)

            if issues:
                text.append("ISSUES DETECTED:\n", style="bold cyan")
                for issue_id, solved, desc in issues[:8]:  # Limit to 8 issues
                    desc_clean = desc.strip()[:40]  # Truncate description
                    if solved == "true":
                        text.append("  \u2713 ", style="green")
                        text.append(f"{desc_clean}\n", style="dim")
                    else:
                        accent = ISSUE_COLORS[unsolved_index % len(ISSUE_COLORS)]
                        text.append("  \u2717 ", style=accent)
                        text.append(f"{desc_clean}\n", style="bright_white")
                        unsolved_index += 1
                if len(issues) > 8:
                    text.append(f"  (+{len(issues) - 8} more)\n", style="dim")
                text.append("\n")

            # Find function being generated
            name_match = re.search(r'<name>([^<]+)</name>', response)
            docstring_match = re.search(r'<docstring>([^<]+)</docstring>', response, re.DOTALL)

            if name_match:
                text.append("GENERATING: ", style="bold cyan")
                text.append(f"{name_match.group(1).strip()}\n", style="green bold")
                if docstring_match:
                    doc = docstring_match.group(1).strip()[:60]
                    text.append(f'  "{doc}..."\n', style="italic")
                text.append("\n")

            # Find chunk status
            status_match = re.search(r'<chunk_status>([^<]+)</chunk_status>', response)
            if status_match:
                status = status_match.group(1).strip()
                text.append("STATUS: ", style="bold cyan")
                if status == "clean":
                    text.append(status.upper(), style="green bold")
                else:
                    text.append(status.upper().replace("_", " "), style="yellow bold")

            if text.plain:
                return text
        except Exception:
            pass

        # Fallback: show truncated raw response
        fallback = response[:500] + "..." if len(response) > 500 else response
        return Text(fallback, style="dim cyan")

    def _build_activity_log(self) -> Text:
        """Build the activity log display from the event ring buffer."""
        text = Text()
        text.append("ACTIVITY:\n", style="bold cyan")
        if not self._state.activity_log:
            text.append("  (waiting...)", style="dim")
        else:
            for entry in self._state.activity_log:
                text.append(f"  {entry}\n", style="dim green")
        return text

    def _refresh_right_panel(self) -> None:
        """Refresh the right panel with colorized transmission log and activity."""
        if not HAS_RICH or self._layout is None:
            return

        # Get last response and colorize for display
        response = self._state.last_response
        if not response:
            log_text = Text("(Awaiting transmission...)", style="dim cyan")
        else:
            log_text = self._colorize_transmission(response)

        # Append activity log below transmission
        activity = self._build_activity_log()

        right_panel = Panel(
            Group(log_text, Text(""), activity),
            title="[bold cyan]\u25c4\u25c4 TRANSMISSION LOG \u25ba\u25ba[/bold cyan]",
            border_style="cyan",
            box=DOUBLE,
        )
        self._layout["right_panel"].update(right_panel)

    # Legacy method stubs for backwards compatibility
    def _refresh_progress(self) -> None:
        """Legacy method - calls _refresh_progress_bar."""
        self._refresh_progress_bar()

    def _refresh_functions(self) -> None:
        """Legacy method - calls _refresh_left_panel."""
        self._refresh_left_panel()

    def _refresh_footer(self) -> None:
        """Legacy method - no longer used but kept for compatibility."""
        pass

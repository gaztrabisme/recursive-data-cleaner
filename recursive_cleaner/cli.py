"""CLI interface for Recursive Data Cleaner."""

import argparse
import os
import sys


def create_backend(provider: str, model: str, base_url: str | None, api_key: str | None):
    """
    Factory function to create the appropriate backend.

    Args:
        provider: Backend provider ("mlx" or "openai")
        model: Model name/path
        base_url: Optional API base URL (for openai-compatible servers)
        api_key: Optional API key

    Returns:
        LLMBackend instance

    Raises:
        SystemExit: With code 2 if provider is invalid or import fails
    """
    if provider == "mlx":
        try:
            from backends import MLXBackend
            return MLXBackend(model_path=model)
        except ImportError:
            print("Error: MLX backend requires mlx-lm. Install with: pip install mlx-lm", file=sys.stderr)
            sys.exit(2)
    elif provider == "openai":
        try:
            from backends import OpenAIBackend
            return OpenAIBackend(model=model, api_key=api_key, base_url=base_url)
        except ImportError as e:
            print(f"Error: {e}", file=sys.stderr)
            sys.exit(2)
    else:
        print(f"Error: Unknown provider '{provider}'. Use 'mlx' or 'openai'.", file=sys.stderr)
        sys.exit(2)


def read_instructions(value: str) -> str:
    """
    Read instructions from inline text or file.

    Args:
        value: Instructions string or @file.txt path

    Returns:
        Instructions text
    """
    if value.startswith("@"):
        file_path = value[1:]
        try:
            with open(file_path, "r") as f:
                return f.read().strip()
        except FileNotFoundError:
            print(f"Error: Instructions file not found: {file_path}", file=sys.stderr)
            sys.exit(1)
        except IOError as e:
            print(f"Error reading instructions file: {e}", file=sys.stderr)
            sys.exit(1)
    elif value == "-":
        return sys.stdin.read().strip()
    return value


def cmd_generate(args) -> int:
    """Handle the generate command."""
    from recursive_cleaner import DataCleaner

    # Check if file exists
    if not os.path.exists(args.file):
        print(f"Error: File not found: {args.file}", file=sys.stderr)
        return 1

    # Create backend
    backend = create_backend(args.provider, args.model, args.base_url, args.api_key)

    # Read instructions
    instructions = read_instructions(args.instructions) if args.instructions else ""

    # Create progress callback for non-TUI mode
    def on_progress(event):
        if not args.tui:
            event_type = event.get("type", "")
            if event_type == "function_generated":
                print(f"  Generated: {event.get('function_name', '')}")

    try:
        cleaner = DataCleaner(
            llm_backend=backend,
            file_path=args.file,
            chunk_size=args.chunk_size,
            instructions=instructions,
            max_iterations=args.max_iterations,
            mode=args.mode,
            state_file=args.state_file,
            report_path=args.report if args.report else None,
            tui=args.tui,
            optimize=args.optimize,
            track_metrics=args.track_metrics,
            early_termination=args.early_termination,
            on_progress=on_progress if not args.tui else None,
            output_path=args.output,
        )
        cleaner.run()
        return 0
    except FileNotFoundError as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        return 3


def cmd_analyze(args) -> int:
    """Handle the analyze command (dry-run mode)."""
    from recursive_cleaner import DataCleaner

    # Check if file exists
    if not os.path.exists(args.file):
        print(f"Error: File not found: {args.file}", file=sys.stderr)
        return 1

    # Create backend
    backend = create_backend(args.provider, args.model, args.base_url, args.api_key)

    # Read instructions
    instructions = read_instructions(args.instructions) if args.instructions else ""

    # Progress callback for analysis output
    def on_progress(event):
        if not args.tui:
            event_type = event.get("type", "")
            if event_type == "issues_detected":
                issues = event.get("issues", [])
                chunk_idx = event.get("chunk_index", 0)
                unsolved = [i for i in issues if not i.get("solved", False)]
                print(f"Chunk {chunk_idx + 1}: {len(issues)} issues ({len(unsolved)} unsolved)")

    try:
        cleaner = DataCleaner(
            llm_backend=backend,
            file_path=args.file,
            chunk_size=args.chunk_size,
            instructions=instructions,
            max_iterations=args.max_iterations,
            mode=args.mode,
            dry_run=True,
            tui=args.tui,
            on_progress=on_progress if not args.tui else None,
        )
        cleaner.run()
        return 0
    except FileNotFoundError as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        return 3


def cmd_resume(args) -> int:
    """Handle the resume command."""
    from recursive_cleaner import DataCleaner

    # Check if state file exists
    if not os.path.exists(args.state_file):
        print(f"Error: State file not found: {args.state_file}", file=sys.stderr)
        return 1

    # Create backend
    backend = create_backend(args.provider, args.model, args.base_url, args.api_key)

    try:
        cleaner = DataCleaner.resume(args.state_file, backend)
        cleaner.run()
        return 0
    except FileNotFoundError as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1
    except ValueError as e:
        print(f"Error: Invalid state file: {e}", file=sys.stderr)
        return 1
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        return 3


def create_parser() -> argparse.ArgumentParser:
    """Create the argument parser with all subcommands."""
    parser = argparse.ArgumentParser(
        prog="recursive-cleaner",
        description="LLM-powered incremental data cleaning pipeline",
    )

    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # --- generate command ---
    gen_parser = subparsers.add_parser(
        "generate",
        help="Generate cleaning functions from data file",
    )
    gen_parser.add_argument("file", metavar="FILE", help="Path to input data file")
    gen_parser.add_argument(
        "-p", "--provider", required=True, choices=["mlx", "openai"],
        help="LLM provider (mlx or openai)"
    )
    gen_parser.add_argument(
        "-m", "--model", required=True, help="Model name/path"
    )
    gen_parser.add_argument(
        "-i", "--instructions", default="",
        help="Cleaning instructions (text or @file.txt)"
    )
    gen_parser.add_argument(
        "--base-url", help="API base URL (for openai-compatible servers)"
    )
    gen_parser.add_argument(
        "--api-key", help="API key (or use OPENAI_API_KEY env var)"
    )
    gen_parser.add_argument(
        "--chunk-size", type=int, default=50, help="Items per chunk (default: 50)"
    )
    gen_parser.add_argument(
        "--max-iterations", type=int, default=5,
        help="Max iterations per chunk (default: 5)"
    )
    gen_parser.add_argument(
        "--mode", choices=["auto", "structured", "text"], default="auto",
        help="Processing mode (default: auto)"
    )
    gen_parser.add_argument(
        "-o", "--output", default="cleaning_functions.py",
        help="Output file path (default: cleaning_functions.py)"
    )
    gen_parser.add_argument(
        "--report", default="cleaning_report.md",
        help="Report file path (empty to disable, default: cleaning_report.md)"
    )
    gen_parser.add_argument(
        "--state-file", help="Checkpoint file for resume"
    )
    gen_parser.add_argument(
        "--tui", action="store_true", help="Enable Rich terminal dashboard"
    )
    gen_parser.add_argument(
        "--optimize", action="store_true", help="Consolidate redundant functions"
    )
    gen_parser.add_argument(
        "--track-metrics", action="store_true", help="Measure before/after quality"
    )
    gen_parser.add_argument(
        "--early-termination", action="store_true",
        help="Stop on pattern saturation"
    )
    gen_parser.set_defaults(func=cmd_generate)

    # --- analyze command ---
    analyze_parser = subparsers.add_parser(
        "analyze",
        help="Dry-run analysis without generating functions",
    )
    analyze_parser.add_argument("file", metavar="FILE", help="Path to input data file")
    analyze_parser.add_argument(
        "-p", "--provider", required=True, choices=["mlx", "openai"],
        help="LLM provider (mlx or openai)"
    )
    analyze_parser.add_argument(
        "-m", "--model", required=True, help="Model name/path"
    )
    analyze_parser.add_argument(
        "-i", "--instructions", default="",
        help="Cleaning instructions (text or @file.txt)"
    )
    analyze_parser.add_argument(
        "--base-url", help="API base URL (for openai-compatible servers)"
    )
    analyze_parser.add_argument(
        "--api-key", help="API key (or use OPENAI_API_KEY env var)"
    )
    analyze_parser.add_argument(
        "--chunk-size", type=int, default=50, help="Items per chunk (default: 50)"
    )
    analyze_parser.add_argument(
        "--max-iterations", type=int, default=5,
        help="Max iterations per chunk (default: 5)"
    )
    analyze_parser.add_argument(
        "--mode", choices=["auto", "structured", "text"], default="auto",
        help="Processing mode (default: auto)"
    )
    analyze_parser.add_argument(
        "--tui", action="store_true", help="Enable Rich terminal dashboard"
    )
    analyze_parser.set_defaults(func=cmd_analyze)

    # --- resume command ---
    resume_parser = subparsers.add_parser(
        "resume",
        help="Resume from checkpoint file",
    )
    resume_parser.add_argument(
        "state_file", metavar="STATE_FILE", help="Path to checkpoint JSON file"
    )
    resume_parser.add_argument(
        "-p", "--provider", required=True, choices=["mlx", "openai"],
        help="LLM provider (mlx or openai)"
    )
    resume_parser.add_argument(
        "-m", "--model", required=True, help="Model name/path"
    )
    resume_parser.add_argument(
        "--base-url", help="API base URL (for openai-compatible servers)"
    )
    resume_parser.add_argument(
        "--api-key", help="API key (or use OPENAI_API_KEY env var)"
    )
    resume_parser.set_defaults(func=cmd_resume)

    return parser


def main(args: list[str] | None = None) -> int:
    """
    Main entry point for the CLI.

    Args:
        args: Command-line arguments (defaults to sys.argv[1:])

    Returns:
        Exit code (0=success, 1=general error, 2=backend error, 3=validation error)
    """
    parser = create_parser()
    parsed = parser.parse_args(args)

    if parsed.command is None:
        parser.print_help()
        return 0

    return parsed.func(parsed)


if __name__ == "__main__":
    sys.exit(main())

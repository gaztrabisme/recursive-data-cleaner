#!/usr/bin/env python3
"""Benchmark runner for Recursive Data Cleaner.

Measures pipeline performance across different MLX model sizes.
Separates download, load, warmup (TTFT), and generation timing.

Usage:
    python benchmarks/run_benchmark.py --model lmstudio-community/Qwen3-4B-Instruct-2507-MLX-8bit
    python benchmarks/run_benchmark.py --model lmstudio-community/Qwen3-8B-MLX-8bit --runs 3
    python benchmarks/run_benchmark.py --help
"""

import argparse
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path


def parse_args():
    parser = argparse.ArgumentParser(
        description="Benchmark Recursive Data Cleaner with MLX models",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python benchmarks/run_benchmark.py --model lmstudio-community/Qwen3-4B-Instruct-2507-MLX-8bit
  python benchmarks/run_benchmark.py --model lmstudio-community/Qwen3-8B-MLX-8bit --chunk-size 10
  python benchmarks/run_benchmark.py --model lmstudio-community/Qwen3-4B-Instruct-2507-MLX-8bit --runs 3 --warmup
        """,
    )
    parser.add_argument(
        "--model",
        required=True,
        help="HuggingFace model path (e.g., lmstudio-community/Qwen3-4B-Instruct-2507-MLX-8bit)",
    )
    parser.add_argument(
        "--data",
        default=str(Path(__file__).parent / "benchmark_data.jsonl"),
        help="Path to benchmark data file (default: benchmarks/benchmark_data.jsonl)",
    )
    parser.add_argument(
        "--instructions",
        default=str(Path(__file__).parent / "benchmark_instructions.txt"),
        help="Path to instructions file (default: benchmarks/benchmark_instructions.txt)",
    )
    parser.add_argument(
        "--chunk-size",
        type=int,
        default=20,
        help="Records per chunk (default: 20)",
    )
    parser.add_argument(
        "--max-iterations",
        type=int,
        default=5,
        help="Max iterations per chunk (default: 5)",
    )
    parser.add_argument(
        "--output-dir",
        default=str(Path(__file__).parent / "results"),
        help="Directory for output files (default: benchmarks/results/)",
    )
    parser.add_argument(
        "--runs",
        type=int,
        default=1,
        help="Number of runs for averaging (default: 1)",
    )
    parser.add_argument(
        "--warmup",
        action="store_true",
        help="Run a warmup generation before benchmarking (measures TTFT)",
    )
    return parser.parse_args()


def setup_backend(model_path: str, verbose: bool = True):
    """Download and load model separately, returning timing for each phase.

    Returns:
        (backend, download_time_s, load_time_s)
    """
    try:
        sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
        from backends.mlx_backend import MLXBackend
    except ImportError:
        print("Error: MLX backend not available. Install mlx-lm:")
        print("  pip install mlx-lm")
        sys.exit(1)

    backend = MLXBackend(model_path=model_path, verbose=verbose)

    # Phase 1: Download (may be cached — 0s if so)
    print("  Downloading model (if not cached)...")
    download_time = backend.download()

    # Phase 2: Load into memory
    print("  Loading model into memory...")
    load_time = backend.load_model()

    return backend, download_time, load_time


def run_warmup(backend) -> dict:
    """Run a warmup generation to measure time-to-first-token characteristics.

    Returns:
        Dict with warmup timing and token stats.
    """
    prompt = "Say 'hello' in one word."

    t0 = time.perf_counter()
    response = backend.generate(prompt)
    warmup_time = time.perf_counter() - t0

    stats = backend.last_generation_stats or {}
    return {
        "warmup_time_s": round(warmup_time, 3),
        "warmup_prompt_tokens": stats.get("prompt_tokens", 0),
        "warmup_response_tokens": stats.get("response_tokens", 0),
        "warmup_decode_tok_per_s": stats.get("decode_tok_per_s", 0),
    }


def run_pipeline(backend, data_path: str, instructions: str, chunk_size: int,
                 max_iterations: int, output_dir: str, run_id: int,
                 model_name: str = ""):
    """Run the cleaning pipeline once and collect metrics."""
    from recursive_cleaner import DataCleaner

    # Reset cumulative stats for this run
    backend._total_prompt_tokens = 0
    backend._total_response_tokens = 0
    backend._total_generation_time_s = 0.0
    backend._call_count = 0

    # Metrics collection via callback
    metrics = {
        "llm_calls": 0,
        "functions_generated": 0,
        "function_names": [],
        "chunks_processed": 0,
        "per_call_stats": [],
    }

    def on_progress(event):
        if event["type"] == "llm_call":
            metrics["llm_calls"] += 1
            # Capture per-call token stats
            stats = backend.last_generation_stats
            if stats:
                metrics["per_call_stats"].append({
                    "call_num": metrics["llm_calls"],
                    **stats,
                })
        elif event["type"] == "function_generated":
            metrics["functions_generated"] += 1
            metrics["function_names"].append(event.get("function_name", ""))
        elif event["type"] == "chunk_done":
            metrics["chunks_processed"] += 1

    # Use model name in output paths to avoid overwrites across models
    slug = model_name.split("/")[-1] if model_name else f"run{run_id}"
    output_path = str(Path(output_dir) / f"cleaning_functions_{slug}.py")
    report_path = str(Path(output_dir) / f"cleaning_report_{slug}.md")

    cleaner = DataCleaner(
        llm_backend=backend,
        file_path=data_path,
        chunk_size=chunk_size,
        instructions=instructions,
        max_iterations=max_iterations,
        on_progress=on_progress,
        output_path=output_path,
        report_path=report_path,
        validate_runtime=True,
        tui=False,
    )

    t0 = time.perf_counter()
    cleaner.run()
    pipeline_time = time.perf_counter() - t0

    # Get latency stats from the cleaner's tracker
    latency_stats = cleaner._latency.summary()

    # Get cumulative token stats from backend
    cumulative = backend.cumulative_stats

    return {
        "pipeline_time_s": round(pipeline_time, 2),
        "chunks": cleaner._total_chunks,
        "llm_calls": metrics["llm_calls"],
        "functions_generated": metrics["functions_generated"],
        "function_names": metrics["function_names"],
        "latency_avg_ms": round(latency_stats.get("avg_ms", 0), 1),
        "latency_min_ms": round(latency_stats.get("min_ms", 0), 1),
        "latency_max_ms": round(latency_stats.get("max_ms", 0), 1),
        "latency_total_ms": round(latency_stats.get("total_ms", 0), 1),
        "token_stats": {
            "total_prompt_tokens": cumulative["total_prompt_tokens"],
            "total_response_tokens": cumulative["total_response_tokens"],
            "total_generation_time_s": cumulative["total_generation_time_s"],
            "avg_decode_tok_per_s": cumulative["avg_decode_tok_per_s"],
        },
        "per_call_stats": metrics["per_call_stats"],
        "output_path": output_path,
        "report_path": report_path,
    }


def write_results(results: dict, output_dir: str):
    """Write JSON results and markdown summary."""
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    # Use model slug for filename instead of timestamp to avoid collisions
    slug = results["model"].split("/")[-1]

    # JSON results (full detail)
    json_path = output_dir / f"benchmark_{slug}.json"
    with open(json_path, "w") as f:
        json.dump(results, f, indent=2)

    # Markdown summary
    md_path = output_dir / f"benchmark_{slug}.md"
    with open(md_path, "w") as f:
        f.write(f"# Benchmark: {slug}\n\n")
        f.write(f"**Model**: `{results['model']}`\n")
        f.write(f"**Date**: {results['timestamp']}\n")
        f.write(f"**Data**: {results['data_path']}\n")
        f.write(f"**Chunk Size**: {results['chunk_size']}\n\n")

        # Timing breakdown
        f.write("## Timing Breakdown\n\n")
        f.write("| Phase | Time |\n")
        f.write("|-------|------|\n")
        f.write(f"| Download | {results['download_time_s']:.1f}s |\n")
        f.write(f"| Model Load | {results['load_time_s']:.1f}s |\n")

        if results.get("warmup"):
            wu = results["warmup"]
            f.write(f"| Warmup (TTFT) | {wu['warmup_time_s']:.1f}s |\n")
            f.write(f"| Warmup decode | {wu['warmup_decode_tok_per_s']:.1f} tok/s |\n")

        if results["runs"]:
            r = results["runs"][0]
            f.write(f"| Pipeline | {r['pipeline_time_s']:.1f}s |\n")
            f.write(f"| Avg LLM Latency | {r['latency_avg_ms']:.0f}ms |\n\n")

            # Pipeline metrics
            f.write("## Pipeline Metrics\n\n")
            f.write("| Metric | Value |\n")
            f.write("|--------|-------|\n")
            f.write(f"| Chunks | {r['chunks']} |\n")
            f.write(f"| LLM Calls | {r['llm_calls']} |\n")
            f.write(f"| Functions Generated | {r['functions_generated']} |\n")

            # Token stats
            ts = r.get("token_stats", {})
            if ts:
                f.write(f"| Total Prompt Tokens | {ts.get('total_prompt_tokens', 0):,} |\n")
                f.write(f"| Total Response Tokens | {ts.get('total_response_tokens', 0):,} |\n")
                f.write(f"| Avg Decode Speed | {ts.get('avg_decode_tok_per_s', 0):.1f} tok/s |\n")

            # Functions generated
            if r.get("function_names"):
                f.write(f"\n## Functions Generated\n\n")
                for i, name in enumerate(r["function_names"], 1):
                    f.write(f"{i}. `{name}`\n")

        f.write(f"\n---\n*Generated by run_benchmark.py*\n")

    print(f"\nResults written to:")
    print(f"  JSON: {json_path}")
    print(f"  Markdown: {md_path}")

    return json_path, md_path


def main():
    args = parse_args()

    # Validate inputs
    data_path = Path(args.data)
    if not data_path.exists():
        print(f"Error: Data file not found: {args.data}")
        sys.exit(1)

    instructions_path = Path(args.instructions)
    if not instructions_path.exists():
        print(f"Error: Instructions file not found: {args.instructions}")
        sys.exit(1)

    instructions = instructions_path.read_text(encoding="utf-8").strip()

    print(f"=== Recursive Data Cleaner Benchmark ===")
    print(f"Model: {args.model}")
    print(f"Data: {args.data}")
    print(f"Chunk size: {args.chunk_size}")
    print(f"Max iterations: {args.max_iterations}")
    print(f"Runs: {args.runs}")
    print()

    # Phase 1 & 2: Download + Load (timed separately)
    print("Setting up model...")
    backend, download_time, load_time = setup_backend(args.model)
    print(f"  Download: {download_time:.1f}s")
    print(f"  Load: {load_time:.1f}s")

    # Phase 3: Optional warmup (measures TTFT)
    warmup_stats = None
    if args.warmup:
        print("Running warmup (TTFT measurement)...")
        warmup_stats = run_warmup(backend)
        print(f"  Warmup time: {warmup_stats['warmup_time_s']:.1f}s")
        print(f"  Decode speed: {warmup_stats['warmup_decode_tok_per_s']:.1f} tok/s")

    # Phase 4: Run benchmark
    runs = []
    for i in range(args.runs):
        run_num = i + 1
        print(f"\n--- Run {run_num}/{args.runs} ---")
        result = run_pipeline(
            backend=backend,
            data_path=args.data,
            instructions=instructions,
            chunk_size=args.chunk_size,
            max_iterations=args.max_iterations,
            output_dir=args.output_dir,
            run_id=run_num,
            model_name=args.model,
        )
        runs.append(result)

        ts = result.get("token_stats", {})
        print(f"  Pipeline time: {result['pipeline_time_s']:.1f}s")
        print(f"  LLM calls: {result['llm_calls']}")
        print(f"  Functions generated: {result['functions_generated']}")
        if result.get("function_names"):
            print(f"  Functions: {', '.join(result['function_names'])}")
        print(f"  Avg latency: {result['latency_avg_ms']:.0f}ms")
        print(f"  Avg decode speed: {ts.get('avg_decode_tok_per_s', 0):.1f} tok/s")
        print(f"  Total tokens: {ts.get('total_prompt_tokens', 0):,} prompt + {ts.get('total_response_tokens', 0):,} response")

    # Compile results
    results = {
        "model": args.model,
        "data_path": args.data,
        "chunk_size": args.chunk_size,
        "max_iterations": args.max_iterations,
        "download_time_s": round(download_time, 2),
        "load_time_s": round(load_time, 2),
        "warmup": warmup_stats,
        "runs": runs,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }

    # Write output
    write_results(results, args.output_dir)

    # Print summary
    if len(runs) > 1:
        avg_time = sum(r["pipeline_time_s"] for r in runs) / len(runs)
        print(f"\nAverage pipeline time: {avg_time:.1f}s over {len(runs)} runs")


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""Run benchmark via LM Studio (OpenAI-compatible backend).

Usage:
    python benchmarks/run_lmstudio.py --model qwen/qwen3-coder-next
    python benchmarks/run_lmstudio.py --model qwen/qwen3-coder-next --base-url http://localhost:1234/v1
"""

import argparse
import json
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path


def parse_args():
    parser = argparse.ArgumentParser(description="Benchmark via LM Studio")
    parser.add_argument("--model", required=True, help="LM Studio model ID")
    parser.add_argument("--base-url", default="http://localhost:1234/v1",
                        help="LM Studio API URL (default: http://localhost:1234/v1)")
    parser.add_argument("--data", default=str(Path(__file__).parent / "benchmark_data.jsonl"))
    parser.add_argument("--instructions", default=str(Path(__file__).parent / "benchmark_instructions.txt"))
    parser.add_argument("--chunk-size", type=int, default=20)
    parser.add_argument("--max-iterations", type=int, default=8)
    parser.add_argument("--max-tokens", type=int, default=4096)
    parser.add_argument("--output-dir", default=str(Path(__file__).parent / "results"))
    return parser.parse_args()


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

    # Setup backend
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
    from backends.openai_backend import OpenAIBackend
    from recursive_cleaner import DataCleaner

    backend = OpenAIBackend(
        model=args.model,
        base_url=args.base_url,
        max_tokens=args.max_tokens,
        temperature=0.7,
    )

    # Model slug for filenames
    slug = args.model.replace("/", "-")

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = str(output_dir / f"cleaning_functions_{slug}.py")
    report_path = str(output_dir / f"cleaning_report_{slug}.md")

    # Metrics collection
    metrics = {"llm_calls": 0, "functions_generated": 0, "function_names": []}

    def on_progress(event):
        if event["type"] == "llm_call":
            metrics["llm_calls"] += 1
            print(f"  LLM call #{metrics['llm_calls']} ({event.get('latency_ms', 0):.0f}ms)")
        elif event["type"] == "function_generated":
            metrics["functions_generated"] += 1
            name = event.get("function_name", "")
            metrics["function_names"].append(name)
            print(f"  Function #{metrics['functions_generated']}: {name}")
        elif event["type"] == "chunk_start":
            print(f"\nChunk {event.get('chunk_index', '?') + 1}...")
        elif event["type"] == "duplicate_field":
            print(f"  Duplicate field warning: {event.get('fields', [])}")

    print(f"=== LM Studio Benchmark ===")
    print(f"Model: {args.model}")
    print(f"Base URL: {args.base_url}")
    print(f"Data: {args.data}")
    print(f"Chunk size: {args.chunk_size}")
    print(f"Max iterations: {args.max_iterations}")
    print()

    cleaner = DataCleaner(
        llm_backend=backend,
        file_path=args.data,
        chunk_size=args.chunk_size,
        instructions=instructions,
        max_iterations=args.max_iterations,
        on_progress=on_progress,
        output_path=output_path,
        report_path=report_path,
        validate_runtime=True,
        tui=False,
    )

    t0 = time.perf_counter()
    cleaner.run()
    pipeline_time = time.perf_counter() - t0

    latency_stats = cleaner._latency.summary()

    print(f"\n=== Results ===")
    print(f"Pipeline time: {pipeline_time:.1f}s ({pipeline_time/60:.1f} min)")
    print(f"LLM calls: {metrics['llm_calls']}")
    print(f"Functions: {metrics['functions_generated']}")
    print(f"Avg latency: {latency_stats.get('avg_ms', 0):.0f}ms")
    if metrics["function_names"]:
        print(f"Names: {', '.join(metrics['function_names'])}")

    # Write results JSON
    results = {
        "model": args.model,
        "backend": "openai",
        "base_url": args.base_url,
        "data_path": args.data,
        "chunk_size": args.chunk_size,
        "max_iterations": args.max_iterations,
        "pipeline_time_s": round(pipeline_time, 2),
        "llm_calls": metrics["llm_calls"],
        "functions_generated": metrics["functions_generated"],
        "function_names": metrics["function_names"],
        "latency_avg_ms": round(latency_stats.get("avg_ms", 0), 1),
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }

    json_path = output_dir / f"benchmark_{slug}.json"
    with open(json_path, "w") as f:
        json.dump(results, f, indent=2)
    print(f"\nBenchmark JSON: {json_path}")
    print(f"Cleaning functions: {output_path}")

    # Auto-run eval
    eval_script = Path(__file__).parent / "eval" / "run_eval.py"
    golden = Path(__file__).parent / "eval" / "golden" / "benchmark_golden.jsonl"
    if eval_script.exists() and golden.exists() and Path(output_path).exists():
        print(f"\n=== Running Eval ===")
        result = subprocess.run(
            [sys.executable, str(eval_script),
             "--functions", output_path,
             "--data", args.data,
             "--golden", str(golden)],
            capture_output=True, text=True,
        )
        print(result.stdout)
        if result.stderr:
            print(result.stderr)


if __name__ == "__main__":
    main()

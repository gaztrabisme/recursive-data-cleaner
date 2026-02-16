#!/usr/bin/env python3
"""Plot benchmark results from JSON files.

Reads all benchmark_*.json from benchmarks/results/ and produces:
  - chart_timing.png          — stacked timing breakdown (load, TTFT, pipeline)
  - chart_speed_vs_quality.png — dual-axis: avg call time vs decode tok/s
  - chart_coverage.png         — task coverage heatmap by model

Usage:
    python benchmarks/plot_results.py
"""

import json
import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.colors as mcolors
from matplotlib.patches import Patch
import numpy as np


RESULTS_DIR = Path(__file__).parent / "results"

# Map task names to keywords found in generated function names
TASK_KEYWORDS = {
    "Dates": ["date"],
    "Phone": ["phone"],
    "Amount": ["amount"],
    "Status": ["status"],
    "Weight": ["weight"],
    "Tags": ["tag"],
    "Name/WS": ["name", "whitespace"],
    "Category": ["category"],
    "Email": ["email"],
    "HTML": ["html", "artifact"],
    "Notes": ["note", "null_field", "empty_field"],
}

# Model display order: dense first, then MoE, then MoE coder
MODEL_ORDER = [
    "Qwen3-4B",
    "Qwen3-8B",
    "Qwen3-14B",
    "Qwen3-30B-A3B",
    "Coder-30B-A3B",
    "Coder-Next",
    "Next-80B-A3B",
]


def load_results():
    """Load all model-named benchmark JSON files."""
    results = []
    for json_file in sorted(RESULTS_DIR.glob("benchmark_*.json")):
        if json_file.stem.startswith("benchmark_20"):
            continue
        with open(json_file) as f:
            data = json.load(f)
        results.append(data)

    def sort_key(r):
        sn = short_name(r["model"])
        for i, prefix in enumerate(MODEL_ORDER):
            if prefix in sn:
                return i
        return 99

    results.sort(key=sort_key)
    return results


def short_name(model_path):
    """Extract short display name from full HuggingFace path."""
    name = model_path.split("/")[-1]
    for suffix in ["-MLX-8bit", "-MLX-4bit", "-Instruct-2507", "-Instruct", "-2507"]:
        name = name.replace(suffix, "")
    return name


def model_type(model_path):
    """Classify model as dense, moe, or coder."""
    name = model_path.lower()
    if "coder" in name:
        return "coder"
    if "a3b" in name or "next" in name:
        return "moe"
    return "dense"


TYPE_COLORS = {"dense": "#FF9800", "moe": "#4CAF50", "coder": "#2196F3"}
TYPE_LABELS = {"dense": "Dense", "moe": "MoE", "coder": "MoE Coder"}


def plot_timing_breakdown(results, output_path):
    """Stacked bar chart: model load + TTFT + pipeline time."""
    fig, ax = plt.subplots(figsize=(12, 6))

    names = [short_name(r["model"]) for r in results]
    x = np.arange(len(names))

    load_times = [r["load_time_s"] for r in results]
    ttft_times = [
        r["warmup"]["warmup_time_s"] if r.get("warmup") else 0
        for r in results
    ]
    pipeline_times = [r["runs"][0]["pipeline_time_s"] / 60 for r in results]
    funcs = [r["runs"][0]["functions_generated"] for r in results]

    # Load and TTFT are in seconds, convert to minutes for same scale
    load_min = [t / 60 for t in load_times]
    ttft_min = [t / 60 for t in ttft_times]

    colors_pipe = [TYPE_COLORS[model_type(r["model"])] for r in results]

    # Pipeline is the dominant bar
    bars_pipe = ax.bar(x, pipeline_times, color=colors_pipe, edgecolor="white",
                       linewidth=0.5, label="Pipeline")
    # TTFT stacked on top
    bars_ttft = ax.bar(x, ttft_min, bottom=pipeline_times, color="#9C27B0",
                       alpha=0.85, edgecolor="white", linewidth=0.5, label="TTFT (warmup)")
    # Load stacked on top of TTFT
    ttft_plus_pipe = [p + t for p, t in zip(pipeline_times, ttft_min)]
    bars_load = ax.bar(x, load_min, bottom=ttft_plus_pipe, color="#78909C",
                       alpha=0.85, edgecolor="white", linewidth=0.5, label="Model Load")

    # Function count + TTFT annotation on each bar
    for i, (bar, fc, ttft_s) in enumerate(zip(bars_pipe, funcs, ttft_times)):
        total_h = pipeline_times[i] + ttft_min[i] + load_min[i]
        ttft_label = f"{ttft_s:.1f}s" if ttft_s >= 1 else f"{ttft_s * 1000:.0f}ms"
        ax.text(
            bar.get_x() + bar.get_width() / 2,
            total_h + 0.5,
            f"{fc} fn | TTFT {ttft_label}",
            ha="center", va="bottom", fontsize=8.5, fontweight="bold",
        )

    ax.set_ylabel("Time (minutes)", fontsize=12)
    ax.set_title("Timing Breakdown by Model", fontsize=14, fontweight="bold")
    ax.set_xticks(x)
    ax.set_xticklabels(names, rotation=25, ha="right", fontsize=9)

    # Legend: architecture types + timing phases
    seen = []
    legend_elements = []
    for r in results:
        mt = model_type(r["model"])
        if mt not in seen:
            seen.append(mt)
            legend_elements.append(Patch(facecolor=TYPE_COLORS[mt], label=f"Pipeline ({TYPE_LABELS[mt]})"))
    legend_elements.append(Patch(facecolor="#9C27B0", alpha=0.85, label="TTFT (warmup)"))
    legend_elements.append(Patch(facecolor="#78909C", alpha=0.85, label="Model Load"))
    ax.legend(handles=legend_elements, loc="upper left", fontsize=9)

    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    max_total = max(p + t + l for p, t, l in zip(pipeline_times, ttft_min, load_min))
    ax.set_ylim(0, max_total * 1.18)

    plt.tight_layout()
    fig.savefig(output_path, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print(f"  {output_path.name}")


def plot_speed_vs_quality(results, output_path):
    """Dual-axis: avg call time (seconds) on left, decode tok/s on right."""
    fig, ax1 = plt.subplots(figsize=(12, 6))

    names = [short_name(r["model"]) for r in results]
    call_times = [r["runs"][0]["latency_avg_ms"] / 1000 for r in results]
    decode_speeds = [r["runs"][0]["token_stats"]["avg_decode_tok_per_s"] for r in results]

    x = np.arange(len(names))
    width = 0.35

    bars1 = ax1.bar(
        x - width / 2, call_times, width,
        color="#E53935", alpha=0.85, label="Avg Call Time (s)",
    )
    ax1.set_ylabel("Avg Time per LLM Call (seconds)", fontsize=12, color="#E53935")
    ax1.tick_params(axis="y", labelcolor="#E53935")

    ax2 = ax1.twinx()
    bars2 = ax2.bar(
        x + width / 2, decode_speeds, width,
        color="#1E88E5", alpha=0.85, label="Decode Speed (tok/s)",
    )
    ax2.set_ylabel("Avg Decode Speed (tok/s)", fontsize=12, color="#1E88E5")
    ax2.tick_params(axis="y", labelcolor="#1E88E5")

    for bar, val in zip(bars1, call_times):
        ax1.text(
            bar.get_x() + bar.get_width() / 2, bar.get_height() + 1,
            f"{val:.0f}s", ha="center", va="bottom", fontsize=8, color="#E53935",
        )
    for bar, val in zip(bars2, decode_speeds):
        ax2.text(
            bar.get_x() + bar.get_width() / 2, bar.get_height() + 0.3,
            f"{val:.0f}", ha="center", va="bottom", fontsize=8, color="#1E88E5",
        )

    ax1.set_xticks(x)
    ax1.set_xticklabels(names, rotation=25, ha="right", fontsize=9)
    ax1.set_title("Call Time vs Decode Speed", fontsize=14, fontweight="bold")

    lines1, labels1 = ax1.get_legend_handles_labels()
    lines2, labels2 = ax2.get_legend_handles_labels()
    ax1.legend(lines1 + lines2, labels1 + labels2, loc="upper left", fontsize=10)

    ax1.spines["top"].set_visible(False)
    ax2.spines["top"].set_visible(False)

    plt.tight_layout()
    fig.savefig(output_path, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print(f"  {output_path.name}")


def plot_coverage_heatmap(results, output_path):
    """Heatmap: tasks (rows) x models (columns)."""
    tasks = list(TASK_KEYWORDS.keys())
    names = [short_name(r["model"]) for r in results]

    matrix = np.zeros((len(tasks), len(names)))

    for j, r in enumerate(results):
        func_names = [fn.lower() for fn in r["runs"][0]["function_names"]]
        for i, task in enumerate(tasks):
            keywords = TASK_KEYWORDS[task]
            if any(kw in fn for kw in keywords for fn in func_names):
                matrix[i][j] = 1.0

    x_labels = []
    for j, name in enumerate(names):
        count = int(matrix[:, j].sum())
        x_labels.append(f"{name}\n({count}/{len(tasks)})")

    fig, ax = plt.subplots(figsize=(13, 6))

    cmap = mcolors.ListedColormap(["#EEEEEE", "#4CAF50"])
    bounds = [-0.5, 0.5, 1.5]
    norm = mcolors.BoundaryNorm(bounds, cmap.N)

    ax.imshow(matrix, cmap=cmap, norm=norm, aspect="auto")

    ax.set_xticks(np.arange(len(names)))
    ax.set_xticklabels(x_labels, rotation=0, ha="center", fontsize=8)
    ax.set_yticks(np.arange(len(tasks)))
    ax.set_yticklabels(tasks, fontsize=10)
    ax.xaxis.set_ticks_position("bottom")

    for i in range(len(tasks)):
        for j in range(len(names)):
            symbol = "\u2713" if matrix[i][j] == 1.0 else "\u2014"
            color = "white" if matrix[i][j] == 1.0 else "#BDBDBD"
            ax.text(j, i, symbol, ha="center", va="center",
                    fontsize=13, fontweight="bold", color=color)

    ax.set_title("Task Coverage by Model", fontsize=14, fontweight="bold")

    ax.set_xticks(np.arange(-0.5, len(names), 1), minor=True)
    ax.set_yticks(np.arange(-0.5, len(tasks), 1), minor=True)
    ax.grid(which="minor", color="white", linewidth=2)
    ax.tick_params(which="minor", size=0)

    plt.tight_layout()
    fig.savefig(output_path, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print(f"  {output_path.name}")


def main():
    results = load_results()
    if not results:
        print(f"No benchmark results found in {RESULTS_DIR}")
        sys.exit(1)

    print(f"Found {len(results)} benchmark results\n")
    print("Generating charts:")
    plot_timing_breakdown(results, RESULTS_DIR / "chart_timing.png")
    plot_speed_vs_quality(results, RESULTS_DIR / "chart_speed_vs_quality.png")
    plot_coverage_heatmap(results, RESULTS_DIR / "chart_coverage.png")
    print(f"\nAll charts saved to {RESULTS_DIR}")


if __name__ == "__main__":
    main()

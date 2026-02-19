#!/usr/bin/env python3
"""Eval harness: check cleaning function output against golden assertions.

Usage:
    # Eval a single model's output
    python benchmarks/eval/run_eval.py \
        --functions benchmarks/results/cleaning_functions_Qwen3-14B.py \
        --data benchmarks/benchmark_data.jsonl \
        --golden benchmarks/eval/golden/benchmark_golden.jsonl

    # Eval all models in a results directory
    python benchmarks/eval/run_eval.py \
        --functions-dir benchmarks/results/ \
        --data benchmarks/benchmark_data.jsonl \
        --golden benchmarks/eval/golden/benchmark_golden.jsonl
"""

import argparse
import copy
import json
import re
import sys
from pathlib import Path

# Allow importing from project root
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from recursive_cleaner.apply import load_cleaning_module


def load_data(data_path: str) -> list[dict]:
    """Load JSONL data as list of dicts."""
    records = []
    with open(data_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                records.append(json.loads(line))
    return records


def load_golden(golden_path: str) -> list[dict]:
    """Load golden assertions from JSONL."""
    assertions = []
    with open(golden_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                assertions.append(json.loads(line))
    return assertions


def extract_numeric(value) -> float | None:
    """Extract a numeric value, stripping units/currency."""
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        cleaned = re.sub(r"[^\d.\-]", "", value)
        if not cleaned or cleaned in (".", "-", "-."):
            return None
        try:
            return float(cleaned)
        except ValueError:
            return None
    return None


def check_assertion(actual, expected, match_mode: str = "exact") -> bool:
    """Check if actual matches expected according to match_mode."""
    if match_mode == "exact":
        return actual == expected
    elif match_mode == "numeric_close":
        a = extract_numeric(actual)
        b = extract_numeric(expected)
        if a is None or b is None:
            return False
        return abs(a - b) < 0.01
    elif match_mode == "contains":
        return str(expected) in str(actual)
    return False


def run_eval(data: list[dict], clean_fn, assertions: list[dict]) -> dict:
    """Run all golden assertions against cleaned data."""
    cleaned = [clean_fn(copy.deepcopy(record)) for record in data]

    results = {
        "total": len(assertions),
        "passed": 0,
        "failures": [],
        "by_issue_type": {},
        "by_field": {},
    }

    for assertion in assertions:
        idx = assertion["record_index"]
        field = assertion["field"]
        expected = assertion["expected"]
        issue_type = assertion.get("issue_type", "unknown")
        match_mode = assertion.get("match_mode", "exact")

        # Init aggregation buckets
        for bucket_key, bucket_name in [
            (issue_type, "by_issue_type"),
            (field, "by_field"),
        ]:
            if bucket_key not in results[bucket_name]:
                results[bucket_name][bucket_key] = {"total": 0, "passed": 0}
            results[bucket_name][bucket_key]["total"] += 1

        # Bounds check
        if idx >= len(cleaned):
            results["failures"].append({
                "record_index": idx,
                "field": field,
                "expected": expected,
                "actual": None,
                "issue_type": issue_type,
                "error": f"record_index {idx} out of range (data has {len(cleaned)} records)",
            })
            continue

        record = cleaned[idx]

        # Field existence check
        if field not in record:
            results["failures"].append({
                "record_index": idx,
                "field": field,
                "expected": expected,
                "actual": None,
                "issue_type": issue_type,
                "error": f"field '{field}' not found in cleaned record",
            })
            continue

        actual = record[field]

        if check_assertion(actual, expected, match_mode):
            results["passed"] += 1
            results["by_issue_type"][issue_type]["passed"] += 1
            results["by_field"][field]["passed"] += 1
        else:
            results["failures"].append({
                "record_index": idx,
                "field": field,
                "expected": expected,
                "actual": actual,
                "issue_type": issue_type,
            })

    # Compute percentages
    results["score_pct"] = (
        round(results["passed"] / results["total"] * 100, 1)
        if results["total"] > 0
        else 0
    )
    for bucket in [results["by_issue_type"], results["by_field"]]:
        for stats in bucket.values():
            stats["score_pct"] = (
                round(stats["passed"] / stats["total"] * 100, 1)
                if stats["total"] > 0
                else 0
            )

    return results


def format_markdown_report(model_name: str, results: dict) -> str:
    """Generate a markdown report from eval results."""
    lines = [
        f"# Eval Report: {model_name}",
        "",
        f"**Score: {results['passed']}/{results['total']} ({results['score_pct']}%)**",
        "",
        "## By Issue Type",
        "",
        "| Issue Type | Passed | Total | Score |",
        "|------------|--------|-------|-------|",
    ]
    for issue_type, stats in sorted(results["by_issue_type"].items()):
        lines.append(
            f"| {issue_type} | {stats['passed']} | {stats['total']} | {stats['score_pct']}% |"
        )

    lines.extend([
        "",
        "## By Field",
        "",
        "| Field | Passed | Total | Score |",
        "|-------|--------|-------|-------|",
    ])
    for field, stats in sorted(results["by_field"].items()):
        lines.append(
            f"| {field} | {stats['passed']} | {stats['total']} | {stats['score_pct']}% |"
        )

    if results["failures"]:
        lines.extend(["", "## Failures", ""])
        for f in results["failures"]:
            lines.append(
                f"- **Record {f['record_index']}.{f['field']}** ({f['issue_type']}): "
                f"expected `{f['expected']}`, got `{f['actual']}`"
            )
            if "error" in f:
                lines.append(f"  - {f['error']}")

    return "\n".join(lines) + "\n"


def format_comparison_table(all_results: dict[str, dict]) -> str:
    """Generate a comparison markdown table across models."""
    all_issue_types = set()
    for results in all_results.values():
        all_issue_types.update(results["by_issue_type"].keys())
    issue_types = sorted(all_issue_types)

    model_names = list(all_results.keys())
    header = "| Issue Type | " + " | ".join(model_names) + " |"
    separator = "|------------|" + "|".join(["-------" for _ in model_names]) + "|"

    lines = ["# Eval Comparison", "", header, separator]

    for it in issue_types:
        row = f"| {it} |"
        for model in model_names:
            stats = all_results[model].get("by_issue_type", {}).get(it, {})
            if stats:
                row += f" {stats['passed']}/{stats['total']} ({stats['score_pct']}%) |"
            else:
                row += " — |"
        lines.append(row)

    # Total row
    row = "| **Total** |"
    for model in model_names:
        r = all_results[model]
        row += f" **{r['passed']}/{r['total']} ({r['score_pct']}%)** |"
    lines.append(row)

    return "\n".join(lines) + "\n"


def model_slug(functions_path: str) -> str:
    """Extract model name from cleaning_functions_MODEL.py filename."""
    stem = Path(functions_path).stem
    if stem.startswith("cleaning_functions_"):
        return stem[len("cleaning_functions_"):]
    return stem


def main():
    parser = argparse.ArgumentParser(
        description="Evaluate cleaning functions against golden assertions"
    )
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--functions", help="Path to a single cleaning_functions.py")
    group.add_argument(
        "--functions-dir", help="Directory containing cleaning_functions_*.py files"
    )
    parser.add_argument("--data", required=True, help="Path to input data JSONL")
    parser.add_argument("--golden", required=True, help="Path to golden assertions JSONL")
    parser.add_argument(
        "--output-dir",
        default=None,
        help="Output directory (default: benchmarks/eval/results/)",
    )
    args = parser.parse_args()

    output_dir = (
        Path(args.output_dir)
        if args.output_dir
        else Path(__file__).parent / "results"
    )
    output_dir.mkdir(parents=True, exist_ok=True)

    data = load_data(args.data)
    assertions = load_golden(args.golden)
    print(f"Loaded {len(data)} records, {len(assertions)} assertions")

    if args.functions:
        function_files = [args.functions]
    else:
        func_dir = Path(args.functions_dir)
        function_files = sorted(
            str(p) for p in func_dir.glob("cleaning_functions_*.py")
        )
        if not function_files:
            print(f"No cleaning_functions_*.py files found in {func_dir}")
            sys.exit(1)

    all_results = {}

    for func_path in function_files:
        slug = model_slug(func_path)
        print(f"\nEvaluating: {slug}")

        try:
            module = load_cleaning_module(func_path)
        except Exception as e:
            print(f"  Error loading module: {e}")
            continue

        if not hasattr(module, "clean_data"):
            print(f"  No clean_data() function found")
            continue

        results = run_eval(data, module.clean_data, assertions)
        results["model"] = slug
        print(f"  Score: {results['passed']}/{results['total']} ({results['score_pct']}%)")

        # Write JSON
        json_out = {
            "model": slug,
            "summary": {
                "total": results["total"],
                "passed": results["passed"],
                "score_pct": results["score_pct"],
            },
            "by_issue_type": results["by_issue_type"],
            "by_field": results["by_field"],
            "failures": results["failures"],
        }
        json_path = output_dir / f"eval_{slug}.json"
        with open(json_path, "w") as f:
            json.dump(json_out, f, indent=2, default=str)
        print(f"  -> {json_path}")

        # Write markdown
        md_path = output_dir / f"eval_{slug}.md"
        md_path.write_text(format_markdown_report(slug, results))
        print(f"  -> {md_path}")

        all_results[slug] = results

    if len(all_results) > 1:
        comp_path = output_dir / "eval_comparison.md"
        comp_path.write_text(format_comparison_table(all_results))
        print(f"\n-> {comp_path}")

    print("\nDone!")


if __name__ == "__main__":
    main()

# Benchmarks

Performance benchmarks for Recursive Data Cleaner across MLX model sizes.

## Setup

```bash
# Install the cleaner with MLX backend
pip install -e ".[excel]"
pip install mlx-lm

# Or install from requirements
pip install mlx-lm tenacity
```

## Usage

```bash
# Run all models (small to large)
./benchmarks/run_all.sh

# Run all models with warmup
./benchmarks/run_all.sh --warmup

# Single model
python benchmarks/run_benchmark.py --model mlx-community/Qwen3-4B-4bit

# Custom chunk size
python benchmarks/run_benchmark.py --model mlx-community/Qwen3-8B-4bit --chunk-size 10

# Multiple runs for averaging
python benchmarks/run_benchmark.py --model mlx-community/Qwen3-4B-4bit --runs 3 --warmup

# All options
python benchmarks/run_benchmark.py \
  --model mlx-community/Qwen3-4B-4bit \
  --data benchmarks/benchmark_data.jsonl \
  --instructions benchmarks/benchmark_instructions.txt \
  --chunk-size 20 \
  --max-iterations 5 \
  --output-dir benchmarks/results/ \
  --runs 3 \
  --warmup
```

## Benchmark Dataset

`benchmark_data.jsonl` — 100 rows, 13 fields, covering 10+ quality issue categories:

| Category | Examples |
|----------|----------|
| Date formats | ISO, US, European, epoch, natural language |
| Phone formats | E.164, parenthesized, raw digits, dashed, international |
| Amount formats | $1,234.56, plain decimal, integer cents, USD suffix |
| HTML artifacts | `<b>`, `&amp;`, `<br/>`, entity refs |
| Whitespace | Leading/trailing spaces, double spaces |
| Case issues | UPPER, lower, Title, mixed in category field |
| Enum typos | "actve", "pendng", "chruned" in status field |
| Unit mixing | kg, lbs, g with various formatting |
| Tag formats | JSON arrays vs comma/semicolon-separated strings |
| Null/empty | null, empty string, whitespace-only in notes |

## Results

Results are saved to `benchmarks/results/` as JSON and Markdown.

### Model Lineup

All models from `lmstudio-community`. 8-bit quantization where possible, 4-bit for the 80B models to fit in memory. 2507 instruct revision used where available.

| # | Model | Active Params | Total Params | Type | Quant | Version |
|---|-------|---------------|--------------|------|-------|---------|
| 1 | Qwen3-4B-Instruct-2507 | 4B | 4B | Dense | 8-bit | 2507 |
| 2 | Qwen3-8B | 8B | 8B | Dense | 8-bit | original |
| 3 | Qwen3-14B | 14B | 14B | Dense | 8-bit | original |
| 4 | Qwen3-30B-A3B-Instruct-2507 | 3B | 30B | MoE | 8-bit | 2507 |
| 5 | Qwen3-Coder-30B-A3B | 3B | 30B | MoE Coder | 8-bit | — |
| 6 | Qwen3-Coder-Next | 3B | 80B | MoE Coder | 4-bit | — |
| 7 | Qwen3-Next-80B-A3B | 3.9B | 80B | MoE | 4-bit | — |

Note: 8B and 14B Instruct-2507 MLX-8bit not yet published; using original release for those sizes.

### Performance Matrix

| Model | Quant | Download | Load | Pipeline | LLM Calls | Functions | Avg Latency | Decode tok/s |
|-------|-------|----------|------|----------|-----------|-----------|-------------|--------------|
| Qwen3-4B-Instruct-2507 | 8-bit | — | — | — | — | — | — | — |
| Qwen3-8B | 8-bit | — | — | — | — | — | — | — |
| Qwen3-14B | 8-bit | — | — | — | — | — | — | — |
| Qwen3-30B-A3B-Instruct-2507 | 8-bit | — | — | — | — | — | — | — |
| Qwen3-Coder-30B-A3B | 8-bit | — | — | — | — | — | — | — |
| Qwen3-Coder-Next | 4-bit | — | — | — | — | — | — | — |
| Qwen3-Next-80B-A3B | 4-bit | — | — | — | — | — | — | — |

*Fill in after running `./benchmarks/run_all.sh` on your hardware.*
*Each model also generates `cleaning_functions_{model}.py` for qualitative code review.*

## Metrics Collected

### Timing (separated phases)
- **download_time_s**: Time to download model from HuggingFace (0 if cached)
- **load_time_s**: Time to load model weights into memory
- **warmup**: Time-to-first-token measurement from a short warmup prompt
- **pipeline_time_s**: Total cleaning pipeline time (excluding download/load)

### Pipeline
- **chunks**: Number of data chunks processed
- **llm_calls**: Total LLM generation calls made
- **functions_generated**: Number of cleaning functions produced
- **function_names**: Names of generated functions (for qualitative assessment)

### Latency
- **latency_avg_ms / min_ms / max_ms**: Per-call LLM latency distribution

### Tokens
- **total_prompt_tokens**: Sum of all prompt tokens across all calls
- **total_response_tokens**: Sum of all response tokens across all calls
- **avg_decode_tok_per_s**: Average decode throughput (response tokens / generation time)
- **per_call_stats**: Per-call breakdown (prompt tokens, response tokens, generation time, decode tok/s)

### Outputs (per model)
- `cleaning_functions_{model}.py` — generated cleaning code (for qualitative review)
- `cleaning_report_{model}.md` — pipeline report with functions and metrics
- `benchmark_{model}.json` — full metrics JSON
- `benchmark_{model}.md` — human-readable summary

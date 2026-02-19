# TODO — Recursive Data Cleaner

**Current: v1.1.0** | 620 tests | ~5k lines

## Roadmap to v2.0

```
v1.1.0 (done)  →  v1.2.0  →  v2.0.0  →  Phase 2 (RL)
Efficiency        Robustness  Distribution-aware  Trained model
```

### Project Scope

**What this system does**: Record-level format normalization and standardization for large/private datasets using local models.

**What v2.0 adds**: Distribution-aware cleaning — the LLM sees global field statistics (value distributions, frequency counts, percentile ranges) alongside business context from `instructions`, enabling it to make the same decisions a human data scientist would after EDA.

**What remains out of scope**: Cross-record deduplication, referential integrity, join-based operations. These are fundamentally different algorithms, not record-level transformations.

**Decision framework for data cleaning problems**:

| Problem type | Context needed | Current (v1.0.4) | v2.0 |
|-------------|---------------|-------------------|------|
| Format normalization | Record only | ✓ | ✓ |
| Categorical typo correction | Record + known valid values | ✓ (via instructions) | ✓ |
| Type coercion | Record only | ✓ | ✓ |
| Whitespace/encoding cleanup | Record only | ✓ | ✓ |
| Null representation | Record only | ✓ | ✓ |
| Distribution-aware normalization | Global stats | Partial (schema samples) | ✓ |
| Outlier handling | Global stats + business rules | ✗ | ✓ (with instructions) |
| Missing data strategy | Global stats + business rules | ✗ | ✓ (with instructions) |
| Business rule validation | Business rules only | ✓ (via instructions) | ✓ |
| Cross-record dedup | Full dataset pairwise | ✗ | ✗ (out of scope) |
| Referential integrity | Join logic | ✗ | ✗ (out of scope) |

---

## Tier 1 — High Impact, Low Effort ✓

### ~~1. Inline test-case generation~~ ✓
> Done. Added `<test_cases>` block to XML schema, `_parse_test_cases()` in `response.py`, `validate_test_cases()` in `validation.py`, wired into `cleaner.py` pipeline with retry-on-failure feedback loop.

### ~~2. Schema-powered prompting~~ ✓
> Done. Enhanced `schema.py` to collect unique sample values (up to 5, deduplicated) + null rates. `format_schema_for_prompt()` now outputs field inventory with inline null percentages.

### ~~3. Before/after metric gate~~ ✓
> Done. Added `check_function_effect()` in `metrics.py`, wired into `cleaner.py` pipeline. Rejects no-op functions with retry feedback. Uses fresh sample data to avoid mutation from prior validation.

### ~~4. Sample transformations in cleaning report~~ ✓
> Done. Added `capture_transformations()` in `report.py`, captures up to 5 before/after pairs per function at acceptance time in `cleaner.py`. Report renders changed fields only under "Sample Transformations" subsection.

---

## v1.1.0 — Pipeline Efficiency ✓

### ~~5. `enable_thinking` parameter for MLX backend~~ ✓
> Done. Added `enable_thinking: bool = True` to `MLXBackend.__init__()`. When `False`, passes `enable_thinking=False` through to `apply_chat_template`, suppressing Qwen3 `<think>` blocks. Default `True` omits the kwarg entirely (preserves current behavior).

### ~~6. Cumulative cross-chunk field dedup~~ ✓
> Done. Removed per-chunk `_fields_covered` reset. Field coverage now accumulates across the entire pipeline run. The existing AST-based `extract_modified_fields` + overlap check handles both within-chunk and cross-chunk duplicate field functions.

### ~~7. Adaptive iteration budget per chunk~~ ✓
> Done. Added `fruitless_iterations` counter in `_process_chunk`. After 2 consecutive iterations that produce no code, remaining iterations are skipped. Counter resets when a function is accepted. Validation failures (with error feedback) don't count as fruitless.

---

## v1.2.0 — Robustness & Verification

Ensure generated functions work together and the quality gates hold on diverse data. Prepares the foundation for v2.0.

### 8. Composition testing
> ~50 lines | `validation.py`

After all functions are generated, run them in sequence on sample data. Verify output is still valid (no crashes, types preserved). Catches: function A outputs `"75.00 kg"`, function B tries to parse it as a number. One extra pass, no LLM calls.

### ~~9. Relevance-filtered context window~~ ✓
> Done. Added optional `chunk` param to `build_context()`. Scores functions by word overlap between docstring/name and chunk text. Selects by relevance, displays in generation order. Falls back to FIFO when no chunk provided (backward compatible).

### 10. Parallel chunk processing
> ~60 lines | `cleaner.py`

Chunks are independent. With API backends (LM Studio, Ollama), process 2-3 concurrently via `concurrent.futures.ThreadPoolExecutor` (stdlib). MLX stays sequential (single GPU). Merge results after. ~2-3x wall-time reduction for remote backends.

### 11. Diverse evaluation datasets
> ~200 lines | `benchmarks/`

Quality gates (test cases, metric gate) are currently validated only against our synthetic benchmark — a "friendly" dataset with textbook issues. Add 3-5 stress-test scenarios:
- **Partially clean data** — 50-80% of rows already correct. Do functions correctly target only the dirty subset?
- **Ambiguous issues** — "NY" (abbreviation or typo?), "N/A" (null or literal?). Does the model generate reasonable test cases for edge cases?
- **Domain-specific patterns** — medical codes, financial instruments. Patterns the LLM might misunderstand.
- **Scale test** — 1000+ rows with chunk boundary effects.

This validates that the quality gates work beyond "easy mode" before building v2.0 on top of them.

---

## v2.0.0 — Distribution-Aware Cleaning

**Theme**: The LLM sees what a human data scientist sees after EDA. Combined with business context from `instructions`, it can make distribution-informed cleaning decisions — not just format normalization.

### 12. Global distribution stats pass
> ~80 lines | new `stats.py`

Pre-processing scan before chunking. No LLM calls, just stdlib `Counter` objects and basic math. Computes per-field:
- **Categorical fields**: Top-N value counts with percentages, unique count
- **Numeric fields**: min, max, mean, median, p1/p99
- **All fields**: Null rate, empty string rate, type distribution (what % are strings vs numbers vs booleans)

Output format injected into prompt:
```
=== FIELD DISTRIBUTIONS ===
status: active (4,521, 72%), pending (1,203, 19%), churned (498, 8%),
        "actve" (23, 0.4%), "ACTIVE" (12, 0.2%)  ← clearly errors
price:  min=0.99, max=49,999.00, median=34.50, p99=299.00
        1 value > $10,000 (outlier?)
phone:  38% null, 45% E.164 format, 12% US parenthesized, 5% raw digits
```

With this context, the LLM can: normalize toward the dominant format, identify statistical outliers, and apply user-specified business rules for edge cases.

### 13. Distribution-injected prompting
> ~30 lines | `prompt.py`, `cleaner.py`

Add `=== FIELD DISTRIBUTIONS ===` section to prompt template between schema and data chunk. Wire stats pass output into `build_prompt()`. The LLM now sees: business instructions + field distributions + schema + sample chunk — the same context a human has after EDA + stakeholder conversation.

### 14. Golden test extraction
> ~80 lines | new `golden.py`

From benchmark data, auto-extract edge cases into a regression test file. Next run with a different model, generated functions get tested against known-good transformations. Bridges to RL training (becomes part of the evaluation set).

### 15. `--compare` mode
> ~100 lines | `cli.py`, new `compare.py`

Run same data through two models, diff generated functions side by side. With distribution-aware cleaning, model quality variance matters more — different models may interpret distributions differently. Output: markdown table of coverage, function quality, timing.

### 16. DataCleanBench packaging
> ~150 lines | new `benchmark/` restructure

Package the evaluation infrastructure as a standalone benchmark for LLM data cleaning:
- Frozen evaluation set (never changes, scores are comparable across time)
- Scoring rubric (weighted: compiles, safe, executes, correct, idempotent, composable)
- Submission format for plugging in any model
- Leaderboard-ready output

There's no standardized LLM data cleaning benchmark. This fills a real niche and gives the project visibility beyond a standalone library.

---

## Phase 2 — Dedicated Model via RL

Train a small dedicated model using pure RL (GRPO) with the existing validation pipeline as programmatically verifiable reward functions. No SFT or DPO — preserve the full search space so the model can discover solutions that general-purpose models never would.

**Why skip SFT/DPO**: SFT caps the model at teacher quality (it can only imitate). DPO further narrows by saying "this style, not that." Both constrain what the model can discover. Pure RL with verifiable rewards has no ceiling — the model is rewarded for *what works*, not for *what looks like the teacher's output*. DeepSeek-R1 demonstrated this: RL-only training produced emergent strategies that SFT models never developed.

**Why this task is uniquely suited**: Most RL-for-LLMs tasks need subjective human preference labels. This system has **deterministic, binary rewards** — the function either fixes the data or it doesn't. Closer to AlphaGo (clear win/lose) than typical RLHF (annotator disagreement). A 4B model trained with RL on only this task dedicates 100% of its parameters to it, while a 70B general-purpose model wastes capacity on poetry, history, and roleplay.

### Prerequisites

- [x] Inline test-case generation (#1) — reward signal for function correctness
- [x] Schema-powered prompting (#2) — ensures full field coverage in prompts
- [x] Before/after metric gate (#3) — reward signal for actual improvement
- [ ] Composition testing (#8) — reward signal for robustness
- [ ] Golden test extraction (#14) — evaluation set for RL iterations
- [ ] Distribution stats pass (#12) — richer training prompts
- [ ] DataCleanBench (#16) — standardized evaluation framework

### Step 1: Format Bootstrapping via Constrained Decoding

Instead of teaching format through SFT (which would bias content), use **grammar-constrained generation** during GRPO rollouts. A formal grammar forces valid XML structure while the model has complete freedom in what it writes *inside* the tags:

```
root     ::= "<cleaning_analysis>" issues function status "</cleaning_analysis>"
issues   ::= "<issues_detected>" issue+ "</issues_detected>"
issue    ::= "<issue id=\"" [0-9]+ "\" solved=\"" ("true"|"false") "\">" freetext "</issue>"
function ::= "<function_to_generate>" name docstring code "</function_to_generate>"
name     ::= "<name>" freetext "</name>"
docstring::= "<docstring>" freetext "</docstring>"
code     ::= "<code>```python\n" freetext "\n```</code>"
status   ::= "<chunk_status>" ("clean"|"needs_more_work") "</chunk_status>"
freetext ::= [^<]+
```

This separates two concerns completely:
- **Structure** → handled by the grammar at generation time (zero learning cost)
- **Intelligence** → what the model writes inside the tags (100% of RL training budget)

No format SFT, no weight changes for structure. Every GRPO rollout is structurally valid XML from step 1, so all training pressure goes to the hard part: writing correct data cleaning code.

Tools: MLX structured generation, llama.cpp GBNF grammars, or Outlines library.

### Step 2: Golden Data Pairs + Corruption Pipeline

**The core reward signal**: the model isn't scored on code quality — it's scored on **data transformation correctness**. Start with clean data, corrupt it, and reward the model for writing functions that reverse the corruption.

```
1. Acquire clean, well-formatted datasets (ground truth)
2. Apply corruption functions to create messy versions
3. Corrupted data + cleaning instructions = GRPO training prompt
4. Reward = how close the generated function brings data back to ground truth
```

**Clean data sources** (already cleaned by schema constraints or curation):
- Government open data portals (data.gov, EU Open Data)
- Kaggle competition datasets
- HuggingFace curated datasets
- UCI ML Repository
- Any database export with enforced schemas

**Corruption functions** (write once, apply to any clean dataset):

| Transformation Type | Corruption Examples |
|---------------------|-------------------|
| Format normalization | ISO dates → MM/DD/YYYY, epoch, "June 18, 2024" |
| Phone formats | E.164 → "(555) 123-4567", raw digits, spaces |
| Currency/amounts | "1234.56" → "$1,234.56", "1234.56 USD", integer cents |
| Unit mixing | "75 kg" → "165 lbs", "33500 g", no units |
| Typo injection | "active" → "actve", "ACTIVE", "actvie" |
| Case scrambling | "New York" → "new york", "NEW YORK", "nEw yOrK" |
| Whitespace noise | Leading/trailing spaces, double spaces, tabs |
| HTML artifacts | Clean text → `<p>text</p>`, `&amp;`, `<br/>` |
| Null scattering | Valid values → randomly replaced with None, "", "N/A", "null" |
| Encoding issues | Clean strings → URL-encoded, HTML entities, Unicode escapes |
| Structural mixing | Lists → comma-separated strings, semicolon-delimited |
| Type coercion | Numbers → strings, booleans → "yes"/"no"/"1"/"0" |
| **Distribution corruption** | Inject minority format variants, synthetic outliers, correlated nulls |

Instructions are derived automatically from the corruptions applied: "Normalize dates to ISO 8601. Phones to E.164. Fix typos in status field."

**Generalization comes from transformation diversity, not domain diversity.** The model learns *patterns of normalization* — date formatting is the same pattern whether it's hospital admissions or ecommerce orders. A model trained on enough transformation types generalizes to unseen domains that have the same types of issues. Both domain and transformation diversity help, but transformation diversity is what drives generalization to novel datasets.

Covering 20-30 domains ensures the model doesn't overfit to specific field names or value distributions. Covering 12+ transformation types (above) ensures it handles whatever quality issues it encounters, even in domains it's never seen.

### Step 3: GRPO with Golden Data Rewards

**Reward function — ground truth comparison:**

```python
for record in sample:
    cleaned = generated_function(corrupted_record)
    score += field_match(cleaned[field], ground_truth[field])
reward = score / total_fields
```

`field_match`: exact match for categorical fields (status, tags), pattern/normalized comparison for structured fields (dates, phones, amounts).

**Full reward table:**

| Signal | What It Measures | Type |
|--------|-----------------|------|
| Python compiles | Syntax correctness | Binary gate |
| Safety scan passes | No dangerous code | Binary gate |
| Executes without error | Runtime stability | Binary gate |
| **Output matches ground truth** | **Semantic correctness** | **Core reward** |
| Function is idempotent | Stability | Bonus |
| Composition doesn't break | Inter-function safety | Bonus |

XML validity is free (grammar-constrained). The ground truth match is the reward that actually matters — everything else is a gate or bonus.

**Staged curriculum** (avoid sparse signal early):

| Phase | Rewards Active | What the Model Learns |
|-------|---------------|----------------------|
| A | Python compiles + safety scan | Write valid, safe Python |
| B | + runtime execution + ground truth match | Write Python that *correctly transforms data* |
| C | + idempotency + composition | Write Python that's *robust* |

Generate N candidates per prompt, score with reward functions, use relative ranking to update policy. **Every reward signal is programmatically verifiable.** No human labels needed.

### Step 4: Held-Out Evaluation Set

Reserve a benchmark set with excellent distribution across all problem types — data the model has **never seen during training**. Must include genuinely novel problem types (geospatial coordinates, encoded strings, nested JSON flattening) to test generalization, not memorization.

The existing benchmark suite (7 models, coverage heatmap, timing charts) applies directly for comparison.

### Step 5: Benchmark and Iterate

Run the RL-trained model through the benchmark suite alongside general-purpose models. Failure cases become harder prompts for the next GRPO iteration.

The system is a flywheel: failures surface gaps → new prompts target those gaps → RL training improves on those gaps → benchmark again.

**Target outcome**: A Qwen3-4B LoRA adapter (~100MB) that exceeds general-purpose 30B+ models on this specific task. Not by imitating them — by discovering solutions they never found, guided by verifiable rewards.

**Target model**: Qwen3-4B base. Benchmarks showed 36 tok/s on Apple Silicon in general-purpose 8-bit. A specialized version produces shorter, more precise outputs — potentially 2-3x effective speedup from reduced token count alone.

### Phase 2.5: Adversarial Corruption Generator

After the basic GRPO loop is validated, replace hand-written corruption functions with a trained adversarial corruptor.

**Concept**: Train a second model to generate corruptions that the cleaner model can't reverse. The reward signals are symmetric:
```
Corruptor reward = 1 - cleaner_score(generated_corruption)
Cleaner reward   = cleaner_score(corrupted_data)
```

**Constraints** (prevent degenerate solutions):
- Corrupted values must parse as the same type (a corrupted date looks date-ish, not random bytes)
- Character edit distance stays below a threshold
- Corruption must be reversible in principle (obscure information, don't destroy it)

**Training strategy**: Freeze-and-alternate (not co-training) for stability. Always mix hand-written corruptions as a floor.

**Strategic value**: The cleaner is the product. The corruptor is proprietary training infrastructure — the moat.

---

## Completed

| Version | Features |
|---------|----------|
| v1.1.0 | Pipeline efficiency: `enable_thinking` param for MLX backend, cumulative cross-chunk field dedup, adaptive iteration budget |
| v1.0.4 | Tier 1 quality gates: inline test-case generation, schema-powered prompting, before/after metric gate, sample transformations in report |
| v1.0.3 | XLSX/ODS structured parsing fix, benchmark suite with MLX model comparison |
| v1.0.2 | Documentation completeness, version alignment |
| v1.0.1 | Return type validation, prompt signature clarity, duplicate field detection |
| v1.0.0 | Apply mode, Excel support, TUI color enhancement |
| v0.9.0 | CLI tool with MLX and OpenAI-compatible backends |
| v0.8.0 | Terminal UI with Rich dashboard |
| v0.7.0 | Markitdown (20+ formats), Parquet support, LLM-generated parsers |
| v0.6.0 | Latency metrics, import consolidation, cleaning report, dry-run mode |
| v0.5.x | Two-pass optimization, early termination, dangerous code detection |
| v0.4.0 | Holdout validation, dependency resolution, smart sampling, quality metrics |
| v0.3.0 | Text mode with sentence-aware chunking |
| v0.2.0 | Runtime validation, schema inference, callbacks, incremental saves |
| v0.1.0 | Core pipeline, chunking, docstring registry |

---

## What We're Not Doing

| Feature | Reason |
|---------|--------|
| Global deduplication | Requires pairwise comparison, fundamentally different algorithm |
| Referential integrity | Requires join logic, not record-level transformation |
| Agentic EDA framework | Small local models can't reliably write/execute arbitrary pandas code; structured prompting is the correct architecture for 4B-8B models |
| Config files (YAML/TOML) | Python is already config |
| Plugin system | No interfaces for single implementations |
| Vector retrieval for context | FIFO works; chromadb dependency not justified |
| Async/streaming pipelines | Sequential is predictable, complexity not justified |

---

## Philosophy Reminder

- **Simplicity over extensibility** — keep it lean
- **stdlib over dependencies** — only tenacity required
- **Functions over classes** — unless state genuinely helps
- **Delete over abstract** — no interfaces for single implementations
- **Retry over recover** — on error, retry with error in prompt
- **Wu wei** — let the LLM make decisions about data it understands
- **Honest scope** — do record-level cleaning well, don't claim to solve everything

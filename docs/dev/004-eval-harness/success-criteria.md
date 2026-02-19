# Session 004: Eval Harness + Golden Assertions

## Success Criteria

1. Golden assertion files exist for all 4 datasets:
   - `benchmarks/eval/golden/benchmark_golden.jsonl` (~72 assertions, 12 issue types)
   - `benchmarks/eval/golden/ecommerce_golden.jsonl` (~40 assertions)
   - `benchmarks/eval/golden/healthcare_golden.jsonl` (~40 assertions)
   - `benchmarks/eval/golden/financial_golden.jsonl` (~40 assertions)

2. Eval harness `benchmarks/eval/run_eval.py` supports:
   - Single model eval (`--functions`)
   - Multi-model eval (`--functions-dir`)
   - Three match modes: exact, numeric_close, contains
   - JSON + markdown output per model
   - Comparison table for multi-model runs
   - Reuses `load_cleaning_module()` from `recursive_cleaner/apply.py`

3. Tests in `tests/test_eval.py` cover:
   - Exact match pass/fail
   - Numeric close within/outside tolerance
   - Aggregation by issue type and field
   - Missing record index / missing field handling
   - Already-clean value assertions
   - File loading, model slug extraction, markdown report

4. All existing tests (666) + new eval tests pass.

## Files Created

- `benchmarks/eval/run_eval.py`
- `benchmarks/eval/golden/benchmark_golden.jsonl`
- `benchmarks/eval/golden/ecommerce_golden.jsonl`
- `benchmarks/eval/golden/healthcare_golden.jsonl`
- `benchmarks/eval/golden/financial_golden.jsonl`
- `tests/test_eval.py`
- `docs/dev/004-eval-harness/success-criteria.md`

## Files Modified

- `docs/dev/session-index.md`

# Tier 4 Handoff: Polish & Observability

## Completed
- [x] Phase 1: Latency Metrics
- [x] Phase 2: Import Consolidation
- [x] Phase 3: Cleaning Report
- [x] Phase 4: Dry-Run Mode

## Files Created/Modified

| File | Purpose | Lines Changed |
|------|---------|---------------|
| `recursive_cleaner/cleaner.py` | Latency tracking, report_path, dry_run params | +80 |
| `recursive_cleaner/output.py` | Enhanced import consolidation | +40 |
| `recursive_cleaner/report.py` | Markdown report generation | 120 (new) |
| `tests/test_latency.py` | Latency metrics tests | 160 (new) |
| `tests/test_report.py` | Report generation tests | 155 (new) |
| `tests/test_dry_run.py` | Dry run mode tests | 175 (new) |
| `tests/test_output.py` | Extended import consolidation tests | +55 |

## Key Decisions

1. **Latency uses perf_counter**: More accurate than `time.time()` for measuring elapsed time
2. **Import consolidation keeps both forms**: `import x` and `from x import y` are both kept when same module used differently
3. **Report path defaults to `cleaning_report.md`**: Set to `None` to disable
4. **Dry run makes one LLM call per chunk**: Gets issues without iterating to generate functions

## Deviations from Plan

None. All features implemented as specified in contracts.

## Test Coverage

| Test File | Tests | Purpose |
|-----------|-------|---------|
| test_latency.py | 7 | Timing, stats, events |
| test_output.py | +5 | Import consolidation |
| test_report.py | 9 | Report generation |
| test_dry_run.py | 7 | Dry run mode |

Total: 392 tests (was 365, +27 new)

## Known Issues

None.

## API Changes

New parameters on `DataCleaner`:
- `report_path: str | None = "cleaning_report.md"` - Where to write report
- `dry_run: bool = False` - Enable dry run mode

New events:
- `llm_call` - Emitted after each LLM call with `latency_ms`
- `issues_detected` - Emitted in dry run mode with detected issues
- `dry_run_complete` - Emitted at end of dry run
- `complete` now includes `latency_stats` dict

## Notes for Future

- Report format is simple markdown, could be templated in future
- Import consolidation handles `as` aliases but doesn't merge them intelligently
- Dry run could track unique issue types for deduplication in future

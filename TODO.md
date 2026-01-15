# TODO - Recursive Data Cleaner Roadmap

## Current Version: v0.6.0

392 tests passing, 2,967 lines. Tier 4 complete.

---

## Completed Work

| Version | Features |
|---------|----------|
| v0.1.0 | Core pipeline, chunking, docstring registry |
| v0.2.0 | Runtime validation, schema inference, callbacks, incremental saves |
| v0.3.0 | Text mode with sentence-aware chunking |
| v0.4.0 | Holdout validation, dependency resolution, smart sampling, quality metrics |
| v0.5.0 | Two-pass optimization, early termination, LLM agency |
| v0.5.1 | Dangerous code detection (AST-based security) |
| v0.6.0 | Latency metrics, import consolidation, cleaning report, dry-run mode |

---

## Patterns That Worked

These patterns proved high-value with low implementation effort:

1. **AST walking** - Dependency detection, dangerous code detection. ~50 lines each.
2. **LLM agency** - Let model decide chunk cleanliness, saturation, consolidation. Elegant.
3. **Retry with feedback** - On error, append error to prompt and retry. No complex recovery.
4. **Holdout validation** - Test on unseen data before accepting. Catches edge cases.
5. **Simple data structures** - List of dicts, JSON serialization. Easy to debug/resume.

---

## Tier 4: Polish & Observability ✅ COMPLETE (v0.6.0)

### Latency Metrics ✅
- [x] Time each LLM call
- [x] Track min/max/avg/total in progress events
- [x] Report in final summary
- **Implemented**: `_call_llm_timed()`, `_get_latency_summary()` in `cleaner.py`

### Import Consolidation ✅
- [x] Deduplicate imports across generated functions
- [x] Move to single import block at top of output file
- [x] Handle `from x import y` merging
- **Implemented**: `consolidate_imports()` in `output.py`

### Cleaning Report ✅
- [x] Generate markdown summary alongside `cleaning_functions.py`
- [x] List: issues found, functions generated, quality delta
- [x] Include per-chunk breakdown
- **Implemented**: `recursive_cleaner/report.py`

### Dry-Run Mode ✅
- [x] Analyze data without generating functions
- [x] Report issues that would be detected
- [x] Useful for data assessment before committing
- **Implemented**: `dry_run` parameter, `_process_chunk_dry_run()` in `cleaner.py`

---

## Future Considerations

Ideas that might be valuable but need more thought.

### Confidence Scoring
- LLM rates confidence in each generated function (high/medium/low)
- Low confidence = flag for human review
- **Question**: Does this actually help users, or just add noise?

### Before/After Examples
- User provides expected input→output pairs
- Validate generated functions match expectations
- **Question**: How to handle functions that transform data differently but correctly?

### Multi-File Batch Mode
- Process multiple files with shared function registry
- Functions learned from file A applied to file B
- **Question**: How to handle schema differences between files?

### Summary Buffer Memory
- Compress old function docstrings into summaries
- Keep recent functions verbatim
- **Question**: Does FIFO eviction already work well enough?

---

## Explicitly Deferred

These don't fit the project philosophy:

| Feature | Reason |
|---------|--------|
| Async multi-chunk | Complexity not justified; sequential is predictable |
| Global state awareness | Would require architectural changes |
| Vector retrieval | Adds chromadb dependency; FIFO works for typical use |
| Jinja2 templates | f-strings are simpler and sufficient |
| TypedDict state | Plain dicts are easier to debug |

---

## Philosophy Reminder

From CLAUDE.md:
- **Simplicity over extensibility** - Keep it lean
- **stdlib over dependencies** - Only tenacity required
- **Functions over classes** - Unless state genuinely helps
- **Delete over abstract** - No interfaces for single implementations
- **Retry over recover** - On error, retry with error in prompt
- **Wu wei** - Let the LLM make decisions about data it understands

---

## Known Limitation

**Stateful ops within chunks only** - Deduplication and aggregations don't work globally. This is architectural and accepted.

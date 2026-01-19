# TODO - Recursive Data Cleaner Roadmap

## Current Version: v0.9.0

502 tests passing, ~3,400 lines. CLI complete.

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
| v0.7.0 | Markitdown (20+ formats), Parquet support, LLM-generated parsers |
| v0.8.0 | Terminal UI with Rich dashboard, mission control aesthetic |
| v0.9.0 | CLI tool with MLX and OpenAI-compatible backends |

---

## Version Progression

| Version | Theme |
|---------|-------|
| v0.1-0.2 | Core pipeline + validation |
| v0.3-0.4 | Data quality assurance |
| v0.5-0.6 | Optimization + observability |
| v0.7-0.8 | Accessibility (formats + UI) |
| v0.9-1.0 | Complete workflow |

---

## Roadmap to v1.0

### v0.9.0 - CLI Tool ✅ COMPLETE

CLI implemented with:
- `recursive_cleaner/cli.py` - argparse CLI (346 lines)
- `backends/openai_backend.py` - OpenAI-compatible backend (71 lines)
- Commands: `generate`, `analyze`, `resume`
- Backends: MLX, OpenAI, LM Studio, Ollama (via --base-url)

### v1.0.0 - Apply Mode (~150 lines)

The final step: actually cleaning the data, not just generating functions.

```python
cleaner = DataCleaner(...)
cleaner.run()  # Generates cleaning_functions.py

# NEW: Apply to full dataset
cleaner.apply(output_path="cleaned_data.jsonl")
```

**Implementation:**
- [ ] `DataCleaner.apply(output_path)` method
- [ ] Stream-process file applying generated functions
- [ ] Progress callbacks for large files
- [ ] Validate output schema matches input
- [ ] CLI integration: `recursive-cleaner apply`

---

## Patterns That Worked

These patterns proved high-value with low implementation effort:

1. **AST walking** - Dependency detection, dangerous code detection. ~50 lines each.
2. **LLM agency** - Let model decide chunk cleanliness, saturation, consolidation. Elegant.
3. **Retry with feedback** - On error, append error to prompt and retry. No complex recovery.
4. **Holdout validation** - Test on unseen data before accepting. Catches edge cases.
5. **Simple data structures** - List of dicts, JSON serialization. Easy to debug/resume.

---

## What We're Not Doing

| Feature | Reason |
|---------|--------|
| Global deduplication | Adds complexity, breaks chunk-based philosophy |
| Built-in LLM backends | Users bring their own, keeps us dependency-free |
| Config files (YAML/TOML) | Python is already config, YAGNI |
| Plugin system | No interfaces for things with one implementation |
| Async multi-chunk | Complexity not justified; sequential is predictable |
| Vector retrieval | Adds chromadb dependency; FIFO works for typical use |

---

## Line Count Budget

| Component | Current | After v1.0 |
|-----------|---------|------------|
| Core library | ~3,000 | ~3,350 |
| Tests | ~4,000 | ~4,400 |

Staying under 3,500 lines for the library keeps us true to the philosophy.

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

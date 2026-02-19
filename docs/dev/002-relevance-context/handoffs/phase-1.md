# 002 — Relevance-Filtered Context Window

## Delivered

| File | Lines | Changes |
|------|-------|---------|
| `recursive_cleaner/context.py` | 65 | Added `_extract_words()` helper + relevance scoring path |
| `recursive_cleaner/cleaner.py` | 794 | Pass `chunk=` to both `build_context()` call sites |
| `tests/test_context.py` | 130 | 5 new tests for relevance filtering |

## Test Evidence

```
658 passed, 2 skipped in 16.84s
```

Previous: 653 passed. Delta: +5 (new context tests). Zero regressions.

## Key Decisions

1. **Word overlap scoring**: `_extract_words()` uses `re.findall(r"[a-z]{2,}", text.lower())` — extracts alpha tokens 2+ chars, ignoring JSON syntax, numbers, punctuation. Simple and effective for both structured (field names) and text (keywords) modes.

2. **Select by relevance, display in generation order**: Functions are scored by overlap with chunk text, but included in the context in their original generation order. The LLM sees a coherent progression, not a relevance-shuffled list.

3. **Backward compatible**: `chunk=""` default falls back to exact FIFO behavior. No breaking changes to public API.

4. **Budget filling with skip**: Unlike FIFO which breaks on first overflow, relevance mode skips oversized functions and continues checking smaller ones. Maximizes useful context within budget.

## Architecture Impact

- `build_context()` signature: `(functions, max_chars=8000, chunk="")` — new optional kwarg
- `context.py`: grew from 27 to 65 lines (added `import re`, helper function, relevance branch)
- No new modules, no new dependencies

# 002 — Relevance-Filtered Context Window

## Done When

- [ ] `build_context(functions, max_chars, chunk)` accepts optional chunk text
- [ ] When chunk provided, functions are selected by word overlap (docstring+name vs chunk)
- [ ] Selected functions are displayed in generation order (not relevance order)
- [ ] When chunk not provided, behavior is identical to current FIFO (backward compatible)
- [ ] Both call sites in `cleaner.py` pass the chunk
- [ ] All existing tests pass unchanged
- [ ] New tests cover: relevance beats recency, generation order preserved, fallback to FIFO

# v1.1.0 Success Criteria

## Done When

- [ ] `MLXBackend(enable_thinking=False)` passes `enable_thinking=False` through to `apply_chat_template`
- [ ] `MLXBackend(enable_thinking=True)` preserves current behavior (default)
- [ ] `_fields_covered` accumulates across chunks (no per-chunk reset)
- [ ] Cross-chunk duplicate field functions are rejected
- [ ] Adaptive iteration: if last 2 iterations produced no new functions, remaining iterations for that chunk are skipped
- [ ] All 613+ existing tests pass (zero regressions)
- [ ] New tests cover all three changes

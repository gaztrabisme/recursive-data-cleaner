# 003 — Composition Testing

## Done When

- [ ] `validate_composition(functions, sample_data, mode)` in validation.py
- [ ] Runs all functions in sequence on sample records, catches crashes and type mismatches
- [ ] Called in cleaner.py after optimization, before _write_output()
- [ ] Emits `composition_failed` event on failure
- [ ] Works for both structured (dict) and text (str) modes
- [ ] All existing tests pass unchanged
- [ ] New tests cover: clean composition passes, type mismatch caught, runtime error caught, text mode

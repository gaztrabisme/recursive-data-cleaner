# v1.0.0 Success Criteria

## Project-Level Success

- [ ] User can apply generated cleaning functions to full dataset
- [ ] CLI `apply` command works without writing Python code
- [ ] Data formats output same format (JSONL, CSV, JSON, Parquet, Excel)
- [ ] Text formats output markdown
- [ ] Streaming for JSONL/CSV (memory efficient)
- [ ] TUI transmission log has colored parsing
- [ ] All existing tests still pass (502+)

## Phase Success Criteria

### Phase 1: Core Apply Function

**Deliverables:**
- [ ] `recursive_cleaner/apply.py` created
- [ ] `apply_cleaning()` function implemented
- [ ] JSONL support (streaming)
- [ ] CSV support (streaming)
- [ ] JSON array support
- [ ] Progress callbacks working

**Verification:**
```bash
python -c "
from recursive_cleaner.apply import apply_cleaning
apply_cleaning('test.jsonl', 'cleaning_functions.py', 'out.jsonl')
"
cat out.jsonl  # Should contain cleaned data
```

### Phase 2: CLI Integration

**Deliverables:**
- [ ] `cmd_apply()` function in cli.py
- [ ] Argument parser for `apply` subcommand
- [ ] Error handling with correct exit codes

**Verification:**
```bash
recursive-cleaner apply test.jsonl -f cleaning_functions.py -o out.jsonl
echo $?  # Should be 0
```

### Phase 3: Extended Format Support

**Deliverables:**
- [ ] Parquet input/output (if pyarrow available)
- [ ] Excel input/output (if openpyxl available)
- [ ] Text formats → markdown output
- [ ] Default output path generation (`input.cleaned.ext`)

**Verification:**
```bash
# Excel
recursive-cleaner apply test.xlsx -f cleaning_functions.py
ls test.cleaned.xlsx  # Should exist

# PDF → markdown
recursive-cleaner apply doc.pdf -f cleaning_functions.py
ls doc.cleaned.md  # Should exist
```

### Phase 4: TUI Enhancement

**Deliverables:**
- [ ] Transmission log parses XML elements
- [ ] Color scheme applied per contract
- [ ] Issue accent colors cycle

**Verification:**
```bash
recursive-cleaner generate test.jsonl -p mlx -m mlx-model --tui
# Visual inspection: colors visible in transmission log
```

### Phase 5: Tests

**Deliverables:**
- [ ] `tests/test_apply.py` created
- [ ] Unit tests for each format
- [ ] Integration test with real cleaning functions
- [ ] Error case tests
- [ ] TUI color tests
- [ ] All tests passing

**Verification:**
```bash
pytest tests/test_apply.py -v
pytest tests/ -v  # 502+ tests still passing
```

## Final Checklist

### Apply Mode
- [ ] `recursive_cleaner/apply.py` exists
- [ ] CLI `apply` command works
- [ ] JSONL streaming works
- [ ] CSV streaming works
- [ ] JSON array works
- [ ] Parquet works (with pyarrow)
- [ ] Excel .xlsx works (with openpyxl)
- [ ] Excel .xls → .xlsx works
- [ ] Text formats → .md works
- [ ] Progress callbacks work
- [ ] Error handling correct

### TUI Enhancement
- [ ] XML tags colored cyan
- [ ] Attributes colored yellow
- [ ] Function names colored green
- [ ] Issues colored (solved=dim, unsolved=bright)
- [ ] Status colored (clean=green, needs_more_work=yellow)
- [ ] Code blocks syntax highlighted
- [ ] Issue accents cycle colors

### Documentation
- [ ] README updated with apply command
- [ ] CLAUDE.md updated to v1.0.0
- [ ] pyproject.toml version bumped

### Quality
- [ ] All new tests passing
- [ ] All existing 502+ tests passing
- [ ] No regressions

# Success Criteria - Tier 4: Polish & Observability

## Project-Level Success (v0.6.0)
- [ ] All 4 Tier 4 features implemented and tested
- [ ] Existing 365 tests still pass
- [ ] New tests for each feature (target: ~20 new tests)
- [ ] Total codebase stays under 3,000 lines
- [ ] No new dependencies beyond stdlib + tenacity

---

## Feature 1: Latency Metrics

### Deliverables
- [ ] `call_llm` wrapper in `cleaner.py` tracks timing
- [ ] Latency stats accumulated during run
- [ ] New event types emitted via `_emit()`
- [ ] Tests in `tests/test_latency.py`

### Success Criteria
- [ ] Each LLM call duration is recorded in milliseconds
- [ ] Stats tracked: `llm_call_count`, `total_ms`, `min_ms`, `max_ms`
- [ ] Event `llm_call` emitted with `latency_ms` field
- [ ] Event `complete` includes aggregated latency stats
- [ ] Test: mock LLM with delay, verify latency captured
- [ ] Test: verify min/max/avg calculations correct

### Verification Commands
```bash
pytest tests/test_latency.py -v
```

---

## Feature 2: Import Consolidation

### Deliverables
- [ ] AST-based import extraction in `output.py`
- [ ] `from x import a, b` merging logic
- [ ] Tests in `tests/test_output.py` (extend existing)

### Success Criteria
- [ ] `import re` + `import re` → single `import re`
- [ ] `from typing import List` + `from typing import Dict` → `from typing import Dict, List`
- [ ] `import json` + `from json import dumps` → both kept (different forms)
- [ ] Imports sorted alphabetically in output
- [ ] Test: duplicate imports consolidated
- [ ] Test: from-imports merged correctly

### Verification Commands
```bash
pytest tests/test_output.py -v -k import
```

---

## Feature 3: Cleaning Report

### Deliverables
- [ ] `report.py` module for markdown generation
- [ ] Integration into `cleaner.py` to write report after run
- [ ] Optional `report_path` parameter on DataCleaner
- [ ] Tests in `tests/test_report.py`

### Success Criteria
- [ ] Report includes: file processed, total chunks, functions generated
- [ ] Report lists each function with name + first line of docstring
- [ ] Report shows quality delta if `track_metrics=True`
- [ ] Report written to `cleaning_report.md` by default (or custom path)
- [ ] Test: report contains expected sections
- [ ] Test: report includes quality metrics when available

### Verification Commands
```bash
pytest tests/test_report.py -v
```

---

## Feature 4: Dry-Run Mode

### Deliverables
- [ ] `dry_run` parameter on DataCleaner
- [ ] When True: analyze chunks, emit events, but don't generate functions
- [ ] Tests in `tests/test_dry_run.py`

### Success Criteria
- [ ] `dry_run=True` processes all chunks
- [ ] Events emitted: `chunk_start`, `issues_detected`, `chunk_done`
- [ ] No functions added to `self.functions`
- [ ] No `cleaning_functions.py` written
- [ ] New event type `issues_detected` with list of issues from LLM
- [ ] Test: dry run emits correct events
- [ ] Test: dry run doesn't write output file

### Verification Commands
```bash
pytest tests/test_dry_run.py -v
```

---

## Integration Success Criteria

- [ ] All existing tests pass: `pytest tests/ -v` (365+ tests)
- [ ] New Tier 4 tests pass
- [ ] Line count check: `find recursive_cleaner -name "*.py" | xargs wc -l` < 3000 total
- [ ] No new dependencies in `pyproject.toml`

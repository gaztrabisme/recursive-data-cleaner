# Refactoring Plan

## Overview

Minimal intervention needed. The codebase is healthy — just documentation drift to fix.

## Phase 1: Quick Wins

### Task 1.1: Update CLAUDE.md

**What**: Sync CLAUDE.md with v0.5.0 state
**Why**: Current docs describe v0.2.0, misleading developers
**Files**: `/CLAUDE.md`
**Risk**: Low

**Changes needed**:
1. Update version table (add v0.3.0, v0.4.0, v0.5.0)
2. Update "Current State" line (344 tests, 2,575 lines)
3. Update file structure section with new modules:
   - `optimizer.py` — Two-pass consolidation
   - `dependencies.py` — Topological sort
   - `metrics.py` — Quality metrics
   - `vendor/chunker.py` — Sentence-aware chunking
4. Update line counts for existing files
5. Add new features to user experience example:
   - `optimize=True`
   - `early_termination=True`
   - `sampling_strategy="stratified"`
6. Update "Known Limitations" (several now fixed)
7. Add LLM agency concept explanation

**Verify**: Read updated CLAUDE.md, confirm accuracy

### Task 1.2: Update TODO.md

**What**: Mark completed tiers, note v0.5.0 status
**Why**: Currently shows Tier 2 as incomplete
**Files**: `/TODO.md`
**Risk**: Low

**Changes needed**:
1. Mark Tier 2 as complete (v0.4.0)
2. Mark Tier 3 "Two-Pass Optimization" as complete (v0.5.0)
3. Update current version
4. Note remaining Tier 3 items (Async, Global State) if desired

**Verify**: Read updated TODO.md

## Phase 2: Not Needed

No structural refactoring required. The codebase is well-organized.

## Phase 3: Context Documentation

Already covered in Phase 1. A single CLAUDE.md is appropriate for this codebase size.

## Out of Scope

| Item | Reason |
|------|--------|
| Split large test files | Tests are well-organized, large is fine |
| Module-specific CLAUDE.md | Overkill for 2,575 line library |
| Refactor any source code | Code is healthy, follows philosophy |
| Remove research docs | Useful historical reference |

## Execution Estimate

| Phase | Tasks | Time |
|-------|-------|------|
| Phase 1 | 2 | ~30 min |
| Total | 2 | ~30 min |

## Recommendation

Execute Phase 1 to sync documentation with code. Everything else can stay as-is.

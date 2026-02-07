# Implementation Plan: Text Mode v0.3.0

## Overview
Add text/prose cleaning mode to DataCleaner with sentence-aware chunking via vendored chonkie code.

## Technology Stack
| Layer | Choice | Rationale |
|-------|--------|-----------|
| Chunking | Vendored chonkie SentenceChunker | MIT license, ~150 lines, zero deps |
| Mode detection | File extension | Simple, predictable |
| Prompt | Separate template | Clean separation |

---

## Phase 1: Vendor Chunker

**Objective:** Extract and vendor chonkie's SentenceChunker with MIT attribution.

**Deliverables:**
- [ ] `recursive_cleaner/vendor/__init__.py`
- [ ] `recursive_cleaner/vendor/chunker.py` (~150 lines)
- [ ] `tests/test_vendor_chunker.py`

**Success Criteria:**
- [ ] SentenceChunker splits text by sentences
- [ ] Overlap between chunks works
- [ ] Short sentences merged correctly
- [ ] Position tracking (start_index, end_index) accurate
- [ ] All chunker tests pass

**Complexity:** Low

**Dependencies:** None

---

## Phase 2: Text Mode

**Objective:** Add mode parameter and text-specific prompt/validation.

**Deliverables:**
- [ ] Update `recursive_cleaner/cleaner.py` - add mode param, detection
- [ ] Update `recursive_cleaner/prompt.py` - add TEXT_PROMPT_TEMPLATE
- [ ] Update `recursive_cleaner/parsers.py` - use SentenceChunker for text
- [ ] Update `recursive_cleaner/validation.py` - handle str input
- [ ] `tests/test_text_mode.py`

**Success Criteria:**
- [ ] `mode="auto"` detects from extension
- [ ] `mode="text"` forces text mode
- [ ] Text chunks use sentence-aware splitting with overlap
- [ ] Schema inference skipped for text mode
- [ ] Generated functions use `def func(text: str)` signature
- [ ] Validation works with string input
- [ ] All text mode tests pass

**Complexity:** Medium

**Dependencies:** Phase 1

---

## Phase 3: Integration Test

**Objective:** Verify end-to-end with real text file.

**Deliverables:**
- [ ] Create sample text file with known issues
- [ ] Run DataCleaner in text mode
- [ ] Verify output is valid Python

**Success Criteria:**
- [ ] All 127+ existing tests still pass
- [ ] Text mode generates valid cleaning functions
- [ ] Functions chain correctly in clean_data()
- [ ] Line count < 1150

**Complexity:** Low

**Dependencies:** Phase 2

---

## Risk Register

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| Chunker edge cases | Low | Medium | Comprehensive tests |
| Prompt confusion | Low | Low | Clear separation of templates |
| Validation mismatch | Low | Low | Type checking in validation |

## Out of Scope
- Semantic chunking (requires ML deps)
- Token-based chunking (requires tokenizer)
- PDF/document parsing (separate concern - use markitdown externally)

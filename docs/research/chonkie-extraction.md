# Chonkie Chunking Library - Extraction Analysis

**Date:** 2025-01-14
**Repository:** https://github.com/chonkie-inc/chonkie
**Version Analyzed:** 1.5.2

## License Confirmation

**License:** MIT License
**Copyright:** 2025 Chonkie

The MIT license explicitly permits:
- Commercial use
- Modification
- Distribution
- Private use
- Sublicensing

Vendoring is fully permitted with attribution.

## Chunker Options Analysis

### Available Chunkers

| Chunker | Purpose | Dependencies | Complexity |
|---------|---------|--------------|------------|
| `TokenChunker` | Split by token count | tokenizer only | Low |
| `SentenceChunker` | Split by sentences with token limits | tokenizer + optional Cython | Medium |
| `RecursiveChunker` | Multi-level recursive splitting | tokenizer + RecursiveRules | Medium-High |
| `SemanticChunker` | Semantic similarity-based | embeddings + ML | High |
| `NeuralChunker` | Neural network based | transformers + torch | High |

### Recommendation: SentenceChunker

The `SentenceChunker` is best for our use case because:
1. Sentence-aware text chunking aligns with LLM prompt generation
2. Built-in overlap support via `chunk_overlap` parameter
3. Has a pure Python fallback when Cython extensions unavailable
4. Configurable delimiters and minimum sentence length
5. Character-based tokenizer available (no external tokenizer deps)

## Dependencies Analysis

### Core Dependencies (Required)

```
tqdm>=4.64.0     # Progress bars (used in BaseChunker batch processing)
numpy>=2.0.0     # Array operations (used in Chunk.embedding type hint only)
```

### Tokenizer Dependencies (Optional)

The chunkers use `AutoTokenizer` which supports multiple backends:
- **Built-in (no deps):** `"character"`, `"word"`, `"byte"`, `"row"`
- **Optional:** `tokenizers`, `tiktoken`, `transformers`

For our use case, the built-in `CharacterTokenizer` would work fine for text chunking since we care about character counts, not LLM tokens.

### Chonkie Internal Dependencies

```
chonkie.tokenizer.AutoTokenizer    # Tokenizer abstraction
chonkie.tokenizer.CharacterTokenizer  # Pure Python, no deps
chonkie.types.Chunk                # Dataclass for chunk output
chonkie.types.Sentence             # Internal dataclass for SentenceChunker
chonkie.logger                     # Optional logging (can be removed)
chonkie.pipeline.chunker           # Decorator for registry (can be removed)
chonkie.utils.Hubbie               # HuggingFace recipe loading (can be removed)
```

### Optional Cython Extensions

The SentenceChunker has optional Cython extensions:
- `c_extensions.split.split_text` - Fast sentence splitting
- `c_extensions.merge.find_merge_indices` - Fast merge calculation

These are **not required** - the code has pure Python fallbacks.

## Code Extraction Assessment

### Minimal Extraction (~200 lines)

To extract a minimal sentence-aware chunker, we would need:

1. **`Chunk` dataclass** (~50 lines simplified)
   - Remove: `id`, `context`, `embedding` fields, serialization methods
   - Keep: `text`, `start_index`, `end_index`, `token_count`

2. **`CharacterTokenizer`** (~40 lines)
   - The simplest tokenizer - counts characters
   - No external dependencies

3. **`SentenceChunker._split_text`** (~40 lines - Python fallback only)
   - Sentence splitting logic with configurable delimiters
   - Minimum character enforcement

4. **`SentenceChunker.chunk`** (~70 lines)
   - Main chunking loop with overlap support
   - Uses bisect for efficient split point finding

### What We Would Remove

- `@chunker` decorator and pipeline registry
- `from_recipe` class method (HuggingFace hub integration)
- `Hubbie` utility class
- Logger integration
- Batch processing (`chunk_batch`, multiprocessing)
- Cython extension support (keep Python fallbacks only)
- `Document` support
- `embedding` fields throughout
- `tqdm` progress bars
- `uuid` ID generation

### What We Would Simplify

- `AutoTokenizer` -> Direct `CharacterTokenizer` usage
- Remove `approximate` parameter (deprecated anyway)
- Remove `Sentence` intermediate class (inline the logic)
- Use `len(text)` directly instead of `tokenizer.count_tokens()`

## Complexity Assessment

**Verdict: Moderate complexity, worth extracting**

The core sentence splitting algorithm is elegant and handles edge cases well:
- Configurable sentence delimiters
- Minimum sentence length enforcement
- Chunk overlap via token-aware backtracking
- Proper index tracking for start/end positions

The fallback Python implementation is ~150 lines total when stripped of:
- Framework integration (decorators, registry)
- HuggingFace Hub integration
- Multi-backend tokenizer support
- Logging and progress bars
- Numpy embedding support

## Extracted Code (Minimal Version)

Here is what a minimal extraction would look like:

```python
"""Minimal sentence-aware text chunker extracted from chonkie.

Original: https://github.com/chonkie-inc/chonkie
License: MIT (Copyright 2025 Chonkie)
"""

from bisect import bisect_left
from dataclasses import dataclass
from itertools import accumulate
from typing import Literal, Optional, Union


@dataclass
class Chunk:
    """A chunk of text with position metadata."""
    text: str
    start_index: int
    end_index: int
    token_count: int  # In our case, character count

    def __len__(self) -> int:
        return len(self.text)


class SentenceChunker:
    """Split text into chunks based on sentence boundaries.

    Args:
        chunk_size: Maximum characters per chunk
        chunk_overlap: Characters to overlap between chunks
        min_sentences_per_chunk: Minimum sentences per chunk
        min_characters_per_sentence: Minimum characters for valid sentence
        delim: Sentence boundary delimiters
        include_delim: Where to include delimiter ("prev", "next", or None)
    """

    def __init__(
        self,
        chunk_size: int = 4000,
        chunk_overlap: int = 200,
        min_sentences_per_chunk: int = 1,
        min_characters_per_sentence: int = 12,
        delim: Union[str, list[str]] = [". ", "! ", "? ", "\n"],
        include_delim: Optional[Literal["prev", "next"]] = "prev",
    ):
        if chunk_size <= 0:
            raise ValueError("chunk_size must be positive")
        if chunk_overlap >= chunk_size:
            raise ValueError("chunk_overlap must be less than chunk_size")
        if min_sentences_per_chunk < 1:
            raise ValueError("min_sentences_per_chunk must be at least 1")

        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
        self.min_sentences_per_chunk = min_sentences_per_chunk
        self.min_characters_per_sentence = min_characters_per_sentence
        self.delim = [delim] if isinstance(delim, str) else delim
        self.include_delim = include_delim
        self._sep = "\x00"  # Internal separator (null char)

    def _split_into_sentences(self, text: str) -> list[str]:
        """Split text into sentences based on delimiters."""
        t = text
        for d in self.delim:
            if self.include_delim == "prev":
                t = t.replace(d, d + self._sep)
            elif self.include_delim == "next":
                t = t.replace(d, self._sep + d)
            else:
                t = t.replace(d, self._sep)

        splits = [s for s in t.split(self._sep) if s]

        # Merge short splits with previous sentence
        sentences = []
        current = ""
        for s in splits:
            if len(s) < self.min_characters_per_sentence:
                current += s
            elif current:
                current += s
                sentences.append(current)
                current = ""
            else:
                sentences.append(s)

            if len(current) >= self.min_characters_per_sentence:
                sentences.append(current)
                current = ""

        if current:
            sentences.append(current)

        return sentences

    def chunk(self, text: str) -> list[Chunk]:
        """Split text into overlapping chunks based on sentences."""
        if not text.strip():
            return []

        # Split into sentences with positions and character counts
        sentence_texts = self._split_into_sentences(text)
        if not sentence_texts:
            return []

        # Calculate positions
        positions = []
        current_pos = 0
        for sent in sentence_texts:
            positions.append(current_pos)
            current_pos += len(sent)

        # Character counts (our "tokens")
        char_counts = [len(s) for s in sentence_texts]

        # Cumulative character counts for bisect
        char_sums = list(accumulate([0] + char_counts))

        chunks = []
        pos = 0

        while pos < len(sentence_texts):
            # Find split point using bisect
            target = char_sums[pos] + self.chunk_size
            split_idx = bisect_left(char_sums, target) - 1
            split_idx = max(split_idx, pos + 1)  # At least one sentence
            split_idx = min(split_idx, len(sentence_texts))

            # Handle minimum sentences requirement
            if split_idx - pos < self.min_sentences_per_chunk:
                if pos + self.min_sentences_per_chunk <= len(sentence_texts):
                    split_idx = pos + self.min_sentences_per_chunk
                else:
                    split_idx = len(sentence_texts)

            # Create chunk
            chunk_sentences = sentence_texts[pos:split_idx]
            chunk_text = "".join(chunk_sentences)
            chunks.append(Chunk(
                text=chunk_text,
                start_index=positions[pos],
                end_index=positions[pos] + len(chunk_text),
                token_count=len(chunk_text),
            ))

            # Calculate next position with overlap
            if self.chunk_overlap > 0 and split_idx < len(sentence_texts):
                overlap_chars = 0
                overlap_idx = split_idx - 1

                while overlap_idx > pos and overlap_chars < self.chunk_overlap:
                    next_chars = overlap_chars + char_counts[overlap_idx]
                    if next_chars > self.chunk_overlap:
                        break
                    overlap_chars = next_chars
                    overlap_idx -= 1

                pos = overlap_idx + 1
            else:
                pos = split_idx

        return chunks
```

## Attribution Text (Required for Vendoring)

If we vendor this code, include this attribution:

```
Sentence chunking algorithm adapted from Chonkie
https://github.com/chonkie-inc/chonkie
Copyright (c) 2025 Chonkie
Licensed under the MIT License
```

## Recommendation

**Option A: Vendor minimal extraction (~150 lines)**
- Pro: Zero dependencies, full control
- Pro: Fits our "stdlib over dependencies" philosophy
- Con: Maintenance burden for bug fixes
- Con: Missing optimizations (Cython)

**Option B: Add chonkie as dependency**
- Pro: Get updates automatically
- Pro: Access to other chunkers if needed
- Con: Adds tqdm + numpy as transitive deps
- Con: More code than we need

**Option C: Write our own simple chunker**
- Pro: Exactly what we need, nothing more
- Pro: Full understanding of the code
- Con: May miss edge cases chonkie handles

**Suggested approach:** Start with Option A (vendor minimal extraction). The core algorithm is simple enough to understand and maintain. If we find bugs or need more features, we can either fix them ourselves or upgrade to Option B.

## Files to Create for Vendoring

If we proceed with vendoring:

```
recursive_cleaner/
    vendor/
        __init__.py
        chunker.py          # ~150 lines, the extraction above
        _attribution.txt    # MIT license attribution
```

## Next Steps

1. Review this analysis with the team
2. Decide on Option A, B, or C
3. If Option A: Create the vendor directory and extract the code
4. Write tests for the chunker integration
5. Update `parsers.py` to use the new sentence-aware chunker for text files

# Chonkie Text Chunking Library Research

**Research Date**: 2026-01-14
**Library Version**: 1.5.2 (as of Jan 5, 2026)
**Repository**: https://github.com/chonkie-inc/chonkie
**PyPI**: https://pypi.org/project/chonkie/

## Executive Summary

Chonkie is a well-designed, modular text chunking library for RAG pipelines. It follows a "minimum installs" philosophy similar to our project principles. The library offers multiple chunking strategies from simple token-based to semantic-aware, with optional heavy dependencies only when advanced features are needed.

**Recommendation**: Consider using chonkie for sentence-aware and token-based chunking, but **only with minimal dependencies**. For our current use case (chunking data for LLM context windows), rolling our own may still be simpler.

---

## 1. What It Does

Chonkie provides 9+ chunking strategies for splitting text into chunks suitable for LLM processing:

| Chunker | Purpose | Dependencies |
|---------|---------|--------------|
| **TokenChunker** | Fixed-size token chunks with overlap | Core only |
| **FastChunker** | SIMD-accelerated byte-based (100+ GB/s) | C extensions |
| **SentenceChunker** | Sentence boundary-aware splitting | Core only |
| **RecursiveChunker** | Hierarchical delimiter-based splitting | Core only |
| **SemanticChunker** | Embedding similarity boundaries | sentence-transformers |
| **LateChunker** | Embed-then-split approach | sentence-transformers |
| **CodeChunker** | Structurally-aware code splitting | tree-sitter |
| **NeuralChunker** | Neural model-based boundaries | torch, transformers |
| **SlumberChunker** | LLM-driven semantic chunking | LLM provider SDK |

---

## 2. Installation

### Minimal Install (Recommended)
```bash
pip install chonkie
```

**Core dependencies only:**
- `tqdm>=4.64.0`
- `numpy>=2.0.0`

**Package size:**
- Wheel: 505KB
- Installed: ~49MB (vs 80-171MB for alternatives)

### Selective Installs
```bash
# Token chunking with HuggingFace tokenizers
pip install "chonkie[tokenizers]"

# Semantic chunking (adds sentence-transformers)
pip install "chonkie[semantic]"

# Full install (all optional deps including torch)
pip install "chonkie[all]"
```

### Python Version
- Requires: **Python >= 3.10**
- Builds available: Python 3.10 - 3.14

---

## 3. API Usage

### Basic Token Chunking
```python
from chonkie import TokenChunker

# Default: character-based tokenizer (no deps)
chunker = TokenChunker(chunk_size=512, chunk_overlap=50)
chunks = chunker("Your text here")

for chunk in chunks:
    print(f"Text: {chunk.text}")
    print(f"Tokens: {chunk.token_count}")
    print(f"Start: {chunk.start_index}, End: {chunk.end_index}")
```

### With HuggingFace Tokenizer
```python
from chonkie import TokenChunker
from tokenizers import Tokenizer

tokenizer = Tokenizer.from_pretrained("gpt2")
chunker = TokenChunker(tokenizer=tokenizer, chunk_size=512, chunk_overlap=50)
chunks = chunker("Your text here")
```

### Sentence-Aware Chunking
```python
from chonkie import SentenceChunker

chunker = SentenceChunker(
    chunk_size=512,
    chunk_overlap=50,
    min_sentences_per_chunk=1,
    min_characters_per_sentence=12,
)
chunks = chunker("Your text with multiple sentences. Like this one.")
```

### Recursive (Hierarchical) Chunking
```python
from chonkie import RecursiveChunker

chunker = RecursiveChunker(
    chunk_size=2048,
    min_characters_per_chunk=24,
)
chunks = chunker("Long document with paragraphs, sections, etc.")
```

### Pipeline Approach
```python
from chonkie import Pipeline

pipe = (
    Pipeline()
    .chunk_with("recursive", tokenizer="gpt2", chunk_size=2048)
    .chunk_with("semantic", chunk_size=512)
    .refine_with("overlap", context_size=128)
)

doc = pipe.run(texts="Your text here")
for chunk in doc.chunks:
    print(chunk.text)
```

---

## 4. Chunking Strategies Deep Dive

### Semantic Chunking (Paragraph/Section Aware)
**Supported**: Yes, via `SemanticChunker` and `RecursiveChunker`

`RecursiveChunker` uses hierarchical delimiters (paragraphs, sentences, words) to find natural breaking points. No ML dependencies required.

`SemanticChunker` uses embedding similarity to detect topic boundaries:
- Default model: `minishlab/potion-base-32M`
- Uses Savitzky-Golay filtering to find semantic troughs
- **Requires**: sentence-transformers (pulls in torch)

### Overlap Between Chunks
**Supported**: Yes, built into all chunkers

```python
# Integer overlap (number of tokens)
chunker = TokenChunker(chunk_size=512, chunk_overlap=50)

# Fractional overlap (percentage)
chunker = TokenChunker(chunk_size=512, chunk_overlap=0.1)  # 10% overlap
```

Also available via `OverlapRefinery` in pipelines for post-processing.

### Token-Based Chunking
**Supported**: Yes, primary use case

- `TokenChunker`: Exact token counts with configurable tokenizers
- Supports: character (default, no deps), tiktoken, HuggingFace tokenizers
- Overlap support built-in

### Sentence-Aware Splitting
**Supported**: Yes, via `SentenceChunker`

Configuration:
- `min_sentences_per_chunk`: Minimum sentences per chunk
- `min_characters_per_sentence`: Filter short fragments
- `delim`: Configurable sentence delimiters (`.`, `!`, `?`, `\n`)
- `include_delim`: Where to attach delimiters (`"prev"` or `"next"`)

---

## 5. Dependencies Analysis

### Core (Always Installed)
| Dependency | Version | Purpose |
|------------|---------|---------|
| numpy | >=2.0.0 | Array operations |
| tqdm | >=4.64.0 | Progress bars |

**Assessment**: Acceptable. numpy is ubiquitous, tqdm is tiny.

### Optional by Feature
| Feature | Extra | Heavy Deps |
|---------|-------|------------|
| HF tokenizers | `[tokenizers]` | tokenizers (Rust, fast) |
| tiktoken | `[tiktoken]` | tiktoken (minimal) |
| Semantic | `[semantic]` | sentence-transformers, torch |
| Neural | `[neural]` | transformers, torch |
| Code | `[code]` | tree-sitter |

### Heavy Dependencies to Avoid
- `torch` (2GB+): Only with semantic/neural chunkers
- `transformers` (100MB+): Only with neural chunker
- `sentence-transformers`: Only with semantic/late chunkers

**Key insight**: Base install + `[tokenizers]` gives us token and sentence chunking without torch.

---

## 6. Comparison: Chonkie vs Simple Character-Based

### Our Current Approach
```python
# In parsers.py (~80 lines total)
def chunk_text(text: str, chunk_size: int = 4000) -> list[str]:
    """Simple character-based chunking."""
    return [text[i:i+chunk_size] for i in range(0, len(text), chunk_size)]
```

**Pros:**
- Zero dependencies
- ~5 lines of code
- Predictable, deterministic

**Cons:**
- May split mid-word, mid-sentence
- No token awareness (LLM context limits are in tokens)
- No overlap for context continuity

### Chonkie's Value Add

| Feature | Our Current | Chonkie |
|---------|-------------|---------|
| Token-aware | No | Yes |
| Sentence boundaries | No | Yes |
| Overlap support | No | Yes |
| Paragraph-aware | No | Yes (recursive) |
| Dependencies | 0 | 2 (numpy, tqdm) |
| Lines of code | ~5 | 0 (import) |
| Predictability | High | High |
| Edge case handling | Manual | Built-in |

### Performance Benchmarks (from Chonkie)
- Token chunking: 33x faster than slowest alternative
- Sentence chunking: ~2x faster than competitors
- Wheel size: 505KB vs 1-12MB alternatives

---

## 7. Recommendation

### Option A: Use Chonkie (Minimal)
```bash
pip install chonkie  # Just numpy + tqdm
```

```python
from chonkie import SentenceChunker

# Sentence-aware, token-counted, with overlap
chunker = SentenceChunker(
    tokenizer="character",  # No extra deps
    chunk_size=4000,
    chunk_overlap=200,
)
```

**Pros:**
- Battle-tested edge case handling
- Sentence boundary awareness
- Overlap for context continuity
- Actively maintained (v1.5.2, Jan 2026)

**Cons:**
- Adds numpy + tqdm dependencies
- Requires Python 3.10+ (we may support 3.9)
- Another dependency to track

### Option B: Roll Our Own (Enhanced)
```python
import re

def chunk_by_sentences(text: str, max_chars: int = 4000, overlap_chars: int = 200) -> list[str]:
    """Sentence-aware chunking with overlap."""
    sentences = re.split(r'(?<=[.!?])\s+', text)
    chunks = []
    current = ""

    for sentence in sentences:
        if len(current) + len(sentence) > max_chars and current:
            chunks.append(current.strip())
            # Overlap: keep last N chars
            current = current[-overlap_chars:] if overlap_chars else ""
        current += sentence + " "

    if current.strip():
        chunks.append(current.strip())

    return chunks
```

**Pros:**
- Zero dependencies
- ~20 lines, fully understood
- Works with Python 3.8+

**Cons:**
- No token counting (character approximation)
- Must handle edge cases ourselves
- Not battle-tested

### Option C: Hybrid Approach
Use chonkie as optional enhancement:

```python
try:
    from chonkie import SentenceChunker
    CHUNKER = SentenceChunker(chunk_size=4000, chunk_overlap=200)
    def chunk_text(text: str) -> list[str]:
        return [c.text for c in CHUNKER(text)]
except ImportError:
    def chunk_text(text: str, chunk_size: int = 4000) -> list[str]:
        # Fallback to simple chunking
        return [text[i:i+chunk_size] for i in range(0, len(text), chunk_size)]
```

---

## 8. Final Assessment

| Criteria | Score | Notes |
|----------|-------|-------|
| **Relevance** | High | Exactly solves our chunking needs |
| **Minimal deps** | Good | Only numpy + tqdm in base |
| **API simplicity** | Excellent | One-liner usage |
| **Maintenance** | Active | Regular releases, v1.5.2 Jan 2026 |
| **Philosophy fit** | Partial | Adds deps, but follows "lightweight" principle |

### Decision Matrix

**Use Chonkie if:**
- You need accurate token counting for LLM limits
- Sentence/paragraph awareness is important
- You want overlap between chunks
- Python 3.10+ is acceptable

**Roll your own if:**
- You need Python 3.8/3.9 support
- Character-based approximation is sufficient
- You want absolute minimal dependencies
- Edge cases are well-understood for your data

### For Recursive-Data-Cleaner Specifically

Given our philosophy of "stdlib over dependencies" but also "trade computational efficiency for human time savings", I recommend:

1. **Short term**: Keep current simple chunking
2. **If users report issues**: Add chonkie as optional with fallback
3. **For v0.2**: Consider chonkie[tokenizers] for accurate LLM token limits

The value proposition is real but not critical for our initial use case of chunk-based LLM analysis.

---

## Sources

- [Chonkie GitHub Repository](https://github.com/chonkie-inc/chonkie)
- [Chonkie on PyPI](https://pypi.org/project/chonkie/)
- [Chonkie Documentation](https://docs.chonkie.ai)
- [Meet Chonkie: A Lightweight Text Chunking Library (Medium)](https://medium.com/mlworks/meet-chonkie-a-lightweight-no-nonsense-text-chunking-library-for-llms-88e94d0d257c)
- [Introducing Chonkie (Deeplearning.fr)](https://deeplearning.fr/introducing-chonkie-the-lightweight-rag-chunking-library/)

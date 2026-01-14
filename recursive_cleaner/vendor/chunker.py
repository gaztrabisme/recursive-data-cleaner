"""Minimal sentence-aware text chunker extracted from chonkie.

Sentence chunking algorithm adapted from Chonkie
https://github.com/chonkie-inc/chonkie
Copyright (c) 2025 Chonkie
Licensed under the MIT License

MIT License

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
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
            chunks.append(
                Chunk(
                    text=chunk_text,
                    start_index=positions[pos],
                    end_index=positions[pos] + len(chunk_text),
                    token_count=len(chunk_text),
                )
            )

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

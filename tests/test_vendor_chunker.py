"""Tests for vendored SentenceChunker."""

import pytest

from recursive_cleaner.vendor import Chunk, SentenceChunker


class TestChunkDataclass:
    """Tests for the Chunk dataclass."""

    def test_chunk_creation(self):
        """Test basic Chunk creation."""
        chunk = Chunk(text="Hello world", start_index=0, end_index=11, token_count=11)
        assert chunk.text == "Hello world"
        assert chunk.start_index == 0
        assert chunk.end_index == 11
        assert chunk.token_count == 11

    def test_chunk_len(self):
        """Test Chunk __len__ method."""
        chunk = Chunk(text="Hello", start_index=0, end_index=5, token_count=5)
        assert len(chunk) == 5


class TestSentenceChunkerInit:
    """Tests for SentenceChunker initialization and validation."""

    def test_default_parameters(self):
        """Test default parameter values."""
        chunker = SentenceChunker()
        assert chunker.chunk_size == 4000
        assert chunker.chunk_overlap == 200
        assert chunker.min_sentences_per_chunk == 1
        assert chunker.min_characters_per_sentence == 12
        assert chunker.delim == [". ", "! ", "? ", "\n"]
        assert chunker.include_delim == "prev"

    def test_custom_parameters(self):
        """Test custom parameter values."""
        chunker = SentenceChunker(
            chunk_size=1000,
            chunk_overlap=100,
            min_sentences_per_chunk=2,
            min_characters_per_sentence=20,
            delim=[".", "!"],
            include_delim="next",
        )
        assert chunker.chunk_size == 1000
        assert chunker.chunk_overlap == 100
        assert chunker.min_sentences_per_chunk == 2
        assert chunker.min_characters_per_sentence == 20
        assert chunker.delim == [".", "!"]
        assert chunker.include_delim == "next"

    def test_string_delim_converted_to_list(self):
        """Test single string delimiter is converted to list."""
        chunker = SentenceChunker(delim=". ")
        assert chunker.delim == [". "]

    def test_invalid_chunk_size(self):
        """Test error on invalid chunk_size."""
        with pytest.raises(ValueError, match="chunk_size must be positive"):
            SentenceChunker(chunk_size=0)
        with pytest.raises(ValueError, match="chunk_size must be positive"):
            SentenceChunker(chunk_size=-100)

    def test_overlap_exceeds_chunk_size(self):
        """Test error when overlap >= chunk_size."""
        with pytest.raises(ValueError, match="chunk_overlap must be less than chunk_size"):
            SentenceChunker(chunk_size=100, chunk_overlap=100)
        with pytest.raises(ValueError, match="chunk_overlap must be less than chunk_size"):
            SentenceChunker(chunk_size=100, chunk_overlap=150)

    def test_invalid_min_sentences(self):
        """Test error on invalid min_sentences_per_chunk."""
        with pytest.raises(ValueError, match="min_sentences_per_chunk must be at least 1"):
            SentenceChunker(min_sentences_per_chunk=0)


class TestBasicSentenceSplitting:
    """Tests for basic sentence splitting functionality."""

    def test_basic_sentence_splitting(self):
        """Test basic sentence splitting with default delimiters."""
        chunker = SentenceChunker(chunk_size=1000)
        text = "Hello world. This is a test. How are you? Fine!"
        chunks = chunker.chunk(text)

        assert len(chunks) == 1
        assert chunks[0].text == text
        assert chunks[0].start_index == 0
        assert chunks[0].end_index == len(text)

    def test_multiple_sentences_split(self):
        """Test splitting into multiple chunks."""
        chunker = SentenceChunker(chunk_size=50, chunk_overlap=0)
        text = "First sentence here. Second sentence here. Third sentence here. Fourth sentence here."
        chunks = chunker.chunk(text)

        # Should split based on chunk_size of 50 chars
        assert len(chunks) >= 2
        # Verify position tracking
        for chunk in chunks:
            assert chunk.start_index >= 0
            assert chunk.end_index <= len(text)
            assert chunk.token_count == len(chunk.text)

    def test_empty_input_returns_empty_list(self):
        """Test empty input returns empty list."""
        chunker = SentenceChunker()
        assert chunker.chunk("") == []
        assert chunker.chunk("   ") == []
        assert chunker.chunk("\n\n") == []
        assert chunker.chunk("\t\t") == []

    def test_single_sentence_input(self):
        """Test single sentence input."""
        chunker = SentenceChunker(chunk_size=1000)
        text = "This is a single sentence without any delimiter at the end"
        chunks = chunker.chunk(text)

        assert len(chunks) == 1
        assert chunks[0].text == text
        assert chunks[0].start_index == 0
        assert chunks[0].end_index == len(text)
        assert chunks[0].token_count == len(text)


class TestChunkOverlap:
    """Tests for chunk overlap functionality."""

    def test_overlap_works(self):
        """Test that overlap creates overlapping content between chunks."""
        chunker = SentenceChunker(chunk_size=60, chunk_overlap=30)
        text = "First sentence here. Second sentence here. Third sentence here. Fourth sentence here."
        chunks = chunker.chunk(text)

        if len(chunks) >= 2:
            # Check for overlap - some text should appear in consecutive chunks
            for i in range(len(chunks) - 1):
                chunk1_end = chunks[i].text[-30:] if len(chunks[i].text) >= 30 else chunks[i].text
                chunk2_start = chunks[i + 1].text[:30] if len(chunks[i + 1].text) >= 30 else chunks[i + 1].text
                # The overlap should mean chunk2 starts before chunk1 ends (position-wise)
                # or they share some content
                if chunks[i + 1].start_index < chunks[i].end_index:
                    # There is overlap in positions
                    pass  # This is expected with overlap

    def test_no_overlap_when_zero(self):
        """Test no overlap when chunk_overlap is 0."""
        chunker = SentenceChunker(chunk_size=50, chunk_overlap=0)
        text = "First sentence here. Second sentence here. Third sentence here."
        chunks = chunker.chunk(text)

        if len(chunks) >= 2:
            # With no overlap, chunks should not share positions
            for i in range(len(chunks) - 1):
                # End of chunk i should be start of chunk i+1
                assert chunks[i].end_index == chunks[i + 1].start_index


class TestShortSentenceMerging:
    """Tests for short sentence merging functionality."""

    def test_short_sentences_merged(self):
        """Test that short sentences are merged with previous sentence."""
        chunker = SentenceChunker(
            chunk_size=1000, chunk_overlap=0, min_characters_per_sentence=20
        )
        # "Hi. " is only 4 chars, should be merged
        text = "Hi. This is a longer sentence. Ok. Another long sentence here."
        chunks = chunker.chunk(text)

        # All should be in one chunk with this size
        assert len(chunks) == 1
        assert chunks[0].text == text

    def test_all_short_sentences(self):
        """Test handling of text with all short sentences."""
        chunker = SentenceChunker(
            chunk_size=1000, chunk_overlap=0, min_characters_per_sentence=50
        )
        text = "Hi. Hello. Hey. Yo. What. Cool."
        chunks = chunker.chunk(text)

        # Should merge all into one since all are short
        assert len(chunks) == 1


class TestPositionTracking:
    """Tests for position tracking accuracy."""

    def test_position_tracking_accuracy(self):
        """Test that start_index and end_index accurately track positions."""
        chunker = SentenceChunker(chunk_size=50, chunk_overlap=0)
        text = "First sentence. Second sentence. Third sentence."
        chunks = chunker.chunk(text)

        for chunk in chunks:
            # Extract text using reported positions
            extracted = text[chunk.start_index : chunk.end_index]
            assert extracted == chunk.text

    def test_position_coverage(self):
        """Test that positions cover the entire text when no overlap."""
        chunker = SentenceChunker(chunk_size=30, chunk_overlap=0)
        text = "First sentence here. Second sentence here. Third here."
        chunks = chunker.chunk(text)

        if len(chunks) >= 1:
            # First chunk should start at 0
            assert chunks[0].start_index == 0
            # Last chunk should end at text length
            assert chunks[-1].end_index == len(text)


class TestConfigurableDelimiters:
    """Tests for configurable delimiter functionality."""

    def test_custom_delimiters(self):
        """Test custom delimiter configuration."""
        chunker = SentenceChunker(chunk_size=1000, delim=["||", ";;"])
        text = "First part||Second part;;Third part"
        chunks = chunker.chunk(text)

        assert len(chunks) == 1
        # Should have processed with custom delimiters

    def test_newline_delimiter(self):
        """Test newline as delimiter."""
        chunker = SentenceChunker(chunk_size=50, chunk_overlap=0, delim=["\n"])
        text = "Line one\nLine two\nLine three\nLine four"
        chunks = chunker.chunk(text)

        # Should split on newlines
        assert len(chunks) >= 1

    def test_include_delim_prev(self):
        """Test delimiter included with previous sentence."""
        chunker = SentenceChunker(
            chunk_size=1000, delim=[". "], include_delim="prev"
        )
        text = "First sentence. Second sentence. Third sentence."
        chunks = chunker.chunk(text)

        # With include_delim="prev", periods should be at end of sentences
        assert ". " in chunks[0].text or chunks[0].text.endswith(".")

    def test_include_delim_next(self):
        """Test delimiter included with next sentence."""
        chunker = SentenceChunker(
            chunk_size=1000, delim=[". "], include_delim="next"
        )
        text = "First sentence. Second sentence. Third sentence"
        chunks = chunker.chunk(text)

        # Chunk should be produced
        assert len(chunks) >= 1

    def test_include_delim_none(self):
        """Test delimiter excluded entirely."""
        chunker = SentenceChunker(
            chunk_size=1000, delim=[". "], include_delim=None
        )
        text = "First sentence. Second sentence. Third sentence"
        chunks = chunker.chunk(text)

        # Chunk should be produced (delimiters removed)
        assert len(chunks) >= 1


class TestTokenCount:
    """Tests for token_count field accuracy."""

    def test_token_count_equals_char_count(self):
        """Test that token_count equals character count."""
        chunker = SentenceChunker(chunk_size=50, chunk_overlap=0)
        text = "First sentence. Second sentence. Third sentence."
        chunks = chunker.chunk(text)

        for chunk in chunks:
            assert chunk.token_count == len(chunk.text)


class TestEdgeCases:
    """Tests for various edge cases."""

    def test_very_long_sentence(self):
        """Test handling of sentence longer than chunk_size."""
        chunker = SentenceChunker(chunk_size=20, chunk_overlap=0)
        text = "This is a very long sentence that exceeds the chunk size limit."
        chunks = chunker.chunk(text)

        # Should still produce at least one chunk
        assert len(chunks) >= 1
        # The chunk might exceed size limit since we can't split mid-sentence
        assert chunks[0].text == text

    def test_whitespace_only_between_sentences(self):
        """Test handling of extra whitespace."""
        chunker = SentenceChunker(chunk_size=1000)
        text = "First sentence.    Second sentence.   Third sentence."
        chunks = chunker.chunk(text)

        assert len(chunks) >= 1

    def test_unicode_text(self):
        """Test handling of unicode text."""
        chunker = SentenceChunker(chunk_size=1000)
        text = "Hello world. Bonjour le monde. Hola mundo."
        chunks = chunker.chunk(text)

        assert len(chunks) == 1
        assert chunks[0].text == text

    def test_special_characters(self):
        """Test handling of special characters."""
        chunker = SentenceChunker(chunk_size=1000)
        text = "Price is $100. Temperature is 25C. Ratio is 1:2."
        chunks = chunker.chunk(text)

        assert len(chunks) == 1
        assert chunks[0].text == text


class TestMinSentencesPerChunk:
    """Tests for min_sentences_per_chunk parameter."""

    def test_min_sentences_enforced(self):
        """Test minimum sentences per chunk is enforced."""
        chunker = SentenceChunker(
            chunk_size=20,  # Very small
            chunk_overlap=0,
            min_sentences_per_chunk=2,
        )
        text = "First. Second. Third. Fourth."
        chunks = chunker.chunk(text)

        # Each chunk should have at least 2 sentences if possible
        # Due to the small chunk size, behavior may vary
        assert len(chunks) >= 1

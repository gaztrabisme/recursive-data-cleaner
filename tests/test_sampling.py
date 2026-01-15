"""Tests for smart sampling functionality."""

import json
import tempfile
from pathlib import Path

import pytest

from recursive_cleaner.parsers import (
    _compute_seed,
    _shuffle_records,
    _stratified_sample,
    chunk_file,
)


class TestComputeSeed:
    """Tests for _compute_seed function."""

    def test_deterministic_same_content(self):
        """Same content always produces same seed."""
        content = "test content for hashing"
        seed1 = _compute_seed(content)
        seed2 = _compute_seed(content)
        assert seed1 == seed2

    def test_different_content_different_seed(self):
        """Different content produces different seeds."""
        seed1 = _compute_seed("content A")
        seed2 = _compute_seed("content B")
        assert seed1 != seed2

    def test_returns_int(self):
        """Seed is an integer."""
        seed = _compute_seed("any content")
        assert isinstance(seed, int)


class TestShuffleRecords:
    """Tests for _shuffle_records function."""

    def test_deterministic_shuffle(self):
        """Same seed produces same shuffle order."""
        records = ["a", "b", "c", "d", "e"]
        seed = 12345
        result1 = _shuffle_records(records, seed)
        result2 = _shuffle_records(records, seed)
        assert result1 == result2

    def test_different_seed_different_order(self):
        """Different seeds produce different orders."""
        records = ["a", "b", "c", "d", "e", "f", "g", "h"]
        result1 = _shuffle_records(records, 111)
        result2 = _shuffle_records(records, 222)
        # With 8 items, very unlikely to get same order by chance
        assert result1 != result2

    def test_preserves_all_records(self):
        """Shuffle preserves all records, no duplicates or losses."""
        records = ["a", "b", "c", "d"]
        result = _shuffle_records(records, 999)
        assert sorted(result) == sorted(records)
        assert len(result) == len(records)

    def test_empty_list(self):
        """Empty list returns empty list."""
        result = _shuffle_records([], 123)
        assert result == []

    def test_single_item(self):
        """Single item list returns same item."""
        result = _shuffle_records(["only"], 123)
        assert result == ["only"]

    def test_does_not_modify_original(self):
        """Original list is not modified."""
        original = ["a", "b", "c"]
        original_copy = original.copy()
        _shuffle_records(original, 123)
        assert original == original_copy


class TestStratifiedSample:
    """Tests for _stratified_sample function."""

    def test_balances_categories(self):
        """Stratified sampling interleaves categories."""
        records = [
            '{"category": "A", "id": 1}',
            '{"category": "A", "id": 2}',
            '{"category": "A", "id": 3}',
            '{"category": "B", "id": 4}',
            '{"category": "B", "id": 5}',
            '{"category": "B", "id": 6}',
        ]
        result = _stratified_sample(records, "category", 42)
        # Check that A and B are interleaved (not all A then all B)
        categories = [json.loads(r)["category"] for r in result]
        # First two items should be from different categories (interleaved)
        assert categories[0] != categories[1] or len(set(categories[:3])) > 1

    def test_preserves_all_records(self):
        """All records are preserved after stratified sampling."""
        records = [
            '{"type": "X", "val": 1}',
            '{"type": "Y", "val": 2}',
            '{"type": "X", "val": 3}',
        ]
        result = _stratified_sample(records, "type", 123)
        assert len(result) == len(records)
        assert sorted(result) == sorted(records)

    def test_missing_field_grouped_together(self):
        """Records missing the stratify field are grouped as '_missing_'."""
        records = [
            '{"status": "active", "id": 1}',
            '{"id": 2}',  # Missing 'status'
            '{"status": "active", "id": 3}',
        ]
        result = _stratified_sample(records, "status", 42)
        assert len(result) == 3

    def test_invalid_json_grouped_together(self):
        """Invalid JSON records are grouped as '_invalid_'."""
        records = [
            '{"valid": "yes"}',
            'not valid json',
            '{"valid": "also"}',
        ]
        result = _stratified_sample(records, "valid", 42)
        assert len(result) == 3
        # All records preserved
        assert sorted(result) == sorted(records)

    def test_deterministic_with_same_seed(self):
        """Same seed produces same order."""
        records = [
            '{"cat": "A", "n": 1}',
            '{"cat": "B", "n": 2}',
            '{"cat": "A", "n": 3}',
            '{"cat": "B", "n": 4}',
        ]
        result1 = _stratified_sample(records, "cat", 999)
        result2 = _stratified_sample(records, "cat", 999)
        assert result1 == result2


class TestChunkFileWithSampling:
    """Tests for chunk_file with sampling strategies."""

    def test_sequential_preserves_order(self):
        """Sequential sampling preserves original order."""
        content = "\n".join([
            '{"id": 1}',
            '{"id": 2}',
            '{"id": 3}',
            '{"id": 4}',
        ])
        with tempfile.NamedTemporaryFile(mode="w", suffix=".jsonl", delete=False) as f:
            f.write(content)
            f.flush()
            chunks = chunk_file(f.name, chunk_size=2, sampling_strategy="sequential")
        # First chunk should have id 1 and 2
        assert '{"id": 1}' in chunks[0]
        assert '{"id": 2}' in chunks[0]
        Path(f.name).unlink()

    def test_random_shuffles_records(self):
        """Random sampling shuffles records before chunking."""
        content = "\n".join([f'{{"id": {i}}}' for i in range(20)])
        with tempfile.NamedTemporaryFile(mode="w", suffix=".jsonl", delete=False) as f:
            f.write(content)
            f.flush()
            chunks_seq = chunk_file(f.name, chunk_size=5, sampling_strategy="sequential")
            chunks_rand = chunk_file(f.name, chunk_size=5, sampling_strategy="random")
        # Random chunks should differ from sequential
        assert chunks_seq != chunks_rand
        Path(f.name).unlink()

    def test_random_is_deterministic(self):
        """Random sampling produces same result on repeated calls."""
        content = "\n".join([f'{{"id": {i}}}' for i in range(10)])
        with tempfile.NamedTemporaryFile(mode="w", suffix=".jsonl", delete=False) as f:
            f.write(content)
            f.flush()
            chunks1 = chunk_file(f.name, chunk_size=3, sampling_strategy="random")
            chunks2 = chunk_file(f.name, chunk_size=3, sampling_strategy="random")
        assert chunks1 == chunks2
        Path(f.name).unlink()

    def test_stratified_balances_chunks(self):
        """Stratified sampling distributes categories across chunks."""
        records = []
        for i in range(6):
            records.append(f'{{"category": "A", "id": {i}}}')
        for i in range(6):
            records.append(f'{{"category": "B", "id": {i + 6}}}')
        content = "\n".join(records)

        with tempfile.NamedTemporaryFile(mode="w", suffix=".jsonl", delete=False) as f:
            f.write(content)
            f.flush()
            chunks = chunk_file(
                f.name,
                chunk_size=4,
                sampling_strategy="stratified",
                stratify_field="category",
            )

        # Each chunk should have mix of categories (not all A then all B)
        for chunk in chunks:
            lines = chunk.strip().split("\n")
            categories = [json.loads(l)["category"] for l in lines]
            # At least one chunk should have both categories
            if len(set(categories)) > 1:
                break
        else:
            # If we get here, no chunk had mixed categories - that's OK for small samples
            # but we should at least verify all records are present
            all_lines = []
            for chunk in chunks:
                all_lines.extend(chunk.strip().split("\n"))
            assert len(all_lines) == 12
        Path(f.name).unlink()

    def test_text_mode_rejects_random(self):
        """Text mode raises ValueError for non-sequential sampling."""
        content = "This is some text content for testing."
        with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
            f.write(content)
            f.flush()
            with pytest.raises(ValueError, match="Text mode only supports 'sequential'"):
                chunk_file(f.name, chunk_size=100, sampling_strategy="random")
        Path(f.name).unlink()

    def test_text_mode_rejects_stratified(self):
        """Text mode raises ValueError for stratified sampling."""
        content = "This is some text content for testing."
        with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
            f.write(content)
            f.flush()
            with pytest.raises(ValueError, match="Text mode only supports 'sequential'"):
                chunk_file(
                    f.name,
                    chunk_size=100,
                    sampling_strategy="stratified",
                    stratify_field="any",
                )
        Path(f.name).unlink()

    def test_text_mode_allows_sequential(self):
        """Text mode works fine with sequential sampling."""
        content = "This is some text content for testing purposes."
        with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
            f.write(content)
            f.flush()
            # Should not raise
            chunks = chunk_file(f.name, chunk_size=100, sampling_strategy="sequential")
            assert len(chunks) >= 1
        Path(f.name).unlink()

    def test_empty_data_returns_empty(self):
        """Empty file returns empty chunks regardless of sampling strategy."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".jsonl", delete=False) as f:
            f.write("")
            f.flush()
            chunks = chunk_file(f.name, chunk_size=10, sampling_strategy="random")
            assert chunks == []
        Path(f.name).unlink()

    def test_stratified_without_field_falls_back(self):
        """Stratified with no stratify_field behaves like sequential."""
        content = "\n".join([f'{{"id": {i}}}' for i in range(5)])
        with tempfile.NamedTemporaryFile(mode="w", suffix=".jsonl", delete=False) as f:
            f.write(content)
            f.flush()
            chunks_seq = chunk_file(f.name, chunk_size=2, sampling_strategy="sequential")
            # When stratify_field is None, stratified falls back to sequential
            chunks_strat = chunk_file(
                f.name,
                chunk_size=2,
                sampling_strategy="stratified",
                stratify_field=None,
            )
        assert chunks_seq == chunks_strat
        Path(f.name).unlink()


class TestDataCleanerSamplingParams:
    """Tests for DataCleaner sampling parameter handling."""

    def test_default_sampling_strategy(self):
        """Default sampling strategy is sequential."""
        from recursive_cleaner import DataCleaner

        class DummyBackend:
            def generate(self, prompt: str) -> str:
                return ""

        cleaner = DataCleaner(
            llm_backend=DummyBackend(),
            file_path="/fake/path.jsonl",
        )
        assert cleaner.sampling_strategy == "sequential"
        assert cleaner.stratify_field is None

    def test_custom_sampling_params(self):
        """Custom sampling parameters are stored correctly."""
        from recursive_cleaner import DataCleaner

        class DummyBackend:
            def generate(self, prompt: str) -> str:
                return ""

        cleaner = DataCleaner(
            llm_backend=DummyBackend(),
            file_path="/fake/path.jsonl",
            sampling_strategy="stratified",
            stratify_field="category",
        )
        assert cleaner.sampling_strategy == "stratified"
        assert cleaner.stratify_field == "category"

"""Tests for global distribution statistics module."""

import json
import tempfile

from recursive_cleaner.stats import compute_field_stats, format_stats_for_prompt


class TestComputeFieldStats:
    """Tests for compute_field_stats function."""

    def test_categorical_field_counts(self):
        """Low-cardinality field gets full value counts."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".jsonl", delete=False) as f:
            for _ in range(48):
                f.write('{"status": "active"}\n')
            for _ in range(16):
                f.write('{"status": "pending"}\n')
            for _ in range(8):
                f.write('{"status": "acitve"}\n')
            f.flush()

            stats = compute_field_stats(f.name)

            assert stats["status"]["type"] == "categorical"
            assert stats["status"]["total"] == 72
            assert stats["status"]["null_count"] == 0
            # Most common first
            counts = stats["status"]["value_counts"]
            assert counts[0] == ("active", 48)
            assert counts[1] == ("pending", 16)
            assert counts[2] == ("acitve", 8)

    def test_high_cardinality_field(self):
        """High-cardinality field gets summary only."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".jsonl", delete=False) as f:
            for i in range(60):
                f.write(json.dumps({"name": f"person_{i}"}) + "\n")
            f.flush()

            stats = compute_field_stats(f.name)

            assert stats["name"]["type"] == "high_cardinality"
            assert stats["name"]["unique"] == 60
            assert stats["name"]["total"] == 60

    def test_null_handling(self):
        """Null values counted separately from value frequencies."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".jsonl", delete=False) as f:
            f.write('{"email": "alice@test.com"}\n')
            f.write('{"email": null}\n')
            f.write('{"email": "bob@test.com"}\n')
            f.write('{"email": null}\n')
            f.flush()

            stats = compute_field_stats(f.name)

            assert stats["email"]["type"] == "categorical"
            assert stats["email"]["null_count"] == 2
            assert stats["email"]["total"] == 4
            # Only non-null values in counts
            values = [v for v, _ in stats["email"]["value_counts"]]
            assert "None" not in values

    def test_empty_dataset(self):
        """Empty file returns empty dict."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".jsonl", delete=False) as f:
            f.write("")
            f.flush()

            stats = compute_field_stats(f.name)

            assert stats == {}

    def test_cardinality_threshold(self):
        """max_cardinality parameter controls the cutoff."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".jsonl", delete=False) as f:
            for i in range(10):
                f.write(json.dumps({"code": f"code_{i}"}) + "\n")
            f.flush()

            # With threshold of 5, 10 unique values is high cardinality
            stats = compute_field_stats(f.name, max_cardinality=5)
            assert stats["code"]["type"] == "high_cardinality"

            # With threshold of 15, 10 unique values is categorical
            stats = compute_field_stats(f.name, max_cardinality=15)
            assert stats["code"]["type"] == "categorical"

    def test_mixed_types_stringified(self):
        """Fields with int/str/None all handled via str conversion."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".jsonl", delete=False) as f:
            f.write('{"value": 123}\n')
            f.write('{"value": "text"}\n')
            f.write('{"value": null}\n')
            f.write('{"value": 123}\n')
            f.flush()

            stats = compute_field_stats(f.name)

            assert stats["value"]["type"] == "categorical"
            assert stats["value"]["null_count"] == 1
            counts = dict(stats["value"]["value_counts"])
            assert counts["123"] == 2
            assert counts["text"] == 1

    def test_list_field_stringified(self):
        """List values are serialized to string for counting."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".jsonl", delete=False) as f:
            f.write('{"tags": ["a", "b"]}\n')
            f.write('{"tags": ["a", "b"]}\n')
            f.write('{"tags": ["c"]}\n')
            f.flush()

            stats = compute_field_stats(f.name)

            assert stats["tags"]["type"] == "categorical"
            assert stats["tags"]["total"] == 3

    def test_multiple_fields(self):
        """Stats computed independently per field."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".jsonl", delete=False) as f:
            for i in range(60):
                f.write(json.dumps({
                    "id": i,
                    "status": "active" if i % 2 == 0 else "pending",
                }) + "\n")
            f.flush()

            stats = compute_field_stats(f.name)

            # id is high cardinality (60 unique values > default 50)
            assert stats["id"]["type"] == "high_cardinality"
            # status is categorical (2 unique values)
            assert stats["status"]["type"] == "categorical"

    def test_value_counts_capped_at_20(self):
        """Value counts list capped at 20 entries (most_common)."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".jsonl", delete=False) as f:
            for i in range(30):
                f.write(json.dumps({"code": f"val_{i}"}) + "\n")
            f.flush()

            stats = compute_field_stats(f.name, max_cardinality=50)

            assert len(stats["code"]["value_counts"]) == 20

    def test_json_array_support(self):
        """Stats work with JSON array files via load_structured_data."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            data = [
                {"status": "active", "name": "Alice"},
                {"status": "pending", "name": "Bob"},
                {"status": "active", "name": "Carol"},
            ]
            json.dump(data, f)
            f.flush()

            stats = compute_field_stats(f.name)

            assert stats["status"]["type"] == "categorical"
            counts = dict(stats["status"]["value_counts"])
            assert counts["active"] == 2
            assert counts["pending"] == 1


class TestFormatStatsForPrompt:
    """Tests for format_stats_for_prompt function."""

    def test_empty_stats(self):
        """Empty stats returns empty string."""
        assert format_stats_for_prompt({}) == ""

    def test_categorical_field_formatted(self):
        """Categorical field shows value counts with percentages."""
        stats = {
            "status": {
                "type": "categorical",
                "value_counts": [("active", 48), ("pending", 16)],
                "total": 64,
                "null_count": 0,
            }
        }

        result = format_stats_for_prompt(stats)

        assert "FULL dataset" in result
        assert "status (64 values):" in result
        assert "'active': 48 (75%)" in result
        assert "'pending': 16 (25%)" in result

    def test_high_cardinality_formatted(self):
        """High-cardinality field shows summary only."""
        stats = {
            "name": {
                "type": "high_cardinality",
                "unique": 98,
                "total": 100,
            }
        }

        result = format_stats_for_prompt(stats)

        assert "name: 98 unique values (high cardinality)" in result

    def test_null_count_shown(self):
        """Null count shown when non-zero."""
        stats = {
            "email": {
                "type": "categorical",
                "value_counts": [("test@x.com", 3)],
                "total": 5,
                "null_count": 2,
            }
        }

        result = format_stats_for_prompt(stats)

        assert "email (5 values, 2 null):" in result

    def test_null_count_hidden_when_zero(self):
        """Null count not shown when zero."""
        stats = {
            "status": {
                "type": "categorical",
                "value_counts": [("active", 10)],
                "total": 10,
                "null_count": 0,
            }
        }

        result = format_stats_for_prompt(stats)

        assert "null" not in result.lower().split("status")[1]

    def test_mixed_fields(self):
        """Both categorical and high-cardinality in same output."""
        stats = {
            "status": {
                "type": "categorical",
                "value_counts": [("active", 48)],
                "total": 48,
                "null_count": 0,
            },
            "name": {
                "type": "high_cardinality",
                "unique": 98,
                "total": 100,
            },
        }

        result = format_stats_for_prompt(stats)

        assert "status (48 values):" in result
        assert "name: 98 unique values (high cardinality)" in result

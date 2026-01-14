"""Tests for schema inference module."""

import json
import tempfile

import pytest

from recursive_cleaner.schema import format_schema_for_prompt, infer_schema


class TestInferSchemaJsonl:
    """Tests for JSONL schema inference."""

    def test_infer_jsonl_basic(self):
        """Test basic JSONL schema inference."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".jsonl", delete=False) as f:
            f.write('{"name": "Alice", "age": 30, "active": true}\n')
            f.write('{"name": "Bob", "age": 25, "active": false}\n')
            f.flush()

            schema = infer_schema(f.name)

            assert schema["fields"] == ["name", "age", "active"]
            assert schema["types"]["name"] == "str"
            assert schema["types"]["age"] == "int"
            assert schema["types"]["active"] == "bool"
            assert schema["nullable"]["name"] is False

    def test_infer_jsonl_nullable_fields(self):
        """Test nullable field detection in JSONL."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".jsonl", delete=False) as f:
            f.write('{"name": "Alice", "email": "alice@test.com"}\n')
            f.write('{"name": "Bob", "email": null}\n')
            f.flush()

            schema = infer_schema(f.name)

            assert schema["nullable"]["name"] is False
            assert schema["nullable"]["email"] is True

    def test_infer_jsonl_samples(self):
        """Test sample collection (max 3 per field)."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".jsonl", delete=False) as f:
            for i in range(10):
                f.write(json.dumps({"id": i, "name": f"item_{i}"}) + "\n")
            f.flush()

            schema = infer_schema(f.name)

            assert len(schema["samples"]["id"]) == 3
            assert schema["samples"]["id"] == [0, 1, 2]

    def test_infer_jsonl_mixed_types(self):
        """Test mixed type detection."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".jsonl", delete=False) as f:
            f.write('{"value": 123}\n')
            f.write('{"value": "text"}\n')
            f.flush()

            schema = infer_schema(f.name)

            assert schema["types"]["value"] == "mixed"

    def test_infer_jsonl_nested_types(self):
        """Test detection of list and dict types."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".jsonl", delete=False) as f:
            f.write('{"tags": ["a", "b"], "meta": {"key": "val"}}\n')
            f.flush()

            schema = infer_schema(f.name)

            assert schema["types"]["tags"] == "list"
            assert schema["types"]["meta"] == "dict"


class TestInferSchemaCsv:
    """Tests for CSV schema inference."""

    def test_infer_csv_basic(self):
        """Test basic CSV schema inference."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False) as f:
            f.write("name,age,score\n")
            f.write("Alice,30,95.5\n")
            f.write("Bob,25,88.0\n")
            f.flush()

            schema = infer_schema(f.name)

            assert schema["fields"] == ["name", "age", "score"]
            # CSV values are strings
            assert schema["types"]["name"] == "str"
            assert schema["types"]["age"] == "str"

    def test_infer_csv_headers_as_fields(self):
        """Test that CSV headers become field names."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False) as f:
            f.write("product_id,product_name,price\n")
            f.write("P001,Widget,19.99\n")
            f.flush()

            schema = infer_schema(f.name)

            assert "product_id" in schema["fields"]
            assert "product_name" in schema["fields"]
            assert "price" in schema["fields"]


class TestInferSchemaJson:
    """Tests for JSON array schema inference."""

    def test_infer_json_array(self):
        """Test JSON array schema inference."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            data = [
                {"id": 1, "name": "First"},
                {"id": 2, "name": "Second"},
            ]
            json.dump(data, f)
            f.flush()

            schema = infer_schema(f.name)

            assert schema["fields"] == ["id", "name"]
            assert schema["types"]["id"] == "int"
            assert schema["types"]["name"] == "str"

    def test_infer_json_object(self):
        """Test JSON object schema inference."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            data = {"config": "value", "count": 42}
            json.dump(data, f)
            f.flush()

            schema = infer_schema(f.name)

            assert "config" in schema["fields"]
            assert "count" in schema["fields"]
            assert schema["types"]["config"] == "str"
            assert schema["types"]["count"] == "int"

    def test_infer_json_empty_array(self):
        """Test empty JSON array returns empty schema."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump([], f)
            f.flush()

            schema = infer_schema(f.name)

            assert schema["fields"] == []


class TestInferSchemaText:
    """Tests for text file schema inference."""

    def test_infer_text_returns_empty(self):
        """Test text file returns empty schema."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
            f.write("This is just plain text.\n")
            f.write("No structured data here.\n")
            f.flush()

            schema = infer_schema(f.name)

            assert schema["fields"] == []
            assert schema["types"] == {}
            assert schema["samples"] == {}
            assert schema["nullable"] == {}

    def test_infer_unknown_extension_returns_empty(self):
        """Test unknown file extension returns empty schema."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".xyz", delete=False) as f:
            f.write("Some content")
            f.flush()

            schema = infer_schema(f.name)

            assert schema["fields"] == []


class TestInferSchemaEdgeCases:
    """Edge case tests for schema inference."""

    def test_infer_nonexistent_file(self):
        """Test nonexistent file returns empty schema."""
        schema = infer_schema("/nonexistent/path/file.jsonl")

        assert schema["fields"] == []

    def test_infer_empty_file(self):
        """Test empty file returns empty schema."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".jsonl", delete=False) as f:
            f.write("")
            f.flush()

            schema = infer_schema(f.name)

            assert schema["fields"] == []

    def test_sample_size_limits_records(self):
        """Test sample_size parameter limits records examined."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".jsonl", delete=False) as f:
            for i in range(100):
                f.write(json.dumps({"id": i}) + "\n")
            f.flush()

            schema = infer_schema(f.name, sample_size=5)

            # Should only see first 5 records
            assert len(schema["samples"]["id"]) == 3  # max 3 samples


class TestFormatSchemaForPrompt:
    """Tests for format_schema_for_prompt function."""

    def test_format_basic_schema(self):
        """Test formatting a basic schema."""
        schema = {
            "fields": ["name", "age"],
            "types": {"name": "str", "age": "int"},
            "samples": {"name": ["Alice", "Bob"], "age": [30, 25]},
            "nullable": {"name": False, "age": False},
        }

        result = format_schema_for_prompt(schema)

        assert "Fields detected:" in result
        assert "- name (str):" in result
        assert "- age (int):" in result
        assert "'Alice'" in result
        assert "30" in result

    def test_format_nullable_field(self):
        """Test formatting nullable fields."""
        schema = {
            "fields": ["email"],
            "types": {"email": "str"},
            "samples": {"email": ["test@example.com"]},
            "nullable": {"email": True},
        }

        result = format_schema_for_prompt(schema)

        assert "nullable" in result
        assert "- email (str, nullable):" in result

    def test_format_empty_schema(self):
        """Test formatting empty schema returns empty string."""
        schema = {"fields": [], "types": {}, "samples": {}, "nullable": {}}

        result = format_schema_for_prompt(schema)

        assert result == ""

    def test_format_includes_sample_values(self):
        """Test that sample values are included in output."""
        schema = {
            "fields": ["status"],
            "types": {"status": "str"},
            "samples": {"status": ["active", "pending", "closed"]},
            "nullable": {"status": False},
        }

        result = format_schema_for_prompt(schema)

        assert "'active'" in result
        assert "'pending'" in result
        assert "'closed'" in result

#!/usr/bin/env python3
"""Test script for MLX backend with Recursive Data Cleaner."""

from backends import MLXBackend
from recursive_cleaner import DataCleaner

# Create a small test file
TEST_DATA = '''{"name": "john doe", "phone": "555-1234", "email": "JOHN@EXAMPLE.COM"}
{"name": "Jane Smith", "phone": "(555) 555-5678", "email": "jane@example.com"}
{"name": "bob wilson", "phone": "5559999", "email": "BOB@TEST.ORG"}
'''

def main():
    # Write test data
    with open("test_data.jsonl", "w") as f:
        f.write(TEST_DATA)

    print("Initializing MLX backend...")
    backend = MLXBackend(
        model_path="lmstudio-community/Qwen3-Next-80B-A3B-Instruct-MLX-4bit",
        max_tokens=4096,
        temperature=0.7,
        verbose=True,
    )

    print("\nCreating DataCleaner...")
    cleaner = DataCleaner(
        llm_backend=backend,
        file_path="test_data.jsonl",
        chunk_size=10,
        instructions="""
        Clean this CRM data:
        - Normalize names to Title Case
        - Format phone numbers consistently as (XXX) XXX-XXXX
        - Lowercase all email addresses
        """,
        max_iterations=3,
    )

    print("\nRunning cleaner...")
    cleaner.run()

    print("\n" + "="*50)
    print("Generated functions:")
    for f in cleaner.functions:
        print(f"  - {f['name']}: {f['docstring'][:50]}...")

    print("\nCheck cleaning_functions.py for the generated code!")

if __name__ == "__main__":
    main()

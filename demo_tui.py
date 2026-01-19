#!/usr/bin/env python3
"""
Demo script to showcase the Rich TUI with real MLX backend.

Run with:
    python demo_tui.py

Requirements:
    pip install recursive-cleaner[mlx,tui]
"""

from backends import MLXBackend
from recursive_cleaner import DataCleaner

# Use a smaller/faster model for demo (change to your preferred model)
MODEL = "lmstudio-community/Qwen3-Next-80B-A3B-Instruct-MLX-4bit"

print("=" * 60)
print("  RECURSIVE DATA CLEANER - TUI DEMO")
print("=" * 60)
print(f"\nLoading model: {MODEL}")
print("This may take a moment on first run...\n")

llm = MLXBackend(
    model_path=MODEL,
    max_tokens=2048,
    temperature=0.3,  # Lower for more consistent output
    verbose=False,  # Disable token streaming to avoid interfering with TUI
)

cleaner = DataCleaner(
    llm_backend=llm,
    file_path="test_cases/ecommerce_products.jsonl",
    chunk_size=5,  # Small chunks for demo
    max_iterations=3,  # Limit iterations per chunk
    instructions="""
    E-commerce product data cleaning:
    - Normalize prices to float (remove $ symbols)
    - Fix category typos and normalize to Title Case
    - Convert weights to kg as float
    - Ensure stock_quantity is non-negative integer
    """,
    tui=True,  # Enable the Rich dashboard!
    track_metrics=True,
)

print("\nStarting cleaner with TUI enabled...")
print("Watch the dashboard below!\n")

cleaner.run()

print("\n" + "=" * 60)
print("Demo complete! Check cleaning_functions.py for output.")
print("=" * 60)

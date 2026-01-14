#!/usr/bin/env python3
import os
import sys
sys.path.insert(0, '/Users/GaryT/Documents/Work/AI/Recursive-Data-Cleaner')
os.chdir('/Users/GaryT/Documents/Work/AI/Recursive-Data-Cleaner/test_cases')

from backends import MLXBackend
from recursive_cleaner import DataCleaner

INSTRUCTIONS = """
E-commerce Product Catalog Cleaning Instructions:

- Normalize all prices to float format (no currency symbols)
- Convert all dates to ISO 8601 format (YYYY-MM-DD)
- Fix category spelling and normalize to Title Case
- Standardize SKU format to uppercase with "SKU-" prefix
- Convert all weights to kilograms as float
- Ensure stock_quantity is a non-negative integer
- Strip HTML tags from descriptions, decode HTML entities
- Normalize brand names to Title Case
- Trim whitespace and fix double spaces
- Convert tags to arrays, remove duplicates, lowercase all
"""

backend = MLXBackend(
    model_path="lmstudio-community/Qwen3-Next-80B-A3B-Instruct-MLX-4bit",
    max_tokens=4096,
    temperature=0.7,
    verbose=True,
)

cleaner = DataCleaner(
    llm_backend=backend,
    file_path="ecommerce_products.jsonl",
    chunk_size=20,
    instructions=INSTRUCTIONS,
    max_iterations=5,
)

cleaner.run()

# Rename output
if os.path.exists("cleaning_functions.py"):
    os.rename("cleaning_functions.py", "ecommerce_cleaning_functions.py")
    print("\n=== OUTPUT SAVED TO ecommerce_cleaning_functions.py ===")

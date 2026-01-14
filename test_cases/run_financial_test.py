#!/usr/bin/env python3
import os
import sys
sys.path.insert(0, '/Users/GaryT/Documents/Work/AI/Recursive-Data-Cleaner')
os.chdir('/Users/GaryT/Documents/Work/AI/Recursive-Data-Cleaner/test_cases')

from backends import MLXBackend
from recursive_cleaner import DataCleaner

INSTRUCTIONS = """
Financial Transaction Records Cleaning Instructions:

- Normalize amounts to float (remove currency symbols, commas)
- Convert all dates to ISO 8601 format (YYYY-MM-DD)
- Standardize time to 24-hour format (HH:MM:SS)
- Normalize currency codes to 3-letter uppercase (USD, EUR, GBP)
- Standardize transaction_type to uppercase (DEBIT, CREDIT, TRANSFER)
- Normalize status to lowercase (completed, pending, failed)
- Clean merchant names: Title Case, trim whitespace
- Mask account numbers consistently as ****XXXX (last 4 digits)
- Standardize country codes to 2-letter ISO format (US, GB, CA)
- Normalize fee to float, convert "N/A" to 0.0
- Standardize reference numbers with "REF-" prefix
- Clean descriptions: proper casing, fix whitespace, remove truncation markers
"""

backend = MLXBackend(
    model_path="lmstudio-community/Qwen3-Next-80B-A3B-Instruct-MLX-4bit",
    max_tokens=4096,
    temperature=0.7,
    verbose=True,
)

cleaner = DataCleaner(
    llm_backend=backend,
    file_path="financial_transactions.jsonl",
    chunk_size=20,
    instructions=INSTRUCTIONS,
    max_iterations=5,
)

cleaner.run()

# Rename output
if os.path.exists("cleaning_functions.py"):
    os.rename("cleaning_functions.py", "financial_cleaning_functions.py")
    print("\n=== OUTPUT SAVED TO financial_cleaning_functions.py ===")

#!/usr/bin/env python3
import os
import sys
sys.path.insert(0, '/Users/GaryT/Documents/Work/AI/Recursive-Data-Cleaner')
os.chdir('/Users/GaryT/Documents/Work/AI/Recursive-Data-Cleaner/test_cases')

from backends import MLXBackend
from recursive_cleaner import DataCleaner

INSTRUCTIONS = """
Healthcare Patient Records Cleaning Instructions:

- Normalize all dates to ISO 8601 format (YYYY-MM-DD)
- Standardize phone numbers to (XXX) XXX-XXXX format
- Normalize gender to single character: M or F
- Standardize state to 2-letter uppercase abbreviation
- Format zip codes as 5-digit strings (preserve leading zeros)
- Standardize blood type to format like "A+", "O-", "AB+"
- Convert allergies and medications to arrays, handle "None"/null consistently
- Lowercase all email addresses
- Normalize names to Title Case, remove titles (Dr., Mr., Ms., etc.)
- Standardize insurance provider names (e.g., all variants of Blue Cross Blue Shield -> "Blue Cross Blue Shield")
- Normalize address abbreviations (St., Ave., Blvd., Ln., Dr., Rd., etc.)
- Trim extra whitespace from all text fields
"""

backend = MLXBackend(
    model_path="lmstudio-community/Qwen3-Next-80B-A3B-Instruct-MLX-4bit",
    max_tokens=4096,
    temperature=0.7,
    verbose=True,
)

cleaner = DataCleaner(
    llm_backend=backend,
    file_path="healthcare_patients.jsonl",
    chunk_size=20,
    instructions=INSTRUCTIONS,
    max_iterations=5,
)

cleaner.run()

# Rename output
if os.path.exists("cleaning_functions.py"):
    os.rename("cleaning_functions.py", "healthcare_cleaning_functions.py")
    print("\n=== OUTPUT SAVED TO healthcare_cleaning_functions.py ===")

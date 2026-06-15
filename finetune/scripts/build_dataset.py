import json
import random
import os
import pandas as pd
from datasets import load_dataset

print("Initializing localized data extraction pipeline...")

TARGET_MBPP_COUNT = 300
TARGET_APPS_COUNT = 300
TARGET_MIT_OCW_COUNT = 300
TARGET_SYNTHETIC_GAP_COUNT = 200

unified_dataset = []

print(f"Step 1: Feteching datasets from MBPP Hugging face")
try:
    # Pulling from the highly optimized, token-clean parquet variant split
    dataset_full = load_dataset("mbpp", "sanitized")
    print(type(dataset_full))
    print(dataset_full)
    mbpp_list = list(dataset_full)
    mbpp_sampled = random.sample(mbpp_list, min(TARGET_MBPP_COUNT, len(mbpp_list)))

    for item in mbpp_sampled:
        prompt_text = item.get("text") or item.get("prompt") or ""
        ref_sol = item.get("code") or item.get("canonical_solution") or ""
        
        unified_dataset.append({
            "instruction": f"Solve and explain this problem like an elite engineering mentor:\n\n{prompt_text.strip()}",
            "input": f"Reference Solution: {ref_sol.strip()}",
            "source": "mbpp",
            "difficulty": "fundamental"
        })
    print(f"✅ Integrated {len(mbpp_sampled)} rows from MBPP.")
except Exception as e:
    print(f"⚠️ Redirection required for MBPP path: {e}")


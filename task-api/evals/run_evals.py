import json
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from src.llm.enrich import enrich_book

with open(os.path.join(os.path.dirname(__file__), "cases.json")) as f:
    cases = json.load(f)

print(f"Running {len(cases)} eval cases...\n")

results = []
for case in cases:
    name = case["name"]
    inp = case["input"]
    try:
        result = enrich_book(inp["title"], inp["description"], inp["price_gbp"])
        print(f"[{name}]")
        print(f"  input: {inp}")
        print(f"  output: {result.model_dump()}")

        # a simple automated hint, not a full grade — you make the real call by eye
        note = ""
        if "expected_category" in case and result.category.value != case["expected_category"]:
            note = f"  ⚠ expected category '{case['expected_category']}', got '{result.category.value}'"
        if "expected_flag" in case and case["expected_flag"] not in [f.value for f in result.quality_flags]:
            note = f"  ⚠ expected flag '{case['expected_flag']}' not present"
        if "expected_low_confidence" in case and result.confidence >= 0.5:
            note = f"  ⚠ expected low confidence, got {result.confidence}"
        if note:
            print(note)
        print()
        results.append({"name": name, "output": result.model_dump(), "note": note})
    except Exception as e:
        print(f"[{name}] FAILED: {e}\n")
        results.append({"name": name, "error": str(e)})

with open(os.path.join(os.path.dirname(__file__), "results.json"), "w") as f:
    json.dump(results, f, indent=2)

print("Saved full results to evals/results.json")
#!/usr/bin/env python3
"""
Filters llm_corrections.json to remove obvious false positives before review.

Removes:
  - Entries where current == correct (model said wrong but gave same value)
  - Entries where verdict is not "errors_found"

Writes:
  llm_corrections_filtered.json  — cleaned corrections for manual review
  llm_review.txt                 — human-readable list of what survived the filter

Run this BEFORE apply_llm_corrections.py.
"""

import json
from pathlib import Path

BASE = Path(__file__).parent
CORRECTIONS_FILE = BASE / "llm_corrections.json"
FILTERED_FILE = BASE / "llm_corrections_filtered.json"
REVIEW_FILE = BASE / "llm_review.txt"

with open(CORRECTIONS_FILE, encoding="utf-8") as f:
    corrections = json.load(f)

kept = {}
removed_same_value = 0
removed_no_errors = 0

for key, result in corrections.items():
    if result.get("verdict") != "errors_found":
        removed_no_errors += 1
        continue

    real_errors = []
    for err in result.get("errors", []):
        current = err.get("current", "")
        correct = err.get("correct", "")
        # Drop if model returned the same value it was "correcting"
        if current.strip() == correct.strip():
            removed_same_value += 1
            continue
        real_errors.append(err)

    if real_errors:
        kept[key] = {**result, "errors": real_errors}

# Write filtered corrections
with open(FILTERED_FILE, "w", encoding="utf-8") as f:
    json.dump(kept, f, ensure_ascii=False, indent=2)

# Write human-readable review file
lines = []
for key, result in kept.items():
    entry_type = result.get("type", "?")
    for err in result["errors"]:
        lines.append(
            f"[{entry_type}] {key}\n"
            f"  field:   {err.get('field')}\n"
            f"  current: {err.get('current')}\n"
            f"  correct: {err.get('correct')}\n"
            f"  reason:  {err.get('reason')}\n"
        )

with open(REVIEW_FILE, "w", encoding="utf-8") as f:
    f.write(f"Filtered corrections: {len(kept)} entries, {len(lines)} field changes\n")
    f.write(f"Removed {removed_same_value} same-value false positives\n")
    f.write(f"Removed {removed_no_errors} ok/api_error entries\n")
    f.write("=" * 60 + "\n\n")
    f.write("\n".join(lines))

print(f"Original entries with errors: {sum(1 for v in corrections.values() if v.get('verdict') == 'errors_found')}")
print(f"After removing same-value false positives: {len(kept)}")
print(f"Removed {removed_same_value} same-value false positives")
print(f"\nReview the changes in: llm_review.txt")
print(f"Then run: python3 apply_llm_corrections.py")
print(f"(apply_llm_corrections.py will auto-use llm_corrections_filtered.json if it exists)")

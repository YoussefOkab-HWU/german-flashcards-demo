#!/usr/bin/env python3
"""
Splits sentences.json into per-word JSON files so the app can load
only the sentences it needs (learned words only) instead of 84MB at once.

Run once, then push the generated sentences/ directory to GitHub.

Output:
    sentences_index.json       — maps word → file id (tiny, ~120KB)
    sentences/s0.json          — sentence data for word 0
    sentences/s1.json          — sentence data for word 1
    ...
    sentences/s4019.json       — sentence data for word 4019
"""

import json
import os
from pathlib import Path

BASE = Path(__file__).parent

print("Loading sentences.json (84MB — takes a moment)...")
with open(BASE / "sentences.json", encoding="utf-8") as f:
    data = json.load(f)

out_dir = BASE / "sentences"
out_dir.mkdir(exist_ok=True)

index = {}
for i, (word, sentences) in enumerate(data.items()):
    index[word] = i
    with open(out_dir / f"s{i}.json", "w", encoding="utf-8") as f:
        # Compact JSON — saves ~20% size per file
        json.dump(sentences, f, ensure_ascii=False, separators=(",", ":"))

with open(BASE / "sentences_index.json", "w", encoding="utf-8") as f:
    json.dump(index, f, ensure_ascii=False, separators=(",", ":"))

print(f"Done. {len(data)} per-word files in sentences/")
print(f"sentences_index.json written ({len(index)} entries)")
print(f"\nNext steps:")
print(f"  1. Verify a few files: cat sentences/s0.json | python3 -m json.tool | head -20")
print(f"  2. git add sentences/ sentences_index.json")
print(f"  3. git commit -m 'split sentences.json into per-word files'")
print(f"  4. git push")

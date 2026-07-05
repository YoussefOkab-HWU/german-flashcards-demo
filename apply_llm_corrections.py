#!/usr/bin/env python3
"""
Applies corrections from llm_corrections.json into grammar.json.
Handles both verbs (conjugation fields) and nouns (article + plural).
Review llm_report.txt first, then run this.

Usage:
    python3 apply_llm_corrections.py [--dry-run]
"""

import json
import sys
from pathlib import Path

GRAMMAR_FILE = Path(__file__).parent / "grammar.json"
# Priority: wiktionary (most accurate) > filtered LLM > raw LLM
_wikt     = Path(__file__).parent / "wikt_corrections.json"
_filtered = Path(__file__).parent / "llm_corrections_filtered.json"
_raw      = Path(__file__).parent / "llm_corrections.json"
CORRECTIONS_FILE = _wikt if _wikt.exists() else (_filtered if _filtered.exists() else _raw)
print(f"Using: {CORRECTIONS_FILE.name}")

DRY_RUN = "--dry-run" in sys.argv


def apply_noun_correction(data: dict, key: str, err: dict) -> dict | None:
    """
    Noun corrections can fix the article (in the key itself) or the plural field.
    Returns a change dict or None if nothing to do.
    """
    field = err.get("field")
    correct = err.get("correct")

    if field == "plural":
        current = data[key].get("plural")
        if current == correct:
            return None
        return {"entry": key, "field": "plural", "old": current, "new": correct, "reason": err.get("reason", "")}

    if field == "article":
        # The article is baked into the key: "der Hund" → need to rename the key
        # correct should be the full corrected key e.g. "die Hund" or just "die"
        # Normalise: if correct is just the article word, rebuild the full key
        parts = key.split(" ", 1)
        if len(parts) == 2:
            word = parts[1]
            new_key = f"{correct} {word}" if correct in ("der", "die", "das") else correct
            if new_key == key:
                return None
            return {"entry": key, "field": "article", "old": key, "new": new_key, "reason": err.get("reason", "")}

    return None


def main():
    if not CORRECTIONS_FILE.exists():
        print("ERROR: llm_corrections.json not found. Run llm_check_grammar.py first.")
        sys.exit(1)

    with open(GRAMMAR_FILE, encoding="utf-8") as f:
        data = json.load(f)

    with open(CORRECTIONS_FILE, encoding="utf-8") as f:
        corrections = json.load(f)

    changes = []
    key_renames = []  # (old_key, new_key) for noun article fixes

    for key, result in corrections.items():
        if result.get("verdict") != "errors_found":
            continue
        if key not in data:
            print(f"SKIP (not in grammar.json): {key}")
            continue

        entry_type = result.get("type") or data[key].get("type")

        for err in result.get("errors", []):
            field = err.get("field")
            correct = err.get("correct")

            if entry_type == "noun":
                change = apply_noun_correction(data, key, err)
                if change:
                    changes.append(change)
                    if field == "article":
                        key_renames.append((change["old"], change["new"]))
            else:
                # Verb: direct field patch
                if field not in data[key]:
                    print(f"SKIP (field '{field}' missing in {key})")
                    continue
                current = data[key].get(field)
                if current == correct:
                    continue
                changes.append({"entry": key, "field": field, "old": current, "new": correct, "reason": err.get("reason", "")})

    if not changes:
        print("No changes to apply.")
        return

    print(f"{'DRY RUN — ' if DRY_RUN else ''}Applying {len(changes)} corrections:\n")
    for c in changes:
        print(f"  {c['entry']}.{c['field']}: '{c['old']}' → '{c['new']}'")
        print(f"    reason: {c['reason']}")

    if DRY_RUN:
        print("\nDry run complete. Run without --dry-run to apply.")
        return

    # Apply field-level changes first
    for c in changes:
        key = c["entry"]
        field = c["field"]
        if field == "article":
            continue  # handled via key rename below
        if key in data:
            data[key][field] = c["new"]

    # Apply key renames (article fixes) — preserves insertion order
    for old_key, new_key in key_renames:
        if old_key in data:
            data[new_key] = data.pop(old_key)

    with open(GRAMMAR_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    print(f"\nApplied {len(changes)} corrections to grammar.json.")
    print("Remember to bump the service worker cache version in sw.js before pushing!")


if __name__ == "__main__":
    main()

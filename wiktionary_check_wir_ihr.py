#!/usr/bin/env python3
"""
Checks wir / ihr / Sie verb forms in grammar.json against de.wiktionary.org.
Complements wiktionary_check.py which already verified ich/du/er/perfekt_ich.

Usage:
    python3 wiktionary_check_wir_ihr.py [--dry-run]
    python3 wiktionary_check_wir_ihr.py --apply
"""

import json, re, time, sys, urllib.request, urllib.parse
from pathlib import Path

GRAMMAR_FILE     = Path(__file__).parent / "grammar.json"
CORRECTIONS_FILE = Path(__file__).parent / "wikt_corrections_wir_ihr.json"
REPORT_FILE      = Path(__file__).parent / "wikt_report_wir_ihr.txt"

DELAY   = 0.3
APPLY   = "--apply" in sys.argv
DRY_RUN = "--dry-run" in sys.argv

# ── Wiktionary ────────────────────────────────────────────────────────────────

def fetch_wikitext(title: str) -> str | None:
    params = urllib.parse.urlencode({"action":"parse","page":title,"prop":"wikitext","format":"json"})
    headers = {"User-Agent": "german-flashcard-checker/1.0 (youssefokab@yahoo.com)"}
    try:
        req = urllib.request.Request(f"https://de.wiktionary.org/w/api.php?{params}", headers=headers)
        with urllib.request.urlopen(req, timeout=10) as r:
            data = json.loads(r.read().decode())
        if "error" in data or "parse" not in data:
            return None
        return data["parse"]["wikitext"]["*"]
    except Exception:
        return None

def wikt_field(block: str, key: str) -> str | None:
    m = re.search(rf'\|{re.escape(key)}=([^\|\n}}]+)', block)
    if not m:
        return None
    val = m.group(1).strip()
    val = re.sub(r'\[\[([^\]|]+\|)?([^\]]+)\]\]', r'\2', val)
    val = val.replace("'''", "").replace("''", "").strip()
    if val in ("—", "-", "–", ""):
        return None
    return val

def parse_wir_ihr_sie(wikitext: str) -> dict | None:
    block_m = re.search(r'Deutsch Verb Übersicht(.*?)\}\}', wikitext, re.DOTALL)
    if not block_m:
        return None
    block = block_m.group(1)
    return {
        "wir": wikt_field(block, "Präsens_wir"),
        "ihr": wikt_field(block, "Präsens_ihr"),
        "Sie": wikt_field(block, "Präsens_sie, Sie"),
    }

# ── Helpers ───────────────────────────────────────────────────────────────────

REFLEXIVE_PRONOUNS = {" mich", " dich", " sich", " uns", " euch"}

def strip_reflexive(form: str) -> str:
    for p in REFLEXIVE_PRONOUNS:
        if form.endswith(p):
            return form[:-len(p)].strip()
    return form

def normalise(form: str) -> str:
    return strip_reflexive(form).strip().lower()

# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    with open(GRAMMAR_FILE, encoding="utf-8") as f:
        grammar = json.load(f)

    verbs = {k: v for k, v in grammar.items() if v.get("type") == "verb"}
    total = len(verbs)
    print(f"Checking wir/ihr/Sie for {total} verbs against de.wiktionary.org")
    print("Resume-safe: progress saved after every entry.\n")

    if CORRECTIONS_FILE.exists():
        with open(CORRECTIONS_FILE, encoding="utf-8") as f:
            all_corrections = json.load(f)
        print(f"Resuming — {len(all_corrections)} already checked.\n")
    else:
        all_corrections = {}

    checked = errors_found = not_found = 0
    report_lines = []

    for key, entry in verbs.items():
        if key in all_corrections:
            checked += 1
            if all_corrections[key].get("verdict") == "errors_found":
                errors_found += 1
            continue

        checked += 1
        pct = checked / total * 100

        is_reflexive = key.startswith("sich ")
        wikt_title = key[5:] if is_reflexive else key

        print(f"[{checked}/{total} {pct:.1f}%] {key}...", end=" ", flush=True)

        wikitext = fetch_wikitext(wikt_title)

        if not wikitext:
            print("not found")
            all_corrections[key] = {"verdict": "not_found", "errors": []}
            not_found += 1
        else:
            wikt = parse_wir_ihr_sie(wikitext)
            if not wikt:
                print("no verb block")
                all_corrections[key] = {"verdict": "no_verb_block", "errors": []}
            else:
                errs = []
                for field in ("wir", "ihr", "Sie"):
                    wikt_val = wikt.get(field)
                    json_val = entry.get(field)
                    if not wikt_val or not json_val:
                        continue
                    # Strip reflexive pronouns before comparing
                    if normalise(wikt_val) != normalise(json_val):
                        errs.append({
                            "field":   field,
                            "current": json_val,
                            "correct": wikt_val if not is_reflexive else _add_reflexive(wikt_val, field),
                            "source":  "de.wiktionary.org",
                        })

                if errs:
                    errors_found += 1
                    print(f"MISMATCH ({len(errs)})")
                    for e in errs:
                        line = f"  {e['field']}: '{e['current']}' → '{e['correct']}'"
                        print(line)
                        report_lines.append(f"{key} | {line.strip()}")
                    all_corrections[key] = {"verdict": "errors_found", "errors": errs}
                else:
                    print("ok")
                    all_corrections[key] = {"verdict": "ok", "errors": []}

        with open(CORRECTIONS_FILE, "w", encoding="utf-8") as f:
            json.dump(all_corrections, f, ensure_ascii=False, indent=2)

        time.sleep(DELAY)

    # Report
    with open(REPORT_FILE, "w", encoding="utf-8") as f:
        f.write("Wiktionary wir/ihr/Sie Audit\n")
        f.write(f"Total: {total} | Mismatches: {errors_found} | Not in Wiktionary: {not_found}\n")
        f.write("=" * 70 + "\n\n")
        f.write("\n".join(report_lines) if report_lines else "No mismatches found.")

    print(f"\n{'='*60}")
    print(f"Done. {total} verbs checked.")
    print(f"Mismatches: {errors_found}  |  Not in Wiktionary: {not_found}")

    if not APPLY:
        print(f"\nRun with --apply to patch grammar.json")
        return

    _apply(grammar, all_corrections)


def _add_reflexive(form: str, field: str) -> str:
    pronouns = {"wir": "uns", "ihr": "euch", "Sie": "sich"}
    p = pronouns.get(field, "sich")
    return f"{form} {p}"


def _apply(grammar: dict, corrections: dict):
    changes = 0
    for key, result in corrections.items():
        if result.get("verdict") != "errors_found":
            continue
        if key not in grammar:
            continue
        for err in result["errors"]:
            field = err["field"]
            if grammar[key].get(field) != err["correct"]:
                grammar[key][field] = err["correct"]
                changes += 1

    with open(GRAMMAR_FILE, "w", encoding="utf-8") as f:
        json.dump(grammar, f, ensure_ascii=False, indent=2)
    print(f"Applied {changes} corrections to grammar.json.")
    print("Bump sw.js cache version before pushing!")


if __name__ == "__main__":
    main()

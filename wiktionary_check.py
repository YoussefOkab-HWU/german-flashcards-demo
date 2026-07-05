#!/usr/bin/env python3
"""
Checks every verb and noun in grammar.json against the German Wiktionary.
Zero LLM hallucinations — every correction comes from the actual dictionary.

Verbs:  checks ich / du / er/sie/es / Partizip II
Nouns:  checks article (Genus) and Nominativ Plural

Usage:
    python3 wiktionary_check.py [--nouns-only | --verbs-only]

Outputs:
    wikt_corrections.json  — machine-readable corrections (resume-safe)
    wikt_report.txt        — human-readable mismatches
"""

import json
import re
import time
import sys
import urllib.request
import urllib.parse
from pathlib import Path

GRAMMAR_FILE = Path(__file__).parent / "grammar.json"
CORRECTIONS_FILE = Path(__file__).parent / "wikt_corrections.json"
REPORT_FILE = Path(__file__).parent / "wikt_report.txt"

API = "https://de.wiktionary.org/w/api.php"
DELAY = 0.3   # seconds between requests — be polite to Wiktionary

# ── Wiktionary fetcher ────────────────────────────────────────────────────────

def fetch_wikitext(title: str) -> str | None:
    params = urllib.parse.urlencode({
        "action": "parse",
        "page": title,
        "prop": "wikitext",
        "format": "json",
    })
    url = f"{API}?{params}"
    headers = {"User-Agent": "german-flashcard-checker/1.0 (youssefokab@yahoo.com)"}
    try:
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=10) as r:
            data = json.loads(r.read().decode())
        if "error" in data:
            return None
        return data["parse"]["wikitext"]["*"]
    except Exception:
        return None

# ── Verb parser ───────────────────────────────────────────────────────────────

def parse_verb(wikitext: str) -> dict | None:
    """Extract present-tense conjugations and Partizip II from wikitext."""
    block_match = re.search(r'Deutsch Verb Übersicht(.*?)\}\}', wikitext, re.DOTALL)
    if not block_match:
        return None
    block = block_match.group(1)

    def field(key):
        # Key may appear as "|Präsens_ich=mache" — extract value, strip wiki markup
        m = re.search(rf'\|{re.escape(key)}=([^\|\n}}]+)', block)
        if not m:
            return None
        val = m.group(1).strip()
        # Strip wiki links [[...]] and bold '''...'''
        val = re.sub(r'\[\[([^\]|]+\|)?([^\]]+)\]\]', r'\2', val)
        val = val.replace("'''", "").replace("''", "").strip()
        return val or None

    return {
        "ich":        field("Präsens_ich"),
        "du":         field("Präsens_du"),
        "er/sie/es":  field("Präsens_er, sie, es"),
        "perfekt_ich": field("Partizip II"),
    }

# ── Noun parser ───────────────────────────────────────────────────────────────

GENUS_MAP = {"m": "der", "f": "die", "n": "das"}

def parse_noun(wikitext: str) -> dict | None:
    """Extract Genus and Nominativ Plural from wikitext."""
    block_match = re.search(r'Deutsch Substantiv Übersicht(.*?)\}\}', wikitext, re.DOTALL)
    if not block_match:
        return None
    block = block_match.group(1)

    def field(key):
        m = re.search(rf'\|{re.escape(key)}=([^\|\n}}]+)', block)
        if not m:
            return None
        val = m.group(1).strip()
        val = re.sub(r'\[\[([^\]|]+\|)?([^\]]+)\]\]', r'\2', val)
        val = val.replace("'''", "").replace("''", "").strip()
        # Wiktionary uses — or - for "no plural"
        if val in ("—", "-", "–", "kein Plural", ""):
            return "kein Plural"
        return val or None

    genus_raw = field("Genus")
    article = GENUS_MAP.get(genus_raw) if genus_raw else None
    plural_stem = field("Nominativ Plural")
    plural = f"die {plural_stem}" if plural_stem and plural_stem != "kein Plural" else plural_stem

    return {"article": article, "plural": plural}

# ── Main ──────────────────────────────────────────────────────────────────────

def check_verb(infinitiv: str, entry: dict, wikitext: str) -> list[dict]:
    """Compare grammar.json verb entry against Wiktionary. Returns list of errors."""
    wikt = parse_verb(wikitext)
    if not wikt:
        return []

    field_map = {
        "ich":        "ich",
        "du":         "du",
        "er/sie/es":  "er/sie/es",
        "perfekt_ich": "perfekt_ich",
    }
    errors = []
    for wikt_key, json_key in field_map.items():
        wikt_val = wikt.get(wikt_key)
        json_val = entry.get(json_key)
        if not wikt_val or not json_val:
            continue
        if wikt_val.strip().lower() != json_val.strip().lower():
            errors.append({
                "field":   json_key,
                "current": json_val,
                "correct": wikt_val,
                "source":  "de.wiktionary.org",
            })
    return errors


def check_noun(key: str, entry: dict, wikitext: str) -> list[dict]:
    """Compare grammar.json noun entry against Wiktionary. Returns list of errors."""
    wikt = parse_noun(wikitext)
    if not wikt:
        return []

    errors = []
    # Check article (gender)
    current_article = key.split()[0]   # "der Hund" → "der"
    if wikt["article"] and wikt["article"] != current_article:
        # The "correct" here is the corrected full noun key
        stem = " ".join(key.split()[1:])
        errors.append({
            "field":   "article",
            "current": current_article,
            "correct": wikt["article"],
            "new_key": f"{wikt['article']} {stem}",
            "source":  "de.wiktionary.org",
        })

    # Check plural
    current_plural = entry.get("plural", "")
    wikt_plural = wikt.get("plural")
    if wikt_plural and current_plural:
        if wikt_plural.strip().lower() != current_plural.strip().lower():
            errors.append({
                "field":   "plural",
                "current": current_plural,
                "correct": wikt_plural,
                "source":  "de.wiktionary.org",
            })

    return errors


def main():
    filter_type = None
    if "--nouns-only" in sys.argv:
        filter_type = "noun"
    elif "--verbs-only" in sys.argv:
        filter_type = "verb"

    with open(GRAMMAR_FILE, encoding="utf-8") as f:
        data = json.load(f)

    entries = {
        k: v for k, v in data.items()
        if v.get("type") in ("verb", "noun")
        and (filter_type is None or v.get("type") == filter_type)
    }

    total = len(entries)
    verb_count = sum(1 for v in entries.values() if v.get("type") == "verb")
    noun_count = sum(1 for v in entries.values() if v.get("type") == "noun")
    print(f"Checking {total} entries ({verb_count} verbs, {noun_count} nouns) against de.wiktionary.org")
    print("Resume-safe: progress saved after every entry.\n")

    # Resume
    if CORRECTIONS_FILE.exists():
        with open(CORRECTIONS_FILE, encoding="utf-8") as f:
            all_corrections = json.load(f)
        print(f"Resuming — {len(all_corrections)} already checked.\n")
    else:
        all_corrections = {}

    checked = errors_found = not_found = 0
    report_lines = []

    for key, entry in entries.items():
        if key in all_corrections:
            checked += 1
            if all_corrections[key].get("verdict") == "errors_found":
                errors_found += 1
            continue

        checked += 1
        pct = checked / total * 100
        entry_type = entry.get("type")

        # Wiktionary page title:
        # - nouns: strip article  ("der Hund" → "Hund")
        # - reflexive verbs: strip "sich "  ("sich erinnern" → "erinnern")
        # - multi-word verbs: use as-is and let not-found handle it
        if entry_type == "noun":
            wikt_title = " ".join(key.split()[1:])
        elif key.startswith("sich "):
            wikt_title = key[5:]   # "sich erinnern" → "erinnern"
        else:
            wikt_title = key

        print(f"[{checked}/{total} {pct:.1f}%] [{entry_type}] {key}...", end=" ", flush=True)

        wikitext = fetch_wikitext(wikt_title)

        if not wikitext:
            print("not found")
            all_corrections[key] = {"verdict": "not_found", "errors": [], "type": entry_type}
            not_found += 1
        else:
            if entry_type == "verb":
                errs = check_verb(key, entry, wikitext)
            else:
                errs = check_noun(key, entry, wikitext)

            if errs:
                errors_found += 1
                print(f"MISMATCH ({len(errs)})")
                for e in errs:
                    line = f"  {e['field']}: '{e['current']}' → '{e['correct']}'"
                    print(line)
                    report_lines.append(f"{key} | {line.strip()}")
                all_corrections[key] = {"verdict": "errors_found", "errors": errs, "type": entry_type}
            else:
                print("ok")
                all_corrections[key] = {"verdict": "ok", "errors": [], "type": entry_type}

        # Save progress after every entry
        with open(CORRECTIONS_FILE, "w", encoding="utf-8") as f:
            json.dump(all_corrections, f, ensure_ascii=False, indent=2)

        time.sleep(DELAY)

    # Report
    with open(REPORT_FILE, "w", encoding="utf-8") as f:
        f.write(f"Wiktionary Grammar Audit\n")
        f.write(f"Total: {total} | Mismatches: {errors_found} | Not in Wiktionary: {not_found}\n")
        f.write("=" * 70 + "\n\n")
        f.write("\n".join(report_lines) if report_lines else "No mismatches found.")

    print(f"\n{'='*60}")
    print(f"Done. {total} entries checked.")
    print(f"Mismatches: {errors_found}  |  Not in Wiktionary: {not_found}")
    print(f"Corrections: {CORRECTIONS_FILE}")
    print(f"Report: {REPORT_FILE}")
    print(f"\nNext: python3 apply_llm_corrections.py  (works with wikt_corrections.json too)")


if __name__ == "__main__":
    main()

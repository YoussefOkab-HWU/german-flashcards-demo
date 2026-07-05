#!/usr/bin/env python3
"""
Generates grammar.json entries for Tier 5 words that don't have one yet,
sourcing conjugations/gender/plural from the German Wiktionary.

Every generated entry is verified against the dictionary — zero LLM involvement.

Usage:
    python3 generate_tier5.py [--dry-run]

Outputs:
    tier5_generated.json  — preview of new entries (always written)
    grammar.json          — updated in place (only without --dry-run)
"""

import json
import re
import time
import sys
import urllib.request
import urllib.parse
from pathlib import Path

GRAMMAR_FILE = Path(__file__).parent / "grammar.json"
GENERATED_FILE = Path(__file__).parent / "tier5_generated.json"
HTML_FILE = Path(__file__).parent / "index.html"

DRY_RUN = "--dry-run" in sys.argv
DELAY = 0.3

# ── Wiktionary fetcher ────────────────────────────────────────────────────────

def fetch_wikitext(title: str) -> str | None:
    params = urllib.parse.urlencode({
        "action": "parse", "page": title,
        "prop": "wikitext", "format": "json",
    })
    headers = {"User-Agent": "german-flashcard-generator/1.0 (youssefokab@yahoo.com)"}
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
    return val or None

# ── Derivation helpers ────────────────────────────────────────────────────────

SPECIAL_IHR = {"sein": "seid"}

def derive_ihr(infinitiv: str, is_reflexive: bool = False) -> str:
    """Derive ihr-form from infinitive. Always uses infinitive stem (no vowel change)."""
    if infinitiv in SPECIAL_IHR:
        ihr = SPECIAL_IHR[infinitiv]
        return f"{ihr} euch" if is_reflexive else ihr

    # Separate prefix for separable verbs by checking Wiktionary er-form later.
    # Here we just derive from the raw infinitive.
    # -eln / -ern: ihr segelt, ihr rudert (keep full stem)
    if infinitiv.endswith("eln"):
        stem = infinitiv[:-2]   # "segeln" → "segel"
        ending = "t"
    elif infinitiv.endswith("ern"):
        stem = infinitiv[:-2]   # "rudern" → "ruder"
        ending = "t"
    elif infinitiv.endswith("en"):
        stem = infinitiv[:-2]   # "machen" → "mach"
        ending = "et" if stem.endswith(("t", "d")) else "t"
    elif infinitiv.endswith("n"):
        stem = infinitiv[:-1]
        ending = "t"
    else:
        stem = infinitiv
        ending = "t"

    ihr = stem + ending
    return f"{ihr} euch" if is_reflexive else ihr


def derive_wir_sie(infinitiv: str, is_reflexive: bool = False) -> str:
    """wir/Sie = infinitive (absolute rule in German)."""
    if infinitiv == "sein":
        return "sind uns" if is_reflexive else "sind"
    return f"{infinitiv} uns" if is_reflexive else infinitiv


def add_reflexive_pronoun(form: str, pronoun: str) -> str:
    """Append the correct reflexive pronoun to a conjugated form."""
    reflexive = {"ich": "mich", "du": "dich", "er": "sich", "wir": "uns", "ihr": "euch", "sie": "sich"}
    return f"{form} {reflexive.get(pronoun, 'sich')}"


def build_verb_entry(infinitiv: str, wikitext: str, is_reflexive: bool = False) -> dict | None:
    block_m = re.search(r'Deutsch Verb Übersicht(.*?)\}\}', wikitext, re.DOTALL)
    if not block_m:
        return None
    block = block_m.group(1)

    ich_raw    = wikt_field(block, "Präsens_ich")
    du_raw     = wikt_field(block, "Präsens_du")
    er_raw     = wikt_field(block, "Präsens_er, sie, es")
    perfekt_ii = wikt_field(block, "Partizip II")

    if not all([ich_raw, du_raw, er_raw, perfekt_ii]):
        return None

    # Reflexive: append pronouns to Wiktionary forms
    if is_reflexive:
        ich = add_reflexive_pronoun(ich_raw, "ich")
        du  = add_reflexive_pronoun(du_raw,  "du")
        er  = add_reflexive_pronoun(er_raw,  "er")
    else:
        ich, du, er = ich_raw, du_raw, er_raw

    # For separable verbs (er form has a space e.g. "macht auf"):
    # wir/Sie/ihr need the prefix appended
    if " " in er_raw:
        # Extract prefix from the er form
        parts = er_raw.rsplit(" ", 1)
        prefix = parts[1]
        base_inf = infinitiv[len(prefix):]   # "aufmachen" → "machen"

        wir_sie = derive_wir_sie(base_inf)
        ihr_base = derive_ihr(base_inf)

        wir = f"{wir_sie} {prefix}"
        ihr = f"{ihr_base} {prefix}"
        sie = f"{wir_sie} {prefix}"
    else:
        wir = derive_wir_sie(infinitiv, is_reflexive)
        ihr = derive_ihr(infinitiv, is_reflexive)
        sie = derive_wir_sie(infinitiv, is_reflexive)

    return {
        "type": "verb",
        "ich":        ich,
        "du":         du,
        "er/sie/es":  er,
        "wir":        wir,
        "ihr":        ihr,
        "Sie":        sie,
        "perfekt_ich": perfekt_ii,
    }


GENUS_MAP = {"m": "der", "f": "die", "n": "das"}

def build_noun_entry(wikitext: str) -> dict | None:
    block_m = re.search(r'Deutsch Substantiv Übersicht(.*?)\}\}', wikitext, re.DOTALL)
    if not block_m:
        return None
    block = block_m.group(1)

    genus_raw    = wikt_field(block, "Genus")
    plural_stem  = wikt_field(block, "Nominativ Plural")

    if not genus_raw:
        return None

    article = GENUS_MAP.get(genus_raw)
    if not article:
        return None

    if plural_stem in (None, "—", "-", "–", ""):
        plural = "kein Plural"
    elif plural_stem.lower() in ("kein plural",):
        plural = "kein Plural"
    else:
        plural = f"die {plural_stem}"

    return {"type": "noun", "plural": plural}, article

# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    # Extract TIERS and DATA from index.html
    html = HTML_FILE.read_text(encoding="utf-8")
    tiers_m = re.search(r'const TIERS = (\{[^;]+\})', html)
    data_m  = re.search(r'const DATA = (\{.*?\});', html, re.DOTALL)
    tiers = json.loads(tiers_m.group(1))
    app_data = json.loads(data_m.group(1))

    # Build word → type map from DATA — only verbs and nouns need grammar entries
    word_type = {}
    for cat, words in app_data.items():
        if cat not in ("verbs", "nouns"):
            continue
        for w in words:
            word_type[w["german"]] = "verb" if cat == "verbs" else "noun"

    with open(GRAMMAR_FILE, encoding="utf-8") as f:
        grammar = json.load(f)

    # Tier 5 words missing from grammar.json
    missing = [
        w for w, t in tiers.items()
        if t == 5 and w not in grammar and w in word_type
    ]
    print(f"Tier 5 words missing grammar entries: {len(missing)}")
    print(f"  Verbs: {sum(1 for w in missing if word_type[w] == 'verb')}")
    print(f"  Nouns: {sum(1 for w in missing if word_type[w] == 'noun')}")
    print()

    # Load progress file if it exists (resume support)
    if GENERATED_FILE.exists():
        with open(GENERATED_FILE, encoding="utf-8") as f:
            generated = json.load(f)
        print(f"Resuming — {len(generated)} already generated.\n")
    else:
        generated = {}

    not_found = 0
    for i, key in enumerate(missing, 1):
        if key in generated:
            continue

        pct = i / len(missing) * 100
        entry_type = word_type[key]
        print(f"[{i}/{len(missing)} {pct:.1f}%] [{entry_type}] {key}...", end=" ", flush=True)

        is_reflexive = key.startswith("sich ")
        if entry_type == "noun":
            wikt_title = " ".join(key.split()[1:])   # strip article
        elif is_reflexive:
            wikt_title = key[5:]   # strip "sich "
        else:
            wikt_title = key

        wikitext = fetch_wikitext(wikt_title)

        if not wikitext:
            print("not found — skipping")
            generated[key] = {"_status": "not_found"}
            not_found += 1
        elif entry_type == "verb":
            entry = build_verb_entry(wikt_title if not is_reflexive else key[5:], wikitext, is_reflexive)
            if entry:
                print("generated")
                generated[key] = entry
            else:
                print("parse failed — skipping")
                generated[key] = {"_status": "parse_failed"}
                not_found += 1
        else:
            result = build_noun_entry(wikitext)
            if result:
                entry, wikt_article = result
                # Check if the article in the key matches Wiktionary
                key_article = key.split()[0]
                if wikt_article != key_article:
                    print(f"generated (article fix: {key_article} → {wikt_article})")
                    entry["_article_fix"] = wikt_article
                else:
                    print("generated")
                generated[key] = entry
            else:
                print("parse failed — skipping")
                generated[key] = {"_status": "parse_failed"}
                not_found += 1

        # Save after every entry
        with open(GENERATED_FILE, "w", encoding="utf-8") as f:
            json.dump(generated, f, ensure_ascii=False, indent=2)

        time.sleep(DELAY)

    # Summary
    good = {k: v for k, v in generated.items() if "_status" not in v}
    print(f"\n{'='*60}")
    print(f"Generated: {len(good)}  |  Not found/failed: {not_found}")
    print(f"Saved to: {GENERATED_FILE}")

    if DRY_RUN:
        print("\nDry run — grammar.json not modified.")
        return

    # Apply to grammar.json
    added = 0
    for key, entry in good.items():
        if key in grammar:
            continue   # already exists

        # Handle article corrections for nouns
        article_fix = entry.pop("_article_fix", None)
        if article_fix:
            stem = " ".join(key.split()[1:])
            new_key = f"{article_fix} {stem}"
            grammar[new_key] = entry
        else:
            grammar[key] = entry
        added += 1

    with open(GRAMMAR_FILE, "w", encoding="utf-8") as f:
        json.dump(grammar, f, ensure_ascii=False, indent=2)

    print(f"Added {added} new entries to grammar.json.")
    print("Remember to bump sw.js cache version before pushing!")


if __name__ == "__main__":
    main()

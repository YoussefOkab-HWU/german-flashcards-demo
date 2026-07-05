#!/usr/bin/env python3
"""
Checks every Tier 5 word against German Wiktionary to find fake/non-German words.

Handles inflected adjectives (analytische → analytisch),
past participles (digitalisiert → digitalisieren),
and other derived forms before declaring a word fake.

Usage:
    python3 scan_tier5_words.py           # scan only
    python3 scan_tier5_words.py --remove  # scan then remove confirmed fakes
"""

import re, json, time, sys, urllib.request, urllib.parse
from pathlib import Path

HTML_FILE    = Path(__file__).parent / "index.html"
GRAMMAR_FILE = Path(__file__).parent / "grammar.json"
SCAN_FILE    = Path(__file__).parent / "tier5_scan.json"

REMOVE = "--remove" in sys.argv
DELAY  = 0.25

# ── Wiktionary ────────────────────────────────────────────────────────────────

def fetch_wikitext(title: str) -> str | None:
    params = urllib.parse.urlencode({"action":"parse","page":title,"prop":"wikitext","format":"json"})
    headers = {"User-Agent": "german-flashcard-scanner/1.0 (youssefokab@yahoo.com)"}
    try:
        req = urllib.request.Request(f"https://de.wiktionary.org/w/api.php?{params}", headers=headers)
        with urllib.request.urlopen(req, timeout=10) as r:
            data = json.loads(r.read().decode())
        if "error" in data or "parse" not in data:
            return None
        return data["parse"]["wikitext"]["*"]
    except Exception:
        return None

def has_german_entry(wikitext: str) -> bool:
    """True if the Wiktionary page has a German language section.
    de.wiktionary uses {{Sprache|Deutsch}} and {{Wortart|...|Deutsch}} templates."""
    return "|Deutsch}}" in wikitext or "Deutsch Adjektiv" in wikitext

# ── Base-form normalisation ───────────────────────────────────────────────────

def base_form_candidates(word: str) -> list[str]:
    """
    Return possible base forms to try when the inflected form isn't found.
    Handles adjective declension and past-participle adjectives.
    """
    candidates = []

    # Past participles of -ieren verbs: digitalisiert → digitalisieren
    if word.endswith("iert"):
        candidates.append(word[:-1] + "en")   # digitalisiert → digitalisieren

    # Past participles of separable/prefix verbs ending in -t
    # e.g. vernetzt → vernetzen, ausgestrahlt → ausstrahlen
    if word.endswith("t") and len(word) > 4:
        candidates.append(word[:-1] + "en")   # vernetzt → vernetzten (wrong but try)
        candidates.append(word + "en")         # vernetz + en doesn't help, skip

    # Adjective strong/weak declension endings — try the base adjective
    # Order matters: try longer suffixes first to avoid over-stripping
    adj_endings = [
        ("ische", "isch"), ("ischen", "isch"), ("ischer", "isch"),
        ("isches", "isch"), ("ischem", "isch"),
        ("elle",  "ell"),  ("ellen",  "ell"),  ("eller",  "ell"),
        ("elles", "ell"),  ("ellem",  "ell"),
        ("ive",   "iv"),   ("iven",   "iv"),   ("iver",   "iv"),
        ("ives",  "iv"),   ("ivem",   "iv"),
        ("ale",   "al"),   ("alen",   "al"),   ("aler",   "al"),
        ("äre",   "är"),   ("ären",   "är"),   ("ärer",   "är"),
        # Generic endings — least specific, try last
        ("en", ""), ("er", ""), ("es", ""), ("em", ""), ("e", ""),
    ]
    for suffix, replacement in adj_endings:
        if word.endswith(suffix) and len(word) - len(suffix) >= 3:
            base = word[:-len(suffix)] + replacement
            if base not in candidates and base != word:
                candidates.append(base)

    return candidates


def lookup_with_fallback(word: str) -> tuple[str, str]:
    """
    Look up word in Wiktionary, trying base forms if the direct lookup fails.
    Returns (status, matched_title) where status is 'real' or 'fake'.
    """
    # Direct lookup
    wikitext = fetch_wikitext(word)
    if wikitext and has_german_entry(wikitext):
        return "real", word
    time.sleep(DELAY)

    # Try base forms
    for base in base_form_candidates(word):
        wikitext = fetch_wikitext(base)
        if wikitext and has_german_entry(wikitext):
            return "real", base
        time.sleep(DELAY)

    return "fake", word

# ── Load Tier 5 ───────────────────────────────────────────────────────────────

html     = HTML_FILE.read_text(encoding="utf-8")
tiers    = json.loads(re.search(r'const TIERS = (\{[^;]+\})', html).group(1))
app_data = json.loads(re.search(r'const DATA = (\{.*?\});', html, re.DOTALL).group(1))

word_type = {w["german"]: cat for cat, words in app_data.items() for w in words}
tier5     = [w for w, t in tiers.items() if t == 5]
print(f"Tier 5 words to scan: {len(tier5)}\n")

scan = json.loads(SCAN_FILE.read_text()) if SCAN_FILE.exists() else {}
print(f"Resuming — {len(scan)} already confirmed real, rest will be checked.\n")

for i, word in enumerate(tier5, 1):
    if word in scan:
        continue

    pct = i / len(tier5) * 100
    print(f"[{i}/{len(tier5)} {pct:.1f}%] {word}...", end=" ", flush=True)

    # Determine lookup title
    if word.startswith("sich "):
        title = word[5:]
    elif word.split()[0] in ("der", "die", "das"):
        title = " ".join(word.split()[1:])
    else:
        title = word

    # Multi-word phrase → look up each content word, real if any is found
    words_to_try = [title]
    if " " in title:
        words_to_try = [w for w in title.split() if w.lower() not in
                        ("sein", "werden", "haben", "sich", "machen", "lassen",
                         "und", "oder", "mit", "für", "auf", "an", "in")]
        words_to_try = words_to_try or [title.split()[-1]]

    found = False
    for t in words_to_try:
        status, matched = lookup_with_fallback(t)
        if status == "real":
            found = True
            extra = f" (via '{matched}')" if matched != t else ""
            print(f"real{extra}")
            break

    if not found:
        print("FAKE")

    scan[word] = "real" if found else "fake"
    SCAN_FILE.write_text(json.dumps(scan, ensure_ascii=False, indent=2))

# ── Report ────────────────────────────────────────────────────────────────────
grammar = json.loads(GRAMMAR_FILE.read_text())
real_words = [w for w, s in scan.items() if s == "real"]
fake_words = [w for w, s in scan.items() if s == "fake"]

print(f"\n{'='*60}")
print(f"Total Tier 5 scanned: {len(scan)}")
print(f"  Real German words:  {len(real_words)}")
print(f"  Fake / not German:  {len(fake_words)}")
print(f"\nFake words ({len(fake_words)}):")
for w in sorted(fake_words):
    loc = "in grammar.json" if w in grammar else "flashcard only"
    print(f"  [{loc}] {w}")

if not REMOVE:
    print(f"\nRun with --remove to delete these from grammar.json and the flashcard list.")
else:
    # Remove from grammar.json
    removed_grammar = [w for w in fake_words if w in grammar]
    for w in removed_grammar:
        del grammar[w]
    GRAMMAR_FILE.write_text(json.dumps(grammar, ensure_ascii=False, indent=2))

    # Remove from DATA in index.html
    html_new = html
    removed_data = 0
    for w in fake_words:
        escaped = re.escape(json.dumps(w, ensure_ascii=False))
        pattern = rf',?\s*\{{\s*"german"\s*:\s*{escaped}\s*,[^}}]+\}}'
        html_new, n = re.subn(pattern, "", html_new)
        removed_data += n

    HTML_FILE.write_text(html_new, encoding="utf-8")

    print(f"\nRemoved {len(removed_grammar)} from grammar.json")
    print(f"Removed {removed_data} from DATA in index.html")
    print("Bump sw.js cache version before pushing!")

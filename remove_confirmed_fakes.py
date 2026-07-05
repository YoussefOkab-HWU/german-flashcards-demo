#!/usr/bin/env python3
"""
Removes confirmed fake/typo Tier 5 words from grammar.json and index.html.
Saves borderline words to tier5_review.txt for manual review.

Usage:
    python3 remove_confirmed_fakes.py [--dry-run]
"""

import re, json, sys
from pathlib import Path

HTML_FILE    = Path(__file__).parent / "index.html"
GRAMMAR_FILE = Path(__file__).parent / "grammar.json"
REVIEW_FILE  = Path(__file__).parent / "tier5_review.txt"

DRY_RUN = "--dry-run" in sys.argv

# ── Words confirmed safe to remove ───────────────────────────────────────────
# Typos where the correct spelling exists in earlier tiers
TYPOS = {
    "analyssieren",      # → analysieren
    "bestimnmen",        # → bestimmen
    "differnzieren",     # → differenzieren
    "dikutieren",        # → diskutieren
    "entauschen",        # → enttäuschen
    "päsentieren",       # → präsentieren
    "marginalsieren",    # → marginalisieren
    "prognosieren",      # → prognostizieren
    "projeketieren",     # → projektieren
    "sarcastisch",       # → sarkastisch
    "sensibelisieren",   # → sensibilisieren
    "sociologisch",      # → soziologisch
    "stetstellen",       # → feststellen
    "vehren",            # → verehren
    "desshalb",          # → deshalb
    "provokieren",       # → provozieren
    "inbeziehen",        # → einbeziehen
}

# Clearly invented / nonsense words
INVENTED = {
    "abaunieren",
    "apachieren",
    "estimatisieren",
    "kapazifizieren",
    "persuaderen",
    "eingestalten",
    "konkreditieren",
    "reaktionenlos",
    "subjektifizieren",
    "verantisieren",
    "wegdüngen",
    "zugestalten",
    "exklaren",
    "beargumentieren",
    "hypothesisieren",
    "revisionieren",     # should be revidieren
    "reflexionieren",    # should be reflektieren
    "equivok",           # wrong form of äquivok
    "legifizieren",
}

# Wrong grammatical forms (not base forms, already covered by correct entry)
WRONG_FORMS = {
    "besonder",          # wrong form of besonders/besondere
    "bequemlich",        # bequem is real, bequemlich is not
    "beschwerden",       # wrong form (should be sich beschweren / die Beschwerden)
}

SAFE_TO_REMOVE = TYPOS | INVENTED | WRONG_FORMS

# ── Words to keep for manual review ──────────────────────────────────────────
# Real German words that Wiktionary happens not to have entries for,
# plus borderline compounds/academic terms
REVIEW = {
    # Definitely real German words
    "ausklingen":        "real German separable verb (to fade out/die away)",
    "ausschmeißen":      "real German separable verb (to throw out)",
    "sozialisieren":     "real German verb (to socialize)",
    "dissoziieren":      "real German verb (to dissociate)",
    "multidisziplinär":  "real German adjective (multidisciplinary)",
    "unzweifelbar":      "real German adverb (undoubtedly)",
    "inklusiv":          "real German adjective (inclusive)",
    "individualistisch": "real German adjective (individualistic)",
    "insignifikant":     "real German adjective (insignificant)",
    "katalysieren":      "real German verb (to catalyze)",
    "neuordnen":         "real German separable verb (to reorganize)",
    "friedensliebend":   "real German compound adjective (peace-loving)",
    "stillgeboren":      "real German adjective (stillborn)",
    "reinterpretieren":  "real German verb (to reinterpret)",
    "rekombinieren":     "real German verb (to recombine)",
    "kontextualisieren": "real German verb, academic usage",
    "ergebnisorientiert":"real German adjective (results-oriented)",
    "leistungssorientiert": "real German adjective (performance-oriented)",
    "hierarchisieren":   "real German verb, academic usage",
    "klarerweise":       "real Austrian German adverb (clearly)",
    "zwar...aber":       "real German conjunction pair",
    # Borderline — likely real but uncommon
    "antipathetisch":    "likely real adjective (antipathetic)",
    "grundlegen":        "likely real separable verb",
    "hypothetisieren":   "questionable — may exist in academic German",
    "kartentechnisch":   "compound adjective, may exist",
    "komplexitätsreich": "compound adjective, may exist",
    "konkurrent":        "may exist as adjective (competing)",
    "konzeptionalisieren": "academic German, may exist",
    "meinungsstark":     "compound adjective, may exist",
    "perspektivieren":   "academic German verb",
    "persönlichkeitszentriert": "compound, may exist",
    "pseudonymieren":    "may exist (to pseudonymize)",
    "rekonstruktiv":     "may exist as adjective",
    "rezeptorientiert":  "compound, may exist",
    "routinisieren":     "questionable",
    "sozialkompetent":   "compound, may exist",
    "strategisieren":    "questionable",
    "strategischerweise":"adverb, may exist",
    "strebenorientiert": "compound, questionable",
    "visionieren":       "questionable",
    "verbotsverachtend": "compound, may exist",
    # Inflected forms / wrong entry format
    "astrophysikalische":"inflected form of astrophysikalisch",
    "beflüstert":        "past participle / inflected form",
    "begründungslos":    "compound adjective, may exist",
    "bewusstseinsfähig": "compound, may exist",
    "branchig":          "questionable",
    "brillen":           "plural of Brille? listed as verb by mistake?",
    "bürgeln":           "questionable",
    "bürgerschaftlich":  "compound adjective, may exist",
    "das Abstrakte":     "nominalised adjective, may exist",
    "der Lehraufbau":    "compound noun, may exist",
    "die Grundlegung":   "compound noun, may exist (foundation)",
    "die Jargonbildung": "compound noun, may exist",
    "die Thesenanalyse": "compound noun, may exist",
    "effektiverweise":   "adverb, may exist",
    "elendselig":        "compound adjective, may exist",
    "erinnerungsreich":  "compound adjective, may exist",
    "formgebenden":      "inflected form of formgebend",
    "früchten":          "questionable verb form",
    "haltern":           "questionable",
    "idealisch":         "should be idealistisch? may exist regionally",
    "nuttig":            "questionable / colloquial",
    "präferenzen":       "plural form — should be die Präferenz",
    "schuldbehaftete":   "inflected adjective form",
    "sensibilität":      "should be die Sensibilität (missing article)",
    "sicherhaft":        "questionable",
    "spekulationen":     "plural form — should be die Spekulation",
}


def main():
    html    = HTML_FILE.read_text(encoding="utf-8")
    grammar = json.loads(GRAMMAR_FILE.read_text())

    print(f"Safe to remove: {len(SAFE_TO_REMOVE)}")
    print(f"Sent to review: {len(REVIEW)}\n")

    # Write review file
    lines = ["Tier 5 words flagged as fake but needing manual review\n",
             "=" * 60 + "\n\n"]
    for word, note in sorted(REVIEW.items()):
        in_grammar = "  [in grammar.json]" if word in grammar else ""
        lines.append(f"{word}{in_grammar}\n  → {note}\n\n")
    REVIEW_FILE.write_text("".join(lines), encoding="utf-8")
    print(f"Review file written: {REVIEW_FILE}\n")

    # Remove safe words from grammar.json
    removed_grammar = [w for w in SAFE_TO_REMOVE if w in grammar]
    if removed_grammar:
        print(f"Removing from grammar.json ({len(removed_grammar)}):")
        for w in sorted(removed_grammar):
            print(f"  {w}")

    # Remove safe words from DATA in index.html
    html_new = html
    removed_data = 0
    removed_data_words = []
    for w in SAFE_TO_REMOVE:
        escaped = re.escape(json.dumps(w, ensure_ascii=False))
        pattern = rf',?\s*\{{\s*"german"\s*:\s*{escaped}\s*,[^}}]+\}}'
        html_new, n = re.subn(pattern, "", html_new)
        if n:
            removed_data += n
            removed_data_words.append(w)

    print(f"\nRemoving from index.html DATA ({removed_data} entries):")
    for w in sorted(removed_data_words):
        print(f"  {w}")

    if DRY_RUN:
        print("\nDry run — no files modified.")
        return

    for w in removed_grammar:
        del grammar[w]
    GRAMMAR_FILE.write_text(json.dumps(grammar, ensure_ascii=False, indent=2))

    HTML_FILE.write_text(html_new, encoding="utf-8")

    print(f"\nDone. Removed {len(removed_grammar)} from grammar.json, {removed_data} from index.html.")
    print("Bump sw.js cache version before pushing!")


if __name__ == "__main__":
    main()

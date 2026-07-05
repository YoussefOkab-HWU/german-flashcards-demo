#!/usr/bin/env python3
"""
Local LLM-based German grammar checker using Ollama (gemma2:9b).
Checks all verbs (conjugations) and nouns (gender + plural) in grammar.json.
Zero API cost. Accuracy over speed: one focused request per entry.

Usage:
    python3 llm_check_grammar.py [--nouns-only | --verbs-only]

Outputs:
    llm_corrections.json  — machine-readable corrections (resume-safe)
    llm_report.txt        — human-readable audit log
"""

import json
import time
import sys
from pathlib import Path

try:
    import ollama
except ImportError:
    print("ERROR: Run: pip install ollama")
    sys.exit(1)

GRAMMAR_FILE = Path(__file__).parent / "grammar.json"
CORRECTIONS_FILE = Path(__file__).parent / "llm_corrections.json"
REPORT_FILE = Path(__file__).parent / "llm_report.txt"

MODEL = "gemma2:9b"

VERB_PROMPT = """You are an expert German linguist. Verify these verb conjugations strictly.

Rules:
1. Present tense regular endings: ich→-e, du→-st, er→-t, wir=infinitiv, ihr→-t, Sie=infinitiv
2. SEPARABLE VERBS (aufmachen, einschätzen, anrufen, etc.): the prefix splits off in conjugated forms and moves to the END.
   CORRECT: aufmachen → ich mache auf | du machst auf | er macht auf
   WRONG:   aufmachen → ich aufmache | du aufmachst
3. INSEPARABLE PREFIXES (be-, ver-, er-, ent-, zer-, miss-, ge-, emp-, hinter-): NEVER split off. No space.
4. PARTIZIP II (perfekt_ich = only the Partizip II, no auxiliary):
   - Regular verb: ge- + stem + -t  →  spielen=gespielt, machen=gemacht
   - Irregular verb: ge- + stem + -en  →  fahren=gefahren, geben=gegeben
   - Inseparable prefix: NO ge-  →  besuchen=besucht, verstehen=verstanden, verlieren=verloren
   - Separable non-ieren: ge- between prefix and stem  →  aufmachen=aufgemacht, einschätzen=eingeschätzt
   - -ieren verbs: NO ge-, stem+-t  →  präsentieren=präsentiert, anprobieren=anprobiert
5. Stem ends in -t or -d: add -e- before -st/-t  →  antworten: antwortest/antwortet
6. Strong verbs: vowel change in du/er  →  fahren: fährst/fährt  |  geben: gibst/gibt
7. -ern verbs (rudern, liefern): ich = rudere, liefere  (NOT rudert, liefere without e)
8. -eln verbs (segeln, zweifeln): ich contracts  →  segle, zweifle

Verb to check:
{verb_block}

Respond with ONLY a JSON object, no explanation, no markdown:
{{"verdict": "ok", "errors": []}}
or
{{"verdict": "errors_found", "errors": [{{"field": "ich", "current": "wrong", "correct": "right", "reason": "brief reason"}}]}}
"""

NOUN_PROMPT = """You are an expert German linguist. Verify this noun's gender and plural strictly.

The noun is written as: ARTICLE NOUN  (e.g. "der Hund", "die Katze", "das Kind")
The plural field uses "die" + plural form, or "kein Plural" for uncountable nouns.

Check:
1. GENDER: Is the article (der/die/das) correct?
2. PLURAL: Is the plural form correct?
   Common patterns:
   - -ung, -heit, -keit, -schaft, -tion, -ie endings → always feminine (die), plural -en/-ionen
   - -chen, -lein → always neuter (das), plural = same form (or kein Plural)
   - compound nouns → plural of the last component

Noun to check:
{noun_block}

Respond with ONLY a JSON object, no explanation, no markdown:
{{"verdict": "ok", "errors": []}}
or
{{"verdict": "errors_found", "errors": [{{"field": "article", "current": "der", "correct": "die", "reason": "brief reason"}}]}}
Valid field values: "article" or "plural"
"""


def check_entry(key: str, entry: dict, entry_type: str) -> dict:
    if entry_type == "verb":
        fields = {k: v for k, v in entry.items() if k != "type"}
        block = f"infinitiv: {key}\n" + "\n".join(f"{k}: {v}" for k, v in fields.items())
        prompt = VERB_PROMPT.format(verb_block=block)
    else:
        plural = entry.get("plural", "?")
        block = f"noun: {key}\nplural: {plural}"
        prompt = NOUN_PROMPT.format(noun_block=block)

    for attempt in range(3):
        try:
            response = ollama.chat(
                model=MODEL,
                messages=[{"role": "user", "content": prompt}],
                format="json",   # forces JSON output mode
                options={"temperature": 0, "num_predict": 300},
            )
            raw = response["message"]["content"].strip()
            return json.loads(raw)
        except json.JSONDecodeError as e:
            print(f"  [WARN] JSON parse error for '{key}' attempt {attempt+1}: {e}")
            time.sleep(1)
        except Exception as e:
            print(f"  [ERROR] '{key}': {e}")
            time.sleep(2)

    return {"verdict": "api_error", "errors": []}


def main():
    filter_type = None
    if "--nouns-only" in sys.argv:
        filter_type = "noun"
    elif "--verbs-only" in sys.argv:
        filter_type = "verb"

    # Verify model is available
    try:
        response = ollama.list()
        models = [m.model for m in response.models]
        if not any(MODEL in m for m in models):
            print(f"ERROR: Model '{MODEL}' not found. Run: ollama pull {MODEL}")
            sys.exit(1)
    except Exception as e:
        print(f"ERROR: Cannot connect to Ollama: {e}\nMake sure Ollama is running.")
        sys.exit(1)

    with open(GRAMMAR_FILE, encoding="utf-8") as f:
        data = json.load(f)

    entries = {
        k: v for k, v in data.items()
        if v.get("type") in ("verb", "noun") and (filter_type is None or v.get("type") == filter_type)
    }

    total = len(entries)
    verb_count = sum(1 for v in entries.values() if v.get("type") == "verb")
    noun_count = sum(1 for v in entries.values() if v.get("type") == "noun")
    print(f"Checking {total} entries ({verb_count} verbs, {noun_count} nouns) with {MODEL}...")
    print("Progress saves after every entry — safe to Ctrl+C and resume.\n")

    # Resume: load existing corrections
    if CORRECTIONS_FILE.exists():
        with open(CORRECTIONS_FILE, encoding="utf-8") as f:
            all_corrections = json.load(f)
        already = len(all_corrections)
        print(f"Resuming — {already} entries already checked, skipping them.\n")
    else:
        all_corrections = {}

    checked = 0
    errors_found = 0
    api_errors = 0
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
        print(f"[{checked}/{total} {pct:.1f}%] [{entry_type}] {key}...", end=" ", flush=True)

        result = check_entry(key, entry, entry_type)
        verdict = result.get("verdict", "api_error")
        errors = result.get("errors", [])

        if verdict == "ok":
            print("ok")
            all_corrections[key] = {"verdict": "ok", "errors": [], "type": entry_type}
        elif verdict == "errors_found" and errors:
            errors_found += 1
            print(f"ERRORS ({len(errors)})")
            for err in errors:
                line = f"  {err.get('field')}: '{err.get('current')}' → '{err.get('correct')}' | {err.get('reason')}"
                print(line)
                report_lines.append(f"{key} | {line.strip()}")
            all_corrections[key] = {"verdict": "errors_found", "errors": errors, "type": entry_type}
        else:
            api_errors += 1
            print("API_ERROR")
            all_corrections[key] = {"verdict": "api_error", "errors": [], "type": entry_type}

        # Save after every entry — safe to interrupt and resume
        with open(CORRECTIONS_FILE, "w", encoding="utf-8") as f:
            json.dump(all_corrections, f, ensure_ascii=False, indent=2)

    # Write report
    with open(REPORT_FILE, "w", encoding="utf-8") as f:
        f.write(f"LLM Grammar Audit — {MODEL}\n")
        f.write(f"Total: {total} | Errors: {errors_found} | API errors: {api_errors}\n")
        f.write("=" * 80 + "\n\n")
        f.write("\n".join(report_lines) if report_lines else "No errors found.")

    print(f"\n{'='*60}")
    print(f"Done. {total} entries checked.")
    print(f"Entries with errors: {errors_found}")
    print(f"API errors: {api_errors}")
    print(f"Corrections: {CORRECTIONS_FILE}")
    print(f"Report: {REPORT_FILE}")
    print(f"\nNext: python3 apply_llm_corrections.py --dry-run")


if __name__ == "__main__":
    main()

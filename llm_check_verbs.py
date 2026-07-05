#!/usr/bin/env python3
"""
LLM-based German verb conjugation checker.
Uses Claude API to verify every verb in grammar.json.
Accuracy over speed: each verb gets its own focused prompt.

Usage:
    pip install anthropic
    export ANTHROPIC_API_KEY=your_key
    python3 llm_check_verbs.py

Outputs:
    llm_corrections.json  — machine-readable corrections to apply
    llm_report.txt        — human-readable audit log
"""

import json
import os
import time
import sys
from pathlib import Path

try:
    import anthropic
except ImportError:
    print("ERROR: Run: pip install anthropic")
    sys.exit(1)

GRAMMAR_FILE = Path(__file__).parent / "grammar.json"
CORRECTIONS_FILE = Path(__file__).parent / "llm_corrections.json"
REPORT_FILE = Path(__file__).parent / "llm_report.txt"

# Haiku is fast and cheap but misses subtleties.
# Sonnet is the sweet spot for grammar accuracy.
# Change to "claude-opus-4-7" if you want maximum accuracy and don't mind cost.
MODEL = "claude-sonnet-4-6"

SYSTEM_PROMPT = """You are an expert German linguist and grammar teacher.
Your task is to verify German verb conjugations with absolute precision.

Rules you must apply:
1. PRESENT TENSE — regular verbs: ich→-e, du→-st, er→-t, wir→infinitiv, ihr→-t, Sie→infinitiv
2. SEPARABLE VERBS (e.g. aufmachen, einschätzen): the prefix splits off in conjugated forms and goes to the END. E.g. aufmachen → ich mache auf, du machst auf.
3. INSEPARABLE PREFIXES (be-, ver-, er-, ent-, zer-, miss-, ge-, emp-, hinter-): prefix stays attached. Never split with a space.
4. PARTIZIP II (perfekt_ich field stores ONLY the Partizip II, no auxiliary):
   - Regular verb: ge- + stem + -t (spielen→gespielt)
   - Irregular verb: ge- + stem + -en (fahren→gefahren)
   - Inseparable prefix verb: NO ge- prefix (besuchen→besucht, verstehen→verstanden)
   - Separable verb with non-ieren base: ge- goes BETWEEN prefix and stem (aufmachen→aufgemacht)
   - -ieren verbs: NO ge-, just stem + -t (präsentieren→präsentiert, anprobieren→anprobiert)
5. STEMS ENDING IN -t OR -d: add epenthetic -e- before -st/-t endings (antworten→antwortest/antwortet)
6. STRONG/IRREGULAR VERBS: stem vowel change in du/er forms (fahren→fährst/fährt, geben→gibst/gibt)
7. -ern VERBS (rudern, liefern): ich drops -n (rudere, liefere) — NOT rudert/rudere without the e
8. -eln VERBS (segeln, zweifeln): ich contracts (segle, zweifle) — drop the -e- before -l

Respond with ONLY valid JSON in this exact format:
{
  "verdict": "ok" | "errors_found",
  "errors": [
    {
      "field": "ich" | "du" | "er/sie/es" | "wir" | "ihr" | "Sie" | "perfekt_ich",
      "current": "the wrong value",
      "correct": "the right value",
      "reason": "one-line explanation"
    }
  ]
}
If no errors, return {"verdict": "ok", "errors": []}
"""

def check_verb(client: anthropic.Anthropic, infinitiv: str, entry: dict) -> dict:
    """Ask Claude to verify one verb's conjugations. Returns parsed JSON response."""
    # Build a compact representation of the verb entry
    fields = {k: v for k, v in entry.items() if k != "type"}
    verb_text = f"Infinitive: {infinitiv}\n"
    for field, value in fields.items():
        verb_text += f"{field}: {value}\n"

    prompt = f"Verify the following German verb conjugations for errors:\n\n{verb_text.strip()}"

    for attempt in range(3):
        try:
            response = client.messages.create(
                model=MODEL,
                max_tokens=512,
                system=SYSTEM_PROMPT,
                messages=[{"role": "user", "content": prompt}],
                temperature=0,  # deterministic — accuracy over creativity
            )
            raw = response.content[0].text.strip()
            # Strip markdown code fences if present
            if raw.startswith("```"):
                raw = raw.split("```")[1]
                if raw.startswith("json"):
                    raw = raw[4:]
            return json.loads(raw)
        except json.JSONDecodeError as e:
            print(f"  [WARN] JSON parse error for {infinitiv} (attempt {attempt+1}): {e}")
            time.sleep(1)
        except anthropic.RateLimitError:
            wait = 30 * (attempt + 1)
            print(f"  [RATE LIMIT] Waiting {wait}s...")
            time.sleep(wait)
        except Exception as e:
            print(f"  [ERROR] {infinitiv}: {e}")
            time.sleep(2)

    return {"verdict": "error", "errors": [], "raw": "failed after 3 attempts"}


def main():
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        print("ERROR: Set ANTHROPIC_API_KEY environment variable")
        sys.exit(1)

    client = anthropic.Anthropic(api_key=api_key)

    with open(GRAMMAR_FILE, encoding="utf-8") as f:
        data = json.load(f)

    verbs = {k: v for k, v in data.items() if v.get("type") == "verb"}
    total = len(verbs)
    print(f"Checking {total} verbs with {MODEL}...\n")

    all_corrections = {}   # infinitiv → list of error dicts
    report_lines = []
    checked = 0
    errors_found = 0
    api_errors = 0

    # Resume support: load existing corrections so we can skip already-checked verbs
    if CORRECTIONS_FILE.exists():
        with open(CORRECTIONS_FILE, encoding="utf-8") as f:
            all_corrections = json.load(f)
        already_done = set(all_corrections.keys())
        # Mark "ok" entries too so we can skip them
        # We store {"verdict": "ok"} for clean verbs
        print(f"Resuming — {len(already_done)} verbs already checked, skipping them.\n")
    else:
        already_done = set()

    for infinitiv, entry in verbs.items():
        if infinitiv in already_done:
            checked += 1
            if all_corrections.get(infinitiv, {}).get("verdict") == "errors_found":
                errors_found += 1
            continue

        checked += 1
        pct = checked / total * 100
        print(f"[{checked}/{total} {pct:.1f}%] {infinitiv}...", end=" ", flush=True)

        result = check_verb(client, infinitiv, entry)

        verdict = result.get("verdict", "error")
        errors = result.get("errors", [])

        if verdict == "ok":
            print("ok")
            all_corrections[infinitiv] = {"verdict": "ok", "errors": []}
        elif verdict == "errors_found" and errors:
            errors_found += 1
            print(f"ERRORS ({len(errors)})")
            for err in errors:
                line = f"  {err.get('field')}: '{err.get('current')}' → '{err.get('correct')}' | {err.get('reason')}"
                print(line)
                report_lines.append(f"{infinitiv} | {line.strip()}")
            all_corrections[infinitiv] = {"verdict": "errors_found", "errors": errors}
        else:
            api_errors += 1
            print(f"API_ERROR: {result}")
            all_corrections[infinitiv] = {"verdict": "api_error", "errors": [], "raw": str(result)}

        # Save progress after every verb (so we can resume if interrupted)
        with open(CORRECTIONS_FILE, "w", encoding="utf-8") as f:
            json.dump(all_corrections, f, ensure_ascii=False, indent=2)

        # Polite pacing: ~1 req/sec to avoid rate limits without sacrificing accuracy
        time.sleep(0.5)

    # Write human-readable report
    with open(REPORT_FILE, "w", encoding="utf-8") as f:
        f.write(f"LLM Verb Audit — {MODEL}\n")
        f.write(f"Total verbs: {total} | Errors found: {errors_found} | API errors: {api_errors}\n")
        f.write("=" * 80 + "\n\n")
        if report_lines:
            for line in report_lines:
                f.write(line + "\n")
        else:
            f.write("No errors found.\n")

    print(f"\n{'='*60}")
    print(f"Done. {total} verbs checked.")
    print(f"Verbs with errors: {errors_found}")
    print(f"API errors (check manually): {api_errors}")
    print(f"Corrections saved to: {CORRECTIONS_FILE}")
    print(f"Report saved to: {REPORT_FILE}")
    print(f"\nNext step: run apply_llm_corrections.py to patch grammar.json")


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""
Adds vocab_refs field to every sentence in sentences_100k/.

Builds a comprehensive inflected-form → base-vocab-word map using:
  - grammar.json: all present conjugations, Partizip II, plural nouns
  - Derived Präteritum for weak verbs (stem + -te/test/ten/tet)
  - Common adjective declension endings (-e/-en/-em/-er/-es)
  - Exact lemma (base form) for adverbs and unrecognised words

Run: python3 enrich_sentences.py   (~15 seconds)
"""

import json, re
from pathlib import Path

BASE          = Path(__file__).parent
HTML_FILE     = BASE / "index.html"
GRAMMAR_FILE  = BASE / "grammar.json"
SENTENCES_DIR = BASE / "sentences_100k"

STRIP_ARTICLE = re.compile(
    r'^(der|die|das|ein|eine|einen|einem|eines|einer|kein|keine|sich)\s+',
    re.IGNORECASE
)

ADJ_ENDINGS = ['e', 'en', 'em', 'er', 'es']

def strip_article(word: str) -> str:
    return STRIP_ARTICLE.sub('', word).strip()

def get_stem(infinitive: str) -> str:
    """Get verb stem from infinitive (remove -en or -n ending)."""
    inf = infinitive.lower()
    if inf.endswith('eln') or inf.endswith('ern'):
        return inf[:-1]   # wandern → wander
    if inf.endswith('en'):
        return inf[:-2]   # kaufen → kauf
    if inf.endswith('n'):
        return inf[:-1]   # tun → tu
    return inf

def weak_praeteritum_forms(stem: str) -> list[str]:
    """Generate Präteritum forms for weak verbs (stem + te/test/te/ten/tet/ten)."""
    # Add -e- connector if stem ends in t/d/fn/gn/chn/ffn/tm
    connector = 'e' if re.search(r'(t|d|chn|gn|fn|tm)$', stem) else ''
    base = stem + connector + 't'
    return [
        stem + connector + 'te',    # ich
        stem + connector + 'test',  # du
        stem + connector + 'te',    # er
        stem + connector + 'ten',   # wir/Sie
        stem + connector + 'tet',   # ihr
    ]

def load_vocab() -> dict[str, str]:
    """Returns {german_word: category}."""
    html = HTML_FILE.read_text(encoding='utf-8')
    m    = re.search(r'const DATA = (\{.*?\});', html, re.DOTALL)
    data = json.loads(m.group(1))
    return {
        w['german']: cat
        for cat in ('verbs', 'nouns', 'adjectives', 'adverbs')
        for w in data.get(cat, [])
    }

def build_inflection_map(vocab: dict[str, str]) -> dict[str, str]:
    """
    Returns {inflected_form_lower: original_vocab_word}.
    One form can only map to one vocab word (last wins on collision,
    but real collisions are rare).
    """
    grammar: dict = json.loads(GRAMMAR_FILE.read_text(encoding='utf-8'))
    imap: dict[str, str] = {}

    def add(form: str, original: str):
        if form:
            imap[form.lower()] = original

    for german, cat in vocab.items():
        bare = strip_article(german)

        # Always add the bare lemma itself
        add(bare, german)

        if cat == 'verbs':
            entry = grammar.get(german, {})
            stem  = get_stem(bare)

            # Present conjugations from grammar.json
            for field in ('ich', 'du', 'er/sie/es', 'wir', 'ihr', 'Sie'):
                add(entry.get(field, ''), german)

            # Partizip II
            p2 = entry.get('perfekt_ich', '')
            add(p2, german)

            # Infinitive + zu-infinitive token (just the infinitive part)
            add(bare, german)

            # Present participle (-end)
            add(stem + 'end', german)

            # Weak Präteritum (always add — strong verbs will just have extra
            # forms that may not match, harmless)
            for f in weak_praeteritum_forms(stem):
                add(f, german)

            # Separable verb: also add the base without prefix
            # e.g. aufmachen → machen forms (skip — too many false positives)

        elif cat == 'nouns':
            entry = grammar.get(german, {})
            plural = entry.get('plural', '')
            if plural:
                add(strip_article(plural), german)

        elif cat == 'adjectives':
            # Add common declined forms
            for ending in ADJ_ENDINGS:
                add(bare + ending, german)
            # Comparative: schnell → schneller, schnellste
            add(bare + 'er', german)
            add(bare + 'ste', german)
            add(bare + 'sten', german)

        elif cat == 'adverbs':
            add(bare, german)

    return imap


def tokenise(text: str) -> set[str]:
    return set(re.findall(r'[a-zäöüßA-ZÄÖÜ]+', text.lower()))


def main():
    print('Loading vocab...')
    vocab = load_vocab()
    print(f'  {len(vocab):,} words')

    print('Building inflection map...')
    imap = build_inflection_map(vocab)
    print(f'  {len(imap):,} inflected forms → vocab words')

    chunk_files = sorted(SENTENCES_DIR.glob('chunk_*.json'))
    total_sents = 0
    total_refs  = 0
    zero_ref    = 0

    print(f'Enriching {len(chunk_files)} chunks...')
    for chunk_path in chunk_files:
        sentences = json.loads(chunk_path.read_text(encoding='utf-8'))

        for s in sentences:
            tokens = tokenise(s['german'])
            # Collect unique base vocab words matched by any token
            seen: set[str] = set()
            for t in tokens:
                orig = imap.get(t)
                if orig:
                    seen.add(orig)
            refs = list(seen)
            s['vocab_refs'] = refs
            total_refs += len(refs)
            if not refs:
                zero_ref += 1
            total_sents += 1

        chunk_path.write_text(
            json.dumps(sentences, ensure_ascii=False, indent=2),
            encoding='utf-8'
        )

    avg = total_refs / total_sents if total_sents else 0
    print(f'\nDone.')
    print(f'  Sentences:  {total_sents:,}')
    print(f'  Avg refs:   {avg:.1f} vocab words per sentence')
    print(f'  Zero refs:  {zero_ref:,}  ({zero_ref/total_sents*100:.1f}%)')


if __name__ == '__main__':
    main()

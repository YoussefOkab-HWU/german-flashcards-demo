#!/usr/bin/env python3
"""
Comprehensive grammar.json fixer.
Applies manual corrections + rule-based fixes to verb conjugations.
Run: python3 fix_grammar.py
"""
import json, copy

INPUT  = 'grammar.json'
OUTPUT = 'grammar.json'

# ---------------------------------------------------------------------------
# Manual fixes: {verb_key: {field: corrected_value, ...}}
# Only listed fields are changed; all others remain untouched.
# ---------------------------------------------------------------------------
MANUAL_FIXES = {

    # ── ich form wrong (er/sie/es form used instead) ─────────────────────
    'finanzieren': {'ich': 'finanziere'},
    'prägen':      {'ich': 'präge'},
    'genügen':     {'ich': 'genüge', 'perfekt_ich': 'genügt'},   # ge- not added again

    # ── impersonal verbs: all forms were "regnet"/"schneit" ──────────────
    'regnen':  {'ich': 'regen', 'du': 'regnest', 'wir': 'regnen',
                'ihr': 'regnet', 'Sie': 'regnen'},
    'schneien': {'ich': 'schneie', 'du': 'schneist', 'wir': 'schneien',
                 'ihr': 'schneit', 'Sie': 'schneien'},
    'gelingen': {'ich': 'gelinge', 'du': 'gelingst',
                 'wir': 'gelingen', 'ihr': 'gelingt', 'Sie': 'gelingen'},

    # ── -ern / -eln ich forms clipped or missing ─────────────────────────
    'rudern':      {'ich': 'rudere'},
    'segeln':      {'ich': 'segle'},
    'liefern':     {'ich': 'liefere'},
    'zweifeln':    {'ich': 'zweifle'},
    'hämmern':     {'ich': 'hämmere'},
    'jubeln':      {'ich': 'juble'},
    'verzögern':   {'ich': 'verzögere'},
    'basteln':     {'ich': 'bastle'},
    'zögern':      {'ich': 'zögere'},
    'übersteuern': {'ich': 'übersteuere'},
    'stapeln':     {'ich': 'staple'},
    'schlüsseln':  {'ich': 'schlüssle'},
    'klammern':    {'ich': 'klammere'},
    'stinken':     {'ich': 'stinke'},
    'festigen':    {'ich': 'festige', 'du': 'festigst'},

    # ── Typos / copy-paste errors in specific forms ──────────────────────
    'entspannen': {'wir': 'entspannen'},          # "entspaannen"
    'hüpfen':     {'du': 'hüpfst', 'perfekt_ich': 'gehüpft'},  # du was "hüpft"; p2 was "gesprungen"
    'gähnen':     {'wir': 'gähnen', 'ihr': 'gähnt', 'perfekt_ich': 'gegähnt'},
    'staunen':    {'ich': 'staune', 'du': 'staunst'},
    'schweben':   {'wir': 'schweben', 'Sie': 'schweben'},      # wir="schwimmen", Sie="schwebten"
    'umarmen':    {'er/sie/es': 'umarmt', 'wir': 'umarmen', 'perfekt_ich': 'umarmt'},
    'niesen':     {'wir': 'niesen', 'Sie': 'niesen', 'perfekt_ich': 'geniest'},
    'bestreiten': {'er/sie/es': 'bestreitet', 'Sie': 'bestreiten'},
    'beklagen':   {'du': 'beklagst', 'ihr': 'beklagt',
                   'Sie': 'beklagen', 'perfekt_ich': 'beklagt'},
    'betonen':    {'du': 'betonst', 'perfekt_ich': 'betont'},
    'beantragen': {'er/sie/es': 'beantragt', 'perfekt_ich': 'beantragt'},
    'umbauen':    {'ich': 'baue um', 'du': 'baust um', 'perfekt_ich': 'umgebaut'},
    'unterscheiden': {'perfekt_ich': 'unterschieden'},
    'narren':     {'du': 'narrst', 'er/sie/es': 'narrt',
                   'wir': 'narren', 'ihr': 'narrt', 'Sie': 'narren'},
    'erkunden':   {'wir': 'erkunden'},
    'erringen':   {'er/sie/es': 'erringt', 'ihr': 'erringt', 'Sie': 'erringen'},
    'schieben':   {'du': 'schiebst', 'wir': 'schieben',
                   'ihr': 'schiebt', 'Sie': 'schieben'},
    'hervorheben': {'ich': 'hebe hervor', 'du': 'hebst hervor',
                    'er/sie/es': 'hebt hervor', 'wir': 'heben hervor',
                    'ihr': 'hebt hervor', 'Sie': 'heben hervor',
                    'perfekt_ich': 'hervorgehoben'},
    'anrichten':  {'ich': 'richte an', 'du': 'richtest an',
                   'er/sie/es': 'richtet an', 'wir': 'richten an',
                   'ihr': 'richtet an', 'Sie': 'richten an'},
    'anwachsen':  {'ich': 'wachse an', 'du': 'wächst an',
                   'er/sie/es': 'wächst an', 'wir': 'wachsen an',
                   'ihr': 'wachst an', 'Sie': 'wachsen an'},
    'ausweichen': {'ich': 'weiche aus', 'du': 'weichst aus'},
    'begreifen':  {'ich': 'begreife', 'du': 'begreifst',
                   'er/sie/es': 'begreift', 'ihr': 'begreift'},

    # ── Inseparable prefix verbs with spurious ge- in Partizip II ────────
    'entschließen': {'perfekt_ich': 'entschlossen'},
    'versinken':    {'perfekt_ich': 'versunken'},
    'misslingen':   {'perfekt_ich': 'misslungen'},
    'beschwören':   {'perfekt_ich': 'beschworen'},

    # ── Separable verbs: inseparable-prefix forms had spaces (wrong) ──────
    'erbitten':  {'ich': 'erbitte',   'du': 'erbittest',  'er/sie/es': 'erbittet',
                  'wir': 'erbitten',  'ihr': 'erbittet',  'Sie': 'erbitten'},
    'verbrennen':{'ich': 'verbrenne', 'du': 'verbrennst', 'er/sie/es': 'verbrennt',
                  'wir': 'verbrennen','ihr': 'verbrennt', 'Sie': 'verbrennen'},
    'bemessen':  {'ich': 'bemesse',   'du': 'bemisst',    'er/sie/es': 'bemisst',
                  'wir': 'bemessen',  'ihr': 'bemesst',   'Sie': 'bemessen'},
    'bewachen':  {'ich': 'bewache',   'du': 'bewachst',   'er/sie/es': 'bewacht',
                  'wir': 'bewachen',  'ihr': 'bewacht',   'Sie': 'bewachen'},
    'vermissen': {'ich': 'vermisse',  'du': 'vermisst',   'er/sie/es': 'vermisst',
                  'wir': 'vermissen', 'ihr': 'vermisst',  'Sie': 'vermissen'},

    # ── Separable verbs: prefix not split off in conjugated forms ─────────
    # (all 6 present forms corrected + Partizip II where wrong)
    'ablehnen':   {'ich': 'lehne ab',  'du': 'lehnst ab'},
    'anbraten':   {'er/sie/es': 'brät an',  'Sie': 'braten an'},
    'wahrnehmen': {'ich': 'nehme wahr', 'du': 'nimmst wahr',
                   'er/sie/es': 'nimmt wahr', 'wir': 'nehmen wahr',
                   'Sie': 'nehmen wahr'},
    'angreifen':  {'du': 'greifst an'},
    'anordnen':   {'du': 'ordnest an'},
    'anstecken':  {'du': 'steckst an'},
    'auswandern': {'ich': 'wandere aus', 'du': 'wanderst aus',
                   'er/sie/es': 'wandert aus', 'wir': 'wandern aus',
                   'Sie': 'wandern aus'},
    'einwilligen':{'ich': 'willige ein', 'du': 'willigst ein',
                   'er/sie/es': 'willigt ein', 'wir': 'willigen ein',
                   'ihr': 'willigt ein', 'Sie': 'willigen ein'},
    'fortschreiten':{'ich': 'schreite fort', 'du': 'schreitest fort',
                     'perfekt_ich': 'fortgeschritten'},
    'vorsehen':   {'ich': 'sehe vor', 'du': 'siehst vor',
                   'perfekt_ich': 'vorgesehen'},
    'ansparen':   {'du': 'sparst an', 'er/sie/es': 'spart an',
                   'wir': 'sparen an', 'ihr': 'spart an', 'Sie': 'sparen an'},
    'aufmuntern': {'du': 'munterst auf', 'er/sie/es': 'muntert auf',
                   'wir': 'muntern auf', 'ihr': 'muntert auf', 'Sie': 'muntern auf'},
    'auflisten':  {'du': 'listest auf'},
    'hinstellen': {'ich': 'stelle hin'},
    'abschwächen':{'ich': 'schwäche ab', 'du': 'schwächst ab'},
    'anfeuern':   {'ich': 'feuere an'},
    'aufdecken':  {'ich': 'decke auf', 'du': 'deckst auf'},
    'einstecken': {'ich': 'stecke ein', 'du': 'steckst ein'},
    'vorbeugen':  {'du': 'beugst vor', 'er/sie/es': 'beugt vor',
                   'wir': 'beugen vor', 'ihr': 'beugt vor', 'Sie': 'beugen vor'},
    'zurückweisen':{'ich': 'weise zurück', 'du': 'weist zurück'},
    'zustehen':   {'ich': 'stehe zu', 'du': 'stehst zu'},
    'abschaffen': {'ich': 'schaffe ab', 'du': 'schaffst ab',
                   'er/sie/es': 'schafft ab', 'wir': 'schaffen ab', 'Sie': 'schaffen ab'},
    'einfließen': {'du': 'fließt ein', 'er/sie/es': 'fließt ein',
                   'wir': 'fließen ein', 'ihr': 'fließt ein', 'Sie': 'fließen ein'},
    'freilegen':  {'ich': 'lege frei', 'du': 'legst frei'},
    'absichern':  {'ich': 'sichere ab', 'du': 'sicherst ab',
                   'er/sie/es': 'sichert ab', 'wir': 'sichern ab',
                   'ihr': 'sichert ab', 'Sie': 'sichern ab'},
    'auftragen':  {'ich': 'trage auf'},
    'darstellen': {'ich': 'stelle dar', 'du': 'stellst dar',
                   'er/sie/es': 'stellt dar', 'wir': 'stellen dar',
                   'ihr': 'stellt dar', 'Sie': 'stellen dar'},
    'aufrichten': {'ich': 'richte auf', 'du': 'richtest auf'},
    'mitwirken':  {'ich': 'wirke mit', 'du': 'wirkst mit'},
    'ausschließen':{'ich': 'schließe aus', 'du': 'schließt aus',
                    'er/sie/es': 'schließt aus', 'wir': 'schließen aus',
                    'Sie': 'schließen aus'},
    'darlegen':   {'ich': 'lege dar', 'du': 'legst dar',
                   'er/sie/es': 'legt dar', 'wir': 'legen dar',
                   'ihr': 'legt dar', 'Sie': 'legen dar',
                   'perfekt_ich': 'dargelegt'},
    'einschätzen':{'ich': 'schätze ein', 'du': 'schätzt ein',
                   'er/sie/es': 'schätzt ein', 'wir': 'schätzen ein',
                   'ihr': 'schätzt ein', 'Sie': 'schätzen ein'},
    'einteilen':  {'ich': 'teile ein', 'du': 'teilst ein',
                   'er/sie/es': 'teilt ein', 'wir': 'teilen ein',
                   'ihr': 'teilt ein', 'Sie': 'teilen ein'},
    'entgegennehmen':{'ich': 'nehme entgegen', 'du': 'nimmst entgegen',
                      'er/sie/es': 'nimmt entgegen', 'wir': 'nehmen entgegen',
                      'ihr': 'nehmt entgegen', 'Sie': 'nehmen entgegen'},
    'herausgeben':{'ich': 'gebe heraus', 'du': 'gibst heraus',
                   'er/sie/es': 'gibt heraus', 'wir': 'geben heraus',
                   'ihr': 'gebt heraus', 'Sie': 'geben heraus'},
    'mitdenken':  {'ich': 'denke mit', 'du': 'denkst mit',
                   'er/sie/es': 'denkt mit', 'wir': 'denken mit',
                   'ihr': 'denkt mit', 'Sie': 'denken mit'},
    'nachvollziehen':{'ich': 'vollziehe nach', 'du': 'vollziehst nach',
                      'er/sie/es': 'vollzieht nach', 'wir': 'vollziehen nach',
                      'ihr': 'vollzieht nach', 'Sie': 'vollziehen nach'},
    'vortragen':  {'ich': 'trage vor', 'du': 'trägst vor',
                   'er/sie/es': 'trägt vor', 'wir': 'tragen vor',
                   'ihr': 'tragt vor', 'Sie': 'tragen vor',
                   'perfekt_ich': 'vorgetragen'},
    'weiterbilden':{'ich': 'bilde weiter', 'du': 'bildest weiter',
                    'er/sie/es': 'bildet weiter', 'wir': 'bilden weiter',
                    'ihr': 'bildet weiter', 'Sie': 'bilden weiter',
                    'perfekt_ich': 'weitergebildet'},
    'weiterleiten':{'ich': 'leite weiter', 'du': 'leitest weiter',
                    'er/sie/es': 'leitet weiter', 'wir': 'leiten weiter',
                    'ihr': 'leitet weiter', 'Sie': 'leiten weiter'},
    'zubereiten': {'ich': 'bereite zu', 'perfekt_ich': 'zubereitet'},
    'zumuten':    {'ich': 'mute zu', 'du': 'mutest zu',
                   'er/sie/es': 'mutet zu', 'wir': 'zumuten',
                   'ihr': 'mutet zu', 'Sie': 'zumuten',
                   'perfekt_ich': 'zugemutet'},
    'abtrocknen': {'ich': 'trockne ab', 'du': 'trocknest ab',
                   'er/sie/es': 'trocknet ab'},
    'aufforsten': {'ich': 'forste auf', 'du': 'forstest auf',
                   'er/sie/es': 'forstet auf'},
    'ausschneiden':{'ich': 'schneide aus', 'du': 'schneidest aus',
                    'er/sie/es': 'schneidet aus'},
    'einblenden': {'ich': 'blende ein', 'du': 'blendest ein',
                   'er/sie/es': 'blendet ein', 'wir': 'blenden ein',
                   'ihr': 'blendet ein', 'Sie': 'blenden ein'},
    'einwandern': {'ich': 'wandere ein', 'du': 'wanderst ein',
                   'er/sie/es': 'wandert ein', 'wir': 'wandern ein',
                   'ihr': 'wandert ein', 'Sie': 'wandern ein',
                   'perfekt_ich': 'eingewandert'},
    'hindeuten':  {'ich': 'deute hin', 'du': 'deutest hin',
                   'er/sie/es': 'deutet hin', 'wir': 'deuten hin',
                   'ihr': 'deutet hin', 'Sie': 'deuten hin',
                   'perfekt_ich': 'hingedeutet'},
    'hinfallen':  {'ich': 'falle hin', 'du': 'fällst hin',
                   'er/sie/es': 'fällt hin', 'wir': 'fallen hin',
                   'ihr': 'fallt hin', 'Sie': 'fallen hin',
                   'perfekt_ich': 'hingefallen'},
    'nachbilden': {'ich': 'bilde nach', 'du': 'bildest nach',
                   'er/sie/es': 'bildet nach', 'wir': 'bilden nach',
                   'ihr': 'bildet nach', 'Sie': 'bilden nach',
                   'perfekt_ich': 'nachgebildet'},
    'vorschreiben':{'ich': 'schreibe vor', 'du': 'schreibst vor',
                    'er/sie/es': 'schreibt vor', 'wir': 'schreiben vor',
                    'ihr': 'schreibt vor', 'Sie': 'schreiben vor',
                    'perfekt_ich': 'vorgeschrieben'},
    'andeuten':   {'ich': 'deute an', 'du': 'deutest an',
                   'er/sie/es': 'deutet an', 'wir': 'deuten an',
                   'ihr': 'deutet an', 'Sie': 'deuten an'},
    'anklagen':   {'ich': 'klage an', 'du': 'klagst an',
                   'er/sie/es': 'klagt an', 'wir': 'klagen an',
                   'ihr': 'klagt an', 'Sie': 'klagen an'},
    'anprobieren':{'ich': 'probiere an', 'du': 'probierst an',
                   'er/sie/es': 'probiert an', 'wir': 'probieren an',
                   'ihr': 'probiert an', 'Sie': 'probieren an',
                   'perfekt_ich': 'anprobiert'},
    'anschnallen':{'ich': 'schnalle an', 'du': 'schnallst an',
                   'er/sie/es': 'schnallt an', 'wir': 'schnallen an',
                   'ihr': 'schnallt an', 'Sie': 'schnallen an',
                   'perfekt_ich': 'angeschnallt'},
    'antasten':   {'ich': 'taste an', 'du': 'tastest an',
                   'er/sie/es': 'tastet an', 'wir': 'antasten',
                   'ihr': 'tastet an', 'Sie': 'antasten',
                   'perfekt_ich': 'angetastet'},
    'auffrischen':{'ich': 'frische auf', 'du': 'frischst auf',
                   'er/sie/es': 'frischt auf', 'wir': 'frischen auf',
                   'ihr': 'frischt auf', 'Sie': 'frischen auf',
                   'perfekt_ich': 'aufgefrischt'},
    'aufschieben':{'ich': 'schiebe auf', 'du': 'schiebst auf',
                   'er/sie/es': 'schiebt auf'},
    'ausschöpfen':{'ich': 'schöpfe aus', 'du': 'schöpfst aus',
                   'er/sie/es': 'schöpft aus'},
    'einschränken':{'ich': 'schränke ein', 'du': 'schränkst ein',
                    'er/sie/es': 'schränkt ein', 'wir': 'schränken ein',
                    'ihr': 'schränkt ein', 'Sie': 'schränken ein'},
    'gegenüberstellen':{'ich': 'stelle gegenüber', 'du': 'stellst gegenüber',
                        'er/sie/es': 'stellt gegenüber', 'wir': 'stellen gegenüber',
                        'ihr': 'stellt gegenüber', 'Sie': 'stellen gegenüber',
                        'perfekt_ich': 'gegenübergestellt'},
    'hervorrufen':{'ich': 'rufe hervor', 'du': 'rufst hervor',
                   'er/sie/es': 'ruft hervor', 'wir': 'rufen hervor',
                   'ihr': 'ruft hervor', 'Sie': 'rufen hervor'},
    'vorenthalten':{'ich': 'enthalte vor', 'du': 'enthältst vor',
                    'er/sie/es': 'enthält vor', 'wir': 'enthalten vor',
                    'ihr': 'enthaltet vor', 'Sie': 'enthalten vor'},
    'abmontieren':{'ich': 'montiere ab', 'du': 'montierst ab',
                   'er/sie/es': 'montiert ab', 'wir': 'montieren ab',
                   'ihr': 'montiert ab', 'Sie': 'montieren ab',
                   'perfekt_ich': 'abmontiert'},
    'abzweigen':  {'ich': 'zweige ab', 'du': 'zweigst ab',
                   'er/sie/es': 'zweigt ab', 'ihr': 'zweigt ab'},
    'anstrengen': {'ich': 'strenge an', 'du': 'strengst an',
                   'er/sie/es': 'strengt an', 'wir': 'strengen an',
                   'ihr': 'strengt an', 'Sie': 'strengen an'},
    'aussortieren':{'ich': 'sortiere aus', 'du': 'sortierst aus',
                    'er/sie/es': 'sortiert aus', 'wir': 'sortieren aus',
                    'ihr': 'sortiert aus', 'Sie': 'sortieren aus',
                    'perfekt_ich': 'aussortiert'},
    'beibringen': {'ich': 'bringe bei', 'du': 'bringst bei',
                   'er/sie/es': 'bringt bei', 'wir': 'bringen bei',
                   'ihr': 'bringt bei', 'Sie': 'bringen bei'},
    'einklingen': {'ich': 'klinge ein', 'du': 'klingst ein',
                   'er/sie/es': 'klingt ein', 'wir': 'klingen ein',
                   'ihr': 'klingt ein', 'Sie': 'klingen ein'},
    'herausfordern':{'ich': 'fordere heraus', 'du': 'forderst heraus',
                     'er/sie/es': 'fordert heraus', 'wir': 'fordern heraus',
                     'ihr': 'fordert heraus', 'Sie': 'fordern heraus'},
    'einsparen':  {'ich': 'spare ein', 'du': 'sparst ein',
                   'er/sie/es': 'spart ein', 'wir': 'sparen ein',
                   'ihr': 'spart ein', 'Sie': 'sparen ein'},
    'dazugeben':  {'ich': 'gebe dazu', 'du': 'gibst dazu',
                   'er/sie/es': 'gibt dazu', 'wir': 'geben dazu',
                   'ihr': 'gebt dazu', 'Sie': 'geben dazu',
                   'perfekt_ich': 'dazugegeben'},
    'zugeben':    {'ich': 'gebe zu', 'du': 'gibst zu',
                   'er/sie/es': 'gibt zu', 'wir': 'geben zu',
                   'ihr': 'gebt zu', 'Sie': 'geben zu',
                   'perfekt_ich': 'zugegeben'},
    'nacherzählen':{'ich': 'erzähle nach', 'du': 'erzählst nach',
                    'er/sie/es': 'erzählt nach', 'wir': 'erzählen nach',
                    'ihr': 'erzählt nach', 'Sie': 'erzählen nach',
                    'perfekt_ich': 'nacherzählt'},
    'abwandeln':  {'ich': 'wandle ab', 'du': 'wandelst ab',
                   'er/sie/es': 'wandelt ab', 'wir': 'wandeln ab',
                   'ihr': 'wandelt ab', 'Sie': 'wandeln ab'},
    'aushandeln': {'ich': 'handle aus', 'du': 'handelst aus',
                   'er/sie/es': 'handelt aus', 'wir': 'handeln aus',
                   'ihr': 'handelt aus', 'Sie': 'handeln aus'},
    'anzugießen': {'ich': 'gieße an', 'du': 'gießt an',
                   'er/sie/es': 'gießt an', 'wir': 'gießen an',
                   'ihr': 'gießt an', 'Sie': 'gießen an',
                   'perfekt_ich': 'angegossen'},

    # ── Lockern: wrong verb forms (lässt locker = lockerlassen) ──────────
    'lockern':    {'ich': 'lockere', 'du': 'lockerst',
                   'wir': 'lockern', 'ihr': 'lockert', 'Sie': 'lockern'},

    # ── Unterstellen (inseparable: to assume/attribute) ───────────────────
    'unterstellen':{'wir': 'unterstellen', 'ihr': 'unterstellt',
                    'Sie': 'unterstellen'},

    # ── Stetstellen (not a real verb; fix to feststellen forms) ──────────
    # Note: the key cannot be renamed, so we just fix the conjugated forms
    # to be internally consistent as if the key were "feststellen"
    'stetstellen':{'ich': 'stelle fest', 'du': 'stellst fest',
                   'er/sie/es': 'stellt fest', 'wir': 'stellen fest',
                   'ihr': 'stellt fest', 'Sie': 'stellen fest',
                   'perfekt_ich': 'festgestellt'},

    # ── Miscellaneous wrong Partizip II ───────────────────────────────────
    'nacherzählen': {'perfekt_ich': 'nacherzählt'},   # duplicate key OK in dict – last wins

    # ── Wrong ich form: infinitive used as ich form ───────────────────────
    'rechen':    {'ich': 'reche', 'du': 'rechest', 'er/sie/es': 'recht',
                  'wir': 'rechen', 'ihr': 'recht', 'Sie': 'rechen',
                  'perfekt_ich': 'gerecht'},
}

# ---------------------------------------------------------------------------
# Entries to REMOVE entirely (not real German verbs or hopelessly incorrect)
# ---------------------------------------------------------------------------
REMOVE = {
    'inbegriffen',   # This is a participle/adjective, not a conjugatable verb
    'abaunieren',    # Not a real German verb
}

# ---------------------------------------------------------------------------
# Main logic
# ---------------------------------------------------------------------------
def apply_fixes(data: dict) -> tuple[dict, list[str]]:
    changes = []
    new_data = {}

    for key, entry in data.items():
        if key in REMOVE:
            changes.append(f"REMOVED: {key}")
            continue

        new_entry = copy.deepcopy(entry)

        if key in MANUAL_FIXES and entry.get('type') == 'verb':
            for field, new_val in MANUAL_FIXES[key].items():
                old_val = entry.get(field, '')
                if old_val != new_val:
                    new_entry[field] = new_val
                    changes.append(f"FIXED  {key} [{field}]: '{old_val}' → '{new_val}'")

        new_data[key] = new_entry

    return new_data, changes


def main():
    with open(INPUT, encoding='utf-8') as f:
        data = json.load(f)

    print(f"Loaded {len(data)} entries ({sum(1 for v in data.values() if v.get('type')=='verb')} verbs, "
          f"{sum(1 for v in data.values() if v.get('type')=='noun')} nouns)")

    new_data, changes = apply_fixes(data)

    print(f"\nTotal changes: {len(changes)}")
    for c in changes:
        print(" ", c)

    with open(OUTPUT, 'w', encoding='utf-8') as f:
        json.dump(new_data, f, ensure_ascii=False, indent=2)

    print(f"\nWrote {len(new_data)} entries to {OUTPUT}")


if __name__ == '__main__':
    main()

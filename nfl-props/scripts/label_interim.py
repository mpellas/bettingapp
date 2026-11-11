"""Post-process a single-week track summary (2026-10-24, Tester1/Tester2): a single week is never a prereg verdict.
Sets decision_this_week_only.label = INTERIM, keeps the raw week-only label in label_raw_week_only. Labels only:
scores untouched. Runs AFTER `python -m nflprops.track week` (src/nflprops/track.py is hash-pinned by the prereg,
so it is not edited). PASS/FAIL only comes from the pooled `track final --weeks 5-18`.
Usage: python scripts/label_interim.py data/track/2026_wk06.summary.json [...]"""
import json, sys
INTERIM = 'INTERIM (weekly number only; prereg verdict is weeks 5-18 pooled via track final)'
NOTE = 'Single-week label set by scripts/label_interim.py: a single week is not a prereg verdict. Numbers unchanged.'

def relabel(d):
    x = d.get('decision_this_week_only')
    if not isinstance(x, dict) or 'label' not in x: return d
    if not str(x['label']).startswith('INTERIM'): x['label_raw_week_only'] = x['label']
    x['label'] = INTERIM; x['label_note'] = NOTE
    return d

if __name__ == '__main__':
    for p in sys.argv[1:]:
        d = relabel(json.load(open(p))); json.dump(d, open(p, 'w'), indent=1); print('INTERIM label:', p)

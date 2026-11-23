"""Shadow grading for the extra NHL paper models. Data only, off the real card.

Rebuilt each time extra_markets/grade_extra_nhl.py runs (hooked at the end).
Uses frozen models in models_extra/models/ plus already-captured DK prices.
Does not invent prices, does not write picks/, does not touch the SOG card.
"""
import os, sys, json, math
import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
os.chdir(ROOT)
from common import MOD, SHADOW, BAND_FLOOR, in_band, am2p, units, summarize_bets


def _load_picks(name):
    p = os.path.join(SHADOW, f'{name}_oos_picks.csv')
    if not os.path.exists(p):
        return None
    return pd.read_csv(p)


def _fmt(s):
    if not s or not s.get('n'):
        return f"{s.get('label','')} n=0"
    return (f"{s['label']}: {s['wins']}-{s['losses']}-{s['pushes']} "
            f"({s['hit_rate']:.1%} of decided) {s['units']:+.2f}u ROI {s['roi']:.1%} "
            f"vs BE {s['avg_breakeven']:.1%} n={s['n']}")


def run():
    os.makedirs(SHADOW, exist_ok=True)
    lines = []
    ready = os.path.exists(os.path.join(MOD, 'points.txt'))
    if not ready:
        print('shadow models: not trained yet')
        return
    cumulative = []
    for name in ('points', 'saves'):
        df = _load_picks(name)
        if df is None or not len(df) or 'pick' not in df.columns:
            lines.append(f'{name}: no shadow picks yet')
            continue
        taken = df[df.pick.notna() & df.pick_result.isin(['win', 'loss', 'push', 'PENDING'])].copy()
        if 'pick_price' not in taken.columns:
            lines.append(f'{name}: picks file missing prices')
            continue
        taken['in_band'] = taken.pick_price.map(in_band)
        graded = taken[taken.pick_result.isin(['win', 'loss', 'push'])]
        pending = int((taken.pick_result == 'PENDING').sum()) if 'PENDING' in set(taken.pick_result) else 0
        alls = summarize_bets(graded.rename(columns={'pick_price': 'price_D', 'pick_result': 'result'}),
                              label=f'{name} shadow all')
        inn = summarize_bets(graded[graded.in_band].rename(columns={'pick_price': 'price_D', 'pick_result': 'result'}),
                             label=f'{name} shadow in-band')
        lines.append(_fmt(alls) + (f'; pending {pending}' if pending else ''))
        lines.append(_fmt(inn))
        # off-card until ~100 graded in-band sides
        n_band = int(inn.get('n') or 0)
        lines.append(f'{name}: {"still off the real card" if n_band < 100 else "reached 100 in-band sides — review before promoting"} ({n_band} in-band graded)')
        cumulative.append({'market': name, **alls, 'in_band_n': n_band, **{f'band_{k}': v for k, v in inn.items()}})
    # puckline: outcome-only until prices exist
    pl = os.path.join(MOD, 'puckline_oos_pred.pkl')
    gl_csv = os.path.join(ROOT, 'extra_markets', 'graded', 'nhl_puckline.csv')
    if os.path.exists(gl_csv):
        g = pd.read_csv(gl_csv)
        n = len(g)
        ng = int(g.result.isin(['win', 'loss', 'push']).sum()) if n else 0
        lines.append(f'puckline captured sides: {n}, graded {ng} (shadow model join once prices + predictions overlap)')
    elif os.path.exists(pl):
        lines.append('puckline: model trained; no captured DK prices graded yet (capture started 2026-11-22)')
    else:
        lines.append('puckline: not trained yet')
    if cumulative:
        pd.DataFrame(cumulative).to_csv(os.path.join(SHADOW, 'summary.csv'), index=False)
    msg = 'shadow models: ' + ' | '.join(lines)
    print(msg)
    open(os.path.join(SHADOW, 'last_run.txt'), 'w').write(msg + '\n')


if __name__ == '__main__':
    run()

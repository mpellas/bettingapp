"""Walk-forward backtest: refit each Monday-ish (per season week) on games before kickoff of that week,
compare to closing lines from CFBD /lines (prefer DraftKings, else consensus/other)."""
import json, sys, csv, datetime as dt, numpy as np
from model import *
PREF = ['DraftKings', 'ESPN Bet', 'Bovada', 'consensus']
def closing(y):
    out = {}
    for L in json.load(open(f'{D}/lines_{y}.json')):
        by = {l['provider']: l for l in L['lines']}
        for pv in PREF + list(by):
            l = by.get(pv)
            if l and l.get('spread') is not None:
                out[L['id']] = (l['spread'], l.get('overUnder'), pv); break
    return out
def run(years, p=P, out=None, quiet=False):
    games = load_games([min(years) - 2, min(years) - 1] + years); rows = []
    for y in years:
        cl = closing(y)
        weeks = sorted({(g['seasonType'], g['week']) for g in games if g['season'] == y})
        for st, wk in weeks:
            wg = [g for g in games if g['season'] == y and g['seasonType'] == st and g['week'] == wk and g['completed'] and g['id'] in cl]
            if not wg: continue
            m = fit(games, min(g['_t'] for g in wg) - dt.timedelta(hours=6), p)
            for g in wg:
                pr = predict(m, g['homeTeam'], g['awayTeam'], g['neutralSite'])
                if pr is None: continue
                sp, ou, pv = cl[g['id']]
                lv = sorted([level(g['homeConference'], g['homeClassification'], g['homeTeam']), level(g['awayConference'], g['awayClassification'], g['awayTeam'])])
                lvl = 'P4' if lv == ['P4', 'P4'] else ('G5' if set(lv) <= {'P4', 'G5'} else '/'.join(lv))
                res = g['awayPoints'] - g['homePoints']  # home cover if res < sp
                rows.append(dict(season=y, week=f'{st[0]}{wk}', id=g['id'], home=g['homeTeam'], away=g['awayTeam'], level=lvl,
                    min_games=min(m['n'].get(g['homeTeam'], 0), m['n'].get(g['awayTeam'], 0)), provider=pv,
                    close_spread=sp, model_spread=round(pr[0], 2), close_total=ou, model_total=round(pr[1], 2),
                    actual_spread=res, actual_total=g['homePoints'] + g['awayPoints']))
    if out:
        with open(out, 'w', newline='') as f:
            w = csv.DictWriter(f, rows[0].keys()); w.writeheader(); w.writerows(rows)
    return rows
def ats(rows, mkt, thr_fn):
    w = l = 0
    for r in rows:
        if mkt == 's': e = r['close_spread'] - r['model_spread']; a = r['close_spread'] - r['actual_spread']; # e>0 -> home
        else:
            if r['close_total'] is None: continue
            e = r['model_total'] - r['close_total']; a = r['actual_total'] - r['close_total']
        if abs(e) < thr_fn(r) or a == 0: continue
        if (e > 0) == (a > 0): w += 1
        else: l += 1
    return w, l
def report(rows, label):
    thr = lambda r: 3 if r['level'] == 'P4' else 5
    print(f'== {label}: n={len(rows)}')
    for lvl in ['ALL', 'P4', 'G5', 'other']:
        rr = [r for r in rows if lvl == 'ALL' or r['level'] == lvl or (lvl == 'other' and r['level'] not in ('P4', 'G5'))]
        if not rr: continue
        ms = np.mean([abs(r['model_spread'] - r['close_spread']) for r in rr])
        rt = [r for r in rr if r['close_total']]
        mt = np.mean([abs(r['model_total'] - r['close_total']) for r in rt]) if rt else float('nan')
        msr = np.mean([abs(r['model_spread'] - r['actual_spread']) for r in rr]); csr = np.mean([abs(r['close_spread'] - r['actual_spread']) for r in rr])
        sw, sl = ats(rr, 's', thr); tw, tl = ats(rr, 't', thr)
        pct = lambda a, b: f'{a}-{b} ({100*a/max(1,a+b):.1f}%, {(a*0.9091-b)/max(1,a+b)*100:+.1f}% ROI@-110)'
        print(f'  {lvl:5} n={len(rr):4} MAE vs close: spread {ms:.2f} total {mt:.2f} | MAE vs result: model {msr:.2f} close {csr:.2f} | ATS@thr spread {pct(sw,sl)} total {pct(tw,tl)}')
if __name__ == '__main__':
    for y in [2024, 2025, 2026]:
        rows = run([y], out=f'backtest_{y}.csv')
        report(rows, f'{y} all weeks'); report([r for r in rows if r['min_games'] >= 4], f'{y} both teams >=4 games this season')

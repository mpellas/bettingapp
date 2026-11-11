# Oct 25 2026 wk7 price-shop build (0 credits; reads raw/20261025T1432)
import sys, json, glob, os, requests, datetime as dt, subprocess
import pandas as pd, numpy as np
sys.path.insert(0, '/workspace/props-finder'); import find as F
HERE = '/workspace/props-finder/analysis/oct25'; RAW = '/workspace/props-finder/raw/20261025T1432'
events = [json.load(open(f)) for f in sorted(glob.glob(RAW + '/*.json'))]
rows = pd.DataFrame(F.analyze(events, {'draftkings', 'fliff'}))
rows['source'] = 'DK/Fliff price vs consensus'
# injuries (ESPN, free)
sb = requests.get('https://site.api.espn.com/apis/site/v2/sports/football/nfl/scoreboard', params={'dates': '20261025'}, timeout=20).json()
inj = {}
for e in sb['events']:
    s = requests.get('https://site.api.espn.com/apis/site/v2/sports/football/nfl/summary', params={'event': e['id']}, timeout=20).json()
    for t in s.get('injuries', []):
        for i in t.get('injuries', []):
            inj[(i.get('athlete') or {}).get('displayName')] = i.get('status')
def recheck(ko):
    if '10:00 AM' in ko: return 'Inactives are out about 8:30 AM PT; check them before betting.'
    t = {'1:05 PM': '11:35 AM', '1:25 PM': '11:55 AM', '5:20 PM': '3:50 PM'}
    for k, v in t.items():
        if k in ko: return (f'Recheck before betting: prices are from the ~7:32 AM PT pull. Check the official inactives '
                            f'(out about {v} PT) and confirm the app price is still at or better than the shop-at price.')
    return 'Recheck before betting.'
def status_dk(r):
    st = inj.get(r.player)
    if st and st not in ('Active',): return 'skip', f'ESPN injury status {st}'
    if r.ev_pct >= 2: return 'PASS', f'{r.book} {F.fmt(r.price)} beats consensus fair {F.fmt(r.fair_price)} by {r.ev_pct:.2f}% EV (>= 2 needed)'
    if r.ev_pct > 0: return 'fail', f'EV {r.ev_pct:.2f}% is positive but under the 2-point bar'
    return 'fail', f'best DK/Fliff price {F.fmt(r.price)} is worse than consensus fair {F.fmt(r.fair_price)} (EV {r.ev_pct:.2f}%)'
rows[['status', 'reason']] = rows.apply(lambda r: pd.Series(status_dk(r)), axis=1)
rows['injury'] = rows.player.map(inj).fillna('not listed')
# PrizePicks legs
L = pd.read_csv(sorted(glob.glob('/workspace/props-finder/analysis/pickem_nfl_legs_20261025T*.csv'))[-1])
Q = pd.read_csv(sorted(glob.glob('/workspace/props-finder/analysis/pickem_nfl_qualifying_20261025T*.csv'))[-1])
BE = {'power2': .5774, 'power3': .5503, 'flex3': .5774, 'flex4': .5503, 'flex5': .5426, 'flex6': .5421}
for t, b in Q.groupby('type').breakeven.min().items(): BE[t] = b  # exact values from pickem where available
def pp_types(p): return [t for t, b in BE.items() if p >= b + 0.01]
pp = []
for r in L.itertuples():
    types = pp_types(r.blend_win) if pd.notna(r.blend_win) else []; st = inj.get(r.player)
    if st and st != 'Active': s, why = 'skip', f'ESPN injury status {st}'
    elif r.flag == "<3 books" or pd.isna(r.blend_win): s, why = 'fail', 'fewer than 3 books'
    elif types: s, why = 'PASS', f'P(win) {r.blend_win:.1%} at PP {r.pp_line:g} clears break-even +1 pt for {", ".join(types)}'
    else: s, why = 'fail', f'P(win) {r.blend_win:.1%} under break-even +1 pt for every entry type (flex6 needs {BE["flex6"]+.01:.1%})'
    pp.append(dict(source='PrizePicks standard leg', event_id=r.event_id, game=r.game, kickoff_pt='Sun ' + r.kickoff_pt, player=r.player,
                   market=r.market, line=r.pp_line, side=r.side, book='prizepicks', price='', fair_prob=r.blend_win, fair_price=(F.amer(r.blend_win) if pd.notna(r.blend_win) else None),
                   ev_pct=round((r.blend_win / BE['flex6'] - 1) * 100, 2), n_books=r.n_books, alt_lines=r.book_lines,
                   status=s, reason=why, injury=st or 'not listed', pp_types=', '.join(types)))
A = pd.concat([rows, pd.DataFrame(pp)], ignore_index=True)
A['recheck'] = A.kickoff_pt.map(recheck)
A.to_csv(HERE + '/all_sides_stage1.csv', index=False)
print(A.status.value_counts()); print(A[A.status == 'PASS'][['source', 'player', 'market', 'line', 'side', 'book', 'price', 'fair_prob', 'ev_pct', 'pp_types']].to_string())
print(A[(A.status == 'skip')][['player', 'market', 'line', 'side', 'injury']].drop_duplicates('player').to_string())

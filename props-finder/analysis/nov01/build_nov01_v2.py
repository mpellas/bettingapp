# Nov 1 2026 wk8 price-shop build v2 (0 credits; offline; reads raw/20261101T1709 + frozen pregame file). Paper only.
# Gates added vs build_nov01.py:
#  1 fair = equal-weight median no-vig across ALL books at the exact line; skip if < 2 sharp books at that line
#  2 player-name normalization (Joshua->Josh, suffixes, punctuation)
#  3 team from frozen model file
#  4 model gate: in_model_universe True and model P(side) >= 55% (DK/Fliff) or >= PP break-even (PP-only)
import sys, json, glob, re, statistics
import pandas as pd, numpy as np
sys.path.insert(0, '/workspace/props-finder'); import find as F
HERE = '/workspace/props-finder/analysis/nov01'
if len(sys.argv) != 3: sys.exit('usage: python3 build_nov01_v2.py <raw_pull_dir> <pregame_predictions.csv>')
RAW, MODEL = sys.argv[1], sys.argv[2]
# find.py defines SHARP = {"pinnacle": 3} only; FanDuel and Circa added per the room decision (Circa is not in this pull)
SHARPS = {'pinnacle', 'fanduel'}
BET = {'draftkings', 'fliff'}; MK = {'player_pass_yds': 'pass_yds', 'player_rush_yds': 'rush_yds', 'player_reception_yds': 'reception_yds'}
NICK = {'joshua': 'josh', 'jacob': 'jake', 'matthew': 'matt', 'michael': 'mike', 'christopher': 'chris', 'william': 'will',
        'robert': 'rob', 'kenneth': 'ken', 'nicholas': 'nick', 'daniel': 'dan', 'gabriel': 'gabe', 'cameron': 'cam', 'joseph': 'joe'}
def norm_name(n):
    n = re.sub(r"[.'’\-]", ' ', str(n).lower()); w = [x for x in n.split() if x not in ('jr', 'sr', 'ii', 'iii', 'iv', 'v')]
    if w: w[0] = NICK.get(w[0], w[0])
    return ' '.join(w)
M = pd.read_csv(MODEL); M['nk'] = M.player_display_name.map(norm_name); M['market'] = M.market.replace({'rec_yds': 'reception_yds'})
TEAM = M.drop_duplicates('nk').set_index('nk').team.to_dict()
Mi = {(r.nk, r.market): r for r in M.itertuples()}
def model_p(nk, mk, line, side):
    r = Mi.get((nk, mk))
    if r is None: return None, TEAM.get(nk), False
    if not bool(r.in_model_universe): return None, r.team, False
    # file's own probability at line_D only; a different line is allowed only if same-or-easier for the side
    p = float(r.p_over_D) if side == 'Over' else 1 - float(r.p_over_D)
    ok = line <= r.line_D if side == 'Over' else line >= r.line_D
    return (p if ok else 0.0), r.team, True
events = [json.load(open(f)) for f in sorted(glob.glob(RAW + '/*.json'))]
props, dfs, gm = {}, {}, {}
for ev in events:
    gm[ev['id']] = f"{ev['away_team']} @ {ev['home_team']}"
    for b in ev['bookmakers']:
        for m in b['markets']:
            if m['key'] not in MK: continue
            for o in m['outcomes']:
                if o.get('point') is None: continue
                k = (ev['id'], norm_name(o['description']), MK[m['key']], float(o['point']))
                if b['key'] in F.DFS: dfs.setdefault(k, set()).add(b['key']); continue
                props.setdefault(k, {}).setdefault(b['key'], {})[o['name']] = o['price']
def fair_at(k):
    two = {b: s for b, s in props.get(k, {}).items() if 'Over' in s and 'Under' in s}
    sh = sorted(b for b in two if b in SHARPS)
    if not two: return None, two, sh
    return statistics.median(F.imp(s['Over']) / (F.imp(s['Over']) + F.imp(s['Under'])) for s in two.values()), two, sh
inj = pd.read_csv(HERE + '/all_sides_stage1.csv').drop_duplicates('player').set_index('player').injury.to_dict()
inj = {norm_name(k): v for k, v in inj.items()}
out, stat = [], []
for k in props:
    fo, two, sh = fair_at(k); eid, nk, mk, ln = k
    if len(two) >= 2: stat.append(dict(key=k, n_books=len(two), n_sharp=len(sh), sharps=','.join(sh)))
    for side in ('Over', 'Under'):
        c = [(b, s[side]) for b, s in two.items() if b in BET]
        if not c: continue
        b, pr = max(c, key=lambda x: F.dec(x[1])); fp = fo if side == 'Over' else 1 - fo
        out.append(dict(src='DK/Fliff', key=k, side=side, book=b, price=pr, fp=fp, ev=(fp * F.dec(pr) - 1) * 100, n=len(two), sh=sh, need=.55, bar='ev>=2'))
L = pd.read_csv(sorted(glob.glob('/workspace/props-finder/analysis/pickem_nfl_legs_20261101T*.csv'))[-1])
Q = pd.read_csv(sorted(glob.glob('/workspace/props-finder/analysis/pickem_nfl_qualifying_20261101T*.csv'))[-1])
BE = {'power2': .5774, 'power3': .5503, 'flex3': .5774, 'flex4': .5503, 'flex5': .5426, 'flex6': .5421}
for t, b in Q.groupby('type').breakeven.min().items(): BE[t] = b
for r in L.itertuples():
    k = (r.event_id, norm_name(r.player), r.market, float(r.pp_line)); fo, two, sh = fair_at(k)
    fp = None if fo is None else (fo if r.side == 'Over' else 1 - fo)
    out.append(dict(src='PrizePicks', key=k, side=r.side, book='prizepicks', price='', fp=fp, ev=None if fp is None else (fp / BE['flex6'] - 1) * 100,
                    n=len(two), sh=sh, need=min(BE.values()), bar='pp'))
rows = []
for o in out:
    eid, nk, mk, ln = o['key']; mp, team, inu = model_p(nk, mk, ln, o['side']); why = []
    if inj.get(nk, 'not listed') not in ('not listed', 'Active'): why.append(f"injury {inj[nk]}")
    if o['n'] < 2 or o['fp'] is None: why.append('no books at exact line')
    if len(o['sh']) < 2: why.append(f"{len(o['sh'])} sharp book(s) at line")
    if o['bar'] == 'ev>=2' and (o['ev'] is None or o['ev'] < 2): why.append(f"EV {o['ev']:.2f}% < 2")
    if o['bar'] == 'pp' and o['fp'] is not None and o['fp'] < o['need'] + .01: why.append(f"fair {o['fp']:.1%} < BE+1")
    if not inu: why.append('not in model universe')
    elif mp == 0.0: why.append('line harder than model line_D for this side')
    elif mp < o['need']: why.append(f"model {mp:.1%} < {o['need']:.1%}")
    rows.append(dict(status='PASS' if not why else 'fail', source=o['src'], game=gm.get(eid), team=team or '', player=nk, market=mk, line=ln, side=o['side'],
                     book=o['book'], price=o['price'], fair_prob=None if o['fp'] is None else round(o['fp'], 4), ev_pct=None if o['ev'] is None else round(o['ev'], 2),
                     n_books=o['n'], sharps=','.join(o['sh']), model_p=None if mp is None else round(mp, 4), reason='; '.join(why) or 'all gates pass'))
import os; tag = os.path.basename(os.path.normpath(RAW))
A = pd.DataFrame(rows); A.to_csv(HERE + f'/all_sides_v2_{tag}.csv', index=False)
S = pd.DataFrame(stat); S.to_csv(HERE + f'/sharp_coverage_v2_{tag}.csv', index=False)
print('PASS:', (A.status == 'PASS').sum())
names = ['jared goff', 'aaron jones', 'ty johnson', 'reggie virgil', 'josh palmer']
print(A[A.player.isin(names) & ((A.book == 'prizepicks') | (A.ev_pct > 0))].to_string())
n = len(S); s2 = (S.n_sharp >= 2).sum(); po = (S.sharps == 'pinnacle').sum(); s0 = (S.n_sharp == 0).sum(); s1o = ((S.n_sharp == 1) & (S.sharps != 'pinnacle')).sum()
print(f'priced lines {n}: >=2 sharp {s2} ({s2/n:.1%}); Pinnacle only {po} ({po/n:.1%}); other single sharp {s1o} ({s1o/n:.1%}); no sharp {s0} ({s0/n:.1%})')
print('sharp-book combos:', S.sharps.value_counts().to_dict())

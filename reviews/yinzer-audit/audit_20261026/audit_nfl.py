"""Oct 26 2026 audit, NFL picks process + paper track (Yinzer section). Read-only on all source files.
Rebuilds: posted picks (wk5-7) -> regrade vs nflverse stats_player_week_2026 (downloaded fresh) ->
EV/fair prob recomputed from props-finder/raw/* with find.analyze / pickem.consensus_at -> bar check ->
CLV vs DK close (nfl-props C captures, real prices only). Paper track wk5/wk6 regraded from track parquets.
Run: /workspace/nfl-props/.venv/bin/python audit_nfl.py"""
import sys, json, glob, os, re, unicodedata, hashlib, subprocess
import pandas as pd, numpy as np
sys.path.insert(0, '/workspace/props-finder'); import find as F, pickem as P
PF = '/workspace/props-finder'; NP = '/workspace/nfl-props'; OUT = os.path.dirname(os.path.abspath(__file__))
S = pd.read_parquet(os.path.join(OUT, 'stats_player_week_2026.parquet'))
norm = lambda x: re.sub(r'(jr|sr|ii|iii)$', '', re.sub(r'[^a-z]', '', unicodedata.normalize('NFKD', str(x)).encode('ascii', 'ignore').decode().lower()))
S['k'] = S.player_display_name.map(norm)
COL = {'rush_attempts': 'carries', 'receptions': 'receptions', 'rush_yds': 'rushing_yards', 'reception_yds': 'receiving_yards',
       'rec_yds': 'receiving_yards', 'pass_yds': 'passing_yards'}
def actual(pl, mk, wk):
    r = S[(S.k == norm(pl)) & (S.week == wk)]
    return float(r[COL[mk]].iloc[0]) if len(r) else np.nan
def novig(o, u): po, pu = F.imp(o), F.imp(u); return po / (po + pu)
# ---- 1. posted picks
picks = []
for f, wk, raw in [('analysis_2026_wk5_live_20261011T0538.csv', 5, '20261011T1237'), ('analysis_2026_wk5_live_20261012T1434.csv', 5, '20261012T2133')]:
    a = pd.read_csv(f'{PF}/analysis/{f}'); a = a[a.in_final_list == True]
    for r in a.itertuples():
        picks.append(dict(week=wk, list=f, raw=raw, player=r.player, market=r.market, line=r.line, side=r.side, book=r.book,
                          price=r.price, posted_fair=r.blend_p, posted_ev=r.ev_pct, pp_types='', bar_in_force=False))
for tp in pd.read_csv(f'{PF}/analysis/pickem_nfl_qualifying_20261012T1434.csv').groupby(['player', 'market', 'pp_line', 'side']):
    (pl, mk, ln, sd), g = tp
    picks.append(dict(week=5, list='pickem_nfl_qualifying_20261012T1434.csv', raw='20261012T2133', player=pl, market=mk, line=ln, side=sd,
                      book='prizepicks', price=np.nan, posted_fair=g.blend_win.iloc[0], posted_ev=np.nan, pp_types=','.join(g.type),
                      bar_in_force=False, be_min=g.breakeven.min()))
for f, wk, raw in [('oct18/nfl_wk6_oct18_all_sides.csv', 6, '20261018T1440'), ('oct25/nfl_wk7_oct25_all_sides.csv', 7, '20261025T1432')]:
    a = pd.read_csv(f'{PF}/analysis/{f}'); a = a[a.status == 'PASS']
    for r in a.itertuples():
        picks.append(dict(week=wk, list=f, raw=raw, player=r.player, market=r.market, line=r.line, side=r.side, book=r.book, price=r.price,
                          posted_fair=r.fair_prob, posted_ev=r.ev_pct, pp_types=r.pp_types if isinstance(r.pp_types, str) else '', bar_in_force=True))
K = pd.DataFrame(picks)
BE = {'power2': .5774, 'power3': .5503, 'flex3': .5774, 'flex4': .5503, 'flex5': .5426, 'flex6': .5421}
# ---- 2. recompute fair/EV from raw
cache = {}
def raw_events(d):
    if d not in cache: cache[d] = [json.load(open(x)) for x in sorted(glob.glob(f'{PF}/raw/{d}/*.json'))]
    return cache[d]
def recompute(r):
    ev = raw_events(r.raw)
    if r.book != 'prizepicks':
        rows = pd.DataFrame(F.analyze(ev, {'draftkings', 'fliff'}))
        m = rows[(rows.player == r.player) & (rows.market == r.market) & (rows.line == r.line) & (rows.side == r.side)]
        if not len(m): return pd.Series(dict(re_fair=np.nan, re_ev=np.nan, re_book='', re_price=np.nan))
        m = m.iloc[0]; return pd.Series(dict(re_fair=m.fair_prob, re_ev=m.ev_pct, re_book=m.book, re_price=m.price))
    for e in ev:
        bl = []
        for b in e.get('bookmakers', []):
            if b['key'] in F.DFS: continue
            for mk in b['markets']:
                if mk['key'] != 'player_' + r.market: continue
                pr = {}
                for o in mk['outcomes']:
                    if o.get('description') == r.player and o.get('point') is not None: pr.setdefault(float(o['point']), {})[o['name']] = o['price']
                for ln, sd in pr.items():
                    if 'Over' in sd and 'Under' in sd: bl.append((b['key'], ln, novig(sd['Over'], sd['Under'])))
        if bl:
            par = 30.0 if r.market in P.COUNT_MK else (P.DEF_S.get(r.market) or max(12.0, 0.55 * r.line))
            dist = 'nb' if r.market in P.COUNT_MK else 'norm'
            c = P.consensus_at(bl, dist, par, r.line)
            if c is None: continue
            (po, pp, pu), _ = c; p = po if r.side == 'Over' else pu
            return pd.Series(dict(re_fair=round(p, 4), re_ev=np.nan, re_book='prizepicks', re_price=np.nan))
    return pd.Series(dict(re_fair=np.nan, re_ev=np.nan, re_book='', re_price=np.nan))
K = pd.concat([K, K.apply(recompute, axis=1)], axis=1)
K['fair_diff_pts'] = (K.re_fair - K.posted_fair) * 100
def bar(r):
    if r.book == 'prizepicks':
        types = [t for t in str(r.pp_types).split(',') if t.strip()]
        ok = all(r.re_fair >= BE[t.strip()] + (0.01 if r.bar_in_force else 0) - 1e-4 for t in types) if types else False
        return 'ok' if ok else ('n/a (pre-bar)' if not r.bar_in_force else 'FAIL')
    if not r.bar_in_force: return 'n/a (pre-bar; EV %.2f%%)' % r.re_ev
    return 'ok' if r.re_ev >= 2 else 'FAIL'
K['bar_check'] = K.apply(bar, axis=1)
# ---- 3. grade
K['actual'] = [actual(r.player, r.market, r.week) for r in K.itertuples()]
def res(r):
    if pd.isna(r.actual): return 'no_stat'
    if r.actual == r.line: return 'P'
    return 'W' if (r.actual > r.line) == (r.side == 'Over') else 'L'
K['result'] = K.apply(res, axis=1)
K['units'] = [(F.dec(r.price) - 1 if r.result == 'W' else -1 if r.result == 'L' else 0) if r.book != 'prizepicks' else np.nan for r in K.itertuples()]
# ---- 4. CLV vs DK close. ESPN C captures carry NO prices (price_assumed=True on every wk5-7 row), so price/no-vig CLV
# is impossible; we report LINE CLV in yards/attempts: close line vs posted line, signed so + = market moved our way.
def clv(r):
    f = f'{NP}/data/lines/snap_2026_wk{r.week}_C.csv'
    if not os.path.exists(f): return np.nan
    c = pd.read_csv(f); mk = {'reception_yds': 'rec_yds'}.get(r.market, r.market)
    m = c[(c.player_name.map(norm) == norm(r.player)) & (c.market == mk)]
    if not len(m): return np.nan
    cl = float(m.iloc[-1].line)
    return round((cl - r.line) if r.side == 'Under' else (r.line - cl), 2)
K['clv_pts'] = K.apply(clv, axis=1)
K.insert(0, 'kind', 'posted_pick')
# ---- 5. paper track wk5/wk6 regrade
T = []
for wk in (5, 6):
    t = pd.read_parquet(f'{NP}/data/track/2026_wk{wk:02d}.parquet')
    t = t[(t.void != True) & (t.in_scope == True)].copy()
    t['actual_re'] = [actual(p, m, wk) for p, m in zip(t.player_name, t.market)]
    t['stat_match'] = (t.actual_re == t.actual)
    t['result'] = np.where(t.actual_re == t.line, 'P', np.where((t.actual_re > t.line) == (t.model_side == 'over'), 'W', 'L'))
    t.loc[t.actual_re.isna(), 'result'] = 'no_stat'
    t['track_hit_main'] = t.hit_main
    t['side_price'] = np.where(t.model_side == 'over', t.over_price, t.under_price)
    t['units'] = [(F.dec(p) - 1 if r == 'W' else -1 if r == 'L' else 0) for p, r in zip(t.side_price, t.result)]
    t['clv_pts'] = t.z_clv
    T.append(t.assign(kind='paper_track', week=wk)[['kind', 'week', 'player_name', 'market', 'line', 'model_side', 'side_price', 'real_prices',
        'actual', 'actual_re', 'stat_match', 'track_hit_main', 'result', 'units', 'clv_pts']].rename(columns={'player_name': 'player', 'model_side': 'side', 'side_price': 'price'}))
T = pd.concat(T)
pd.concat([K, T]).to_csv(os.path.join(OUT, 'sides.csv'), index=False)
# ---- summary
def summ(name, d, clvname):
    w, l, p = (d.result == 'W').sum(), (d.result == 'L').sum(), (d.result == 'P').sum(); c = d.clv_pts.dropna()
    return dict(slice=name, sides=len(d), W=w, L=l, P=p, units=round(d.units.sum(), 2) if d.units.notna().any() else np.nan,
                clv_n=len(c), clv_mean=round(c.mean(), 3) if len(c) else np.nan, clv_unit=clvname)
rows = [summ('Posted picks, all (wk5-7)', K, 'line pts'),
        summ('Posted DK/Fliff', K[K.book != 'prizepicks'], 'line pts'),
        summ('Posted PrizePicks legs', K[K.book == 'prizepicks'], 'line pts')]
for wk in (5, 6, 7): rows.append(summ(f'Posted wk{wk}', K[K.week == wk], 'line pts'))
rows.append(summ('Paper track wk5+6 (in-scope, non-void)', T, 'z_clv'))
for wk in (5, 6): rows.append(summ(f'Paper track wk{wk}', T[T.week == wk], 'z_clv'))
pd.DataFrame(rows).to_csv(os.path.join(OUT, 'summary.csv'), index=False)
print(pd.DataFrame(rows).to_string())
print(K[['week', 'player', 'market', 'line', 'side', 'book', 'price', 'posted_fair', 're_fair', 'fair_diff_pts', 'posted_ev', 're_ev', 'bar_check', 'actual', 'result', 'units', 'clv_pts']].to_string())
print('paper stat mismatches:', (~T.stat_match).sum(), 'result vs track hit_main mismatches:', ((T.result == 'W') != (T.track_hit_main == True)).sum())
# ---- hashes
sh = lambda p: hashlib.sha1(open(p, 'rb').read()).hexdigest()
blob = lambda p: subprocess.run(['git', '-C', NP, 'hash-object', p], capture_output=True, text=True).stdout.strip()
pin = subprocess.run(['git', '-C', NP, 'rev-parse', 'de029ac:src/nflprops/track.py'], capture_output=True, text=True).stdout.strip()
print('prereg sha1', sh(f'{NP}/prereg/prereg_2026_wk5-18_PUBLISHED_20261005.yaml'), 'expected fc9961cfe3c5dd0075a89173393e5d88e67f3cd1')
print('track.py blob', blob(f'{NP}/src/nflprops/track.py'), 'de029ac blob', pin)

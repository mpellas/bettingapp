import os, sys, glob, re, numpy as np, pandas as pd
sys.path.insert(0, '/workspace/nhl-sog'); os.chdir('/workspace/nhl-sog')
import shrink, evidence_extra as X
L = shrink.gamelogs(); rows = []; seen = set()
for f in sorted(glob.glob('picks/2026*_D_*.csv')):
    b = os.path.basename(f); d = b[:8]
    if not re.fullmatch(r'\d{8}_D_\d{4}(pass)?\.csv', b) or d in seen: continue
    seen.add(d); P = pd.read_csv(f); iso = f'{d[:4]}-{d[4:6]}-{d[6:]}'
    ctx = dict(logs=L, iso=iso, fliff={})
    sh = L[L.gameDate == iso].set_index(['playerId', 'gameId']).shots
    for _, r in P.drop_duplicates(['nhl_id', 'line']).iterrows():
        k = (r['nhl_id'], r['gameId'])
        if k not in sh.index or pd.isna(r['nv_over']): continue
        s = sh.loc[k]; s = s.iloc[0] if hasattr(s, 'iloc') else s
        if s == r['line']: continue
        for side in ('over', 'under'):
            v, w = X.rest(r, side, ctx); nv = r['nv_over'] if side == 'over' else 1 - r['nv_over']
            rows.append(dict(date=d, gameId=r['gameId'], player=r['player'], line=r['line'], side=side, nv=nv,
                             hit=int((s > r['line']) == (side == 'over')), rest=v, why=w))
R = pd.DataFrame(rows); R.to_csv('/workspace/tester2-review/20261109_nhl_rest/rows.csv', index=False)
print('dates', R.date.nunique(), 'lines', len(R)//2, 'games', R.gameId.nunique())
print(R[R.side=='over'].why.value_counts().to_dict())
for v in (1, 0, -1):
    s = R[R.rest == v]
    if not len(s): continue
    g = s.groupby('gameId').apply(lambda x: (x.hit - x.nv).sum()); n = s.groupby('gameId').size()
    rng = np.random.default_rng(0); idx = rng.integers(0, len(g), (2000, len(g)))
    m = g.values[idx].sum(1) / n.values[idx].sum(1)
    print({1:'+',0:'0',-1:'-'}[v], 'sides', len(s), 'hit', round(s.hit.mean(),3), 'no-vig', round(s.nv.mean(),3),
          'hit-minus-novig', round((s.hit-s.nv).mean()*100,1), 'pts, 95% CI', [round(x*100,1) for x in np.percentile(m,[2.5,97.5])])

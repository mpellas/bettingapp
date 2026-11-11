"""Backtest the evidence gate on graded DK lines Oct 11-16 (status OK).
Candidate side: champion edge (p_model - no-vig, on that side) >= 1 point. Gate: agrees_n >= K (K = 4 chosen ex ante;
others = sensitivity). Signals as in evidence.py; challenger P from challenger/stageC_rows.csv (trained through Oct 10,
out-of-sample for these dates); shop-gate veto used where a GATE file exists (Oct 15, 16).
Reports n, hit vs implied, z-CLV, log-loss (champion vs no-vig on the picked side), price mix; game-clustered 95% CIs."""
import sys, os, glob, math
import numpy as np, pandas as pd
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__))); sys.path.insert(0, ROOT); os.chdir(ROOT)
sys.path.insert(0, os.path.join(ROOT, 'challenger'))
import evidence as E, shrink
from common import boot_diff
SC = pd.read_csv('challenger/stageC_rows.csv')
chal = {(int(a), int(g), float(b)): p for a, g, b, p in zip(SC.nhl_id, SC.gameId, SC.line, SC.p_chal)}
rows = []
for d in ['20261011', '20261012', '20261013', '20261014', '20261015', '20261016']:
    G = pd.read_csv(f'graded/{d}.csv'); G = G[(G.status == 'OK') & G.actual.notna()].reset_index(drop=True)
    gate = pd.read_csv(f'picks/{d}_D_GATE.csv') if os.path.exists(f'picks/{d}_D_GATE.csv') else None
    ch = {(a, b): chal.get((int(a), int(g), float(b))) for a, g, b in zip(G.nhl_id, G.gameId, G.line)}
    A = E.annotate(G, d, gate=gate, chal={k: v for k, v in ch.items() if v is not None})
    A['date'] = d; rows.append(G.merge(A, on=['nhl_id', 'line']))
X = pd.concat(rows, ignore_index=True)
o = X.side == 'over'
X['nv_side'] = np.where(o, X.nv_over, 1 - X.nv_over); X['pm_side'] = np.where(o, X.p_model_over, 1 - X.p_model_over)
X['edge'] = X.pm_side - X.nv_side
X['hit'] = np.where(o, X.actual > X.line, X.actual < X.line).astype(int)
lg = lambda p: np.log(np.clip(p, 1e-3, 1 - 1e-3) / (1 - np.clip(p, 1e-3, 1 - 1e-3)))
X['zclv'] = np.where(o, 1, -1) * (lg(X.nv_over_C) - lg(X.nv_over))
ll = lambda p, y: -(y * np.log(np.clip(p, 1e-6, 1)) + (1 - y) * np.log(np.clip(1 - p, 1e-6, 1)))
X['dll'] = ll(X.pm_side, X.hit) - ll(X.nv_side, X.hit)
X['price'] = np.where(o, X.over, X.under).astype(float)
cand = X[X.edge >= 0.01]
f = lambda t: f'{t[0]*100:+.1f} [{t[1]*100:+.1f}, {t[2]*100:+.1f}]'
fz = lambda t: f'{t[0]:+.4f} [{t[1]:+.4f}, {t[2]:+.4f}]'
print(f'graded OK lines {X[["nhl_id","gameId","line"]].drop_duplicates().shape[0]}, games {X.gameId.nunique()}; candidate sides (champion edge >= 1 pt): {len(cand)}')
print('agrees_n distribution among candidates:', cand.agrees_n.value_counts().sort_index().to_dict())
print('| rule | picks | games | hit | implied | hit - implied (pts) | z-CLV | log-loss champ - market | at -200 or shorter | median price | unders |')
print('|---|---|---|---|---|---|---|---|---|---|---|')
for K in [None, 2, 3, 4, 5]:
    s = cand if K is None else cand[cand.agrees_n >= K]
    lab = 'edge >= 1 pt only' if K is None else f'edge >= 1 pt and agrees >= {K}' + (' (ex-ante K)' if K == 4 else '')
    if len(s) < 3: print(f'| {lab} | {len(s)} | – | too few |'); continue
    g = s.gameId.values
    print(f'| {lab} | {len(s)} | {s.gameId.nunique()} | {s.hit.mean():.3f} | {s.nv_side.mean():.3f} | {f(boot_diff((s.hit - s.nv_side).values, g))} | '
          f'{fz(boot_diff(s.zclv.values, g))} | {fz(boot_diff(s.dll.values, g))} | {(s.price <= -200).mean():.1%} | {s.price.median():+.0f} | {(s.side=="under").mean():.0%} |')
rest = cand[cand.agrees_n < 4]
if len(rest) > 2:
    print(f'| complement: edge >= 1 pt and agrees < 4 | {len(rest)} | {rest.gameId.nunique()} | {rest.hit.mean():.3f} | {rest.nv_side.mean():.3f} | {f(boot_diff((rest.hit-rest.nv_side).values, rest.gameId.values))} | {fz(boot_diff(rest.zclv.values, rest.gameId.values))} | {fz(boot_diff(rest.dll.values, rest.gameId.values))} | {(rest.price <= -200).mean():.1%} | {rest.price.median():+.0f} | {(rest.side=="under").mean():.0%} |')
print('\nper-signal agreement among candidates and hit - implied when the signal is + vs not:')
for k in E.SIGS:
    p = cand[cand[f'sig_{k}'] == '+']; q = cand[cand[f'sig_{k}'] != '+']
    if len(p) > 2 and len(q) > 2:
        print(f'  {k:7s} + on {len(p):3d}: {f(boot_diff((p.hit-p.nv_side).values, p.gameId.values))} | not +: {len(q):3d}: {f(boot_diff((q.hit-q.nv_side).values, q.gameId.values))}')
    else: print(f'  {k:7s} + on {len(p)} (not enough to split)')
X.to_csv('shadow/backtest_evidence_rows.csv', index=False)
# gated vs complement difference, joint game bootstrap
def joint(a, b, col, B=2000):
    ga, gb = a.groupby('gameId')[col].agg(['sum', 'count']), b.groupby('gameId')[col].agg(['sum', 'count'])
    games = sorted(set(ga.index) | set(gb.index)); ga, gb = ga.reindex(games, fill_value=0), gb.reindex(games, fill_value=0)
    rng = np.random.default_rng(0); idx = rng.integers(0, len(games), (B, len(games)))
    d = ga['sum'].values[idx].sum(1) / ga['count'].values[idx].sum(1) - gb['sum'].values[idx].sum(1) / gb['count'].values[idx].sum(1)
    return a[col].mean() - b[col].mean(), *np.percentile(d, [2.5, 97.5])
g4 = cand[cand.agrees_n >= 4].assign(res=lambda s: s.hit - s.nv_side); c4 = rest.assign(res=lambda s: s.hit - s.nv_side)
print('\nK=4 gated minus complement: hit-implied', f(joint(g4, c4, 'res')), '| z-CLV', fz(joint(g4, c4, 'zclv')), '| log-loss', fz(joint(g4, c4, 'dll')))

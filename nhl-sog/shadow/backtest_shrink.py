"""Backtest: raw 10-game recent-form rule (as logged; and on fresh logs) vs gamma-Poisson shrunk rule,
on graded/<date>.csv rows with status OK and a box-score result. Usage: python3 shadow/backtest_shrink.py 20261011 ... [--m 15]
Scores (all vs the same rows):
  log-loss / Brier of P(over) vs the outcome (market no-vig nv_over is the benchmark)
  'pass' sides (method P(side) > no-vig P(side)): n, hit rate, market-implied rate (mean no-vig P of those sides),
  hit minus implied, mean z-CLV (logit no-vig at C minus at D, side-signed), share of z-CLV > 0."""
import sys, os, math, argparse
import numpy as np, pandas as pd
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.chdir(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import shrink, recent_form
ap = argparse.ArgumentParser(); ap.add_argument('dates', nargs='+'); ap.add_argument('--m', type=int, default=15); a = ap.parse_args()
G = pd.concat([pd.read_csv(f'graded/{d}.csv').assign(date=d) for d in a.dates], ignore_index=True)
G = G[(G.status == 'OK') & G.actual.notna()].copy()
G = recent_form.annotate(G); G = shrink.annotate(G, a.m)
G = G[G.p_shrunk_over.notna()]
lg = lambda p: np.log(np.clip(p, 1e-3, 1 - 1e-3) / (1 - np.clip(p, 1e-3, 1 - 1e-3)))
y = (G.actual > G.line).astype(int)
G['zc_over'] = lg(G.nv_over_C) - lg(G.nv_over)
def ll(p): p = np.clip(p, 1e-3, 1 - 1e-3); return float(-(y * np.log(p) + (1 - y) * np.log(1 - p)).mean())
def br(p): return float(((p - y) ** 2).mean())
res = []
meths = {'market no-vig': ('nv_over', None), 'frozen model': ('p_model_over', None),
         'raw r10 (as logged)': ('p_recent_over', 'p_recent_under'), 'raw r10 (fresh logs)': ('p_fresh_over', 'p_fresh_under'),
         f'shrunk m={a.m} (fresh)': ('p_shrunk_over', 'p_shrunk_under')}
for name, (po, pu) in meths.items():
    p_over = G[po]; row = dict(method=name, n_rows=len(G), logloss=ll(p_over), brier=br(p_over))
    if name != 'market no-vig':
        p_under = G[pu] if pu else 1 - G[po]
        sides = []
        for side, pp, nvp, hit, zc in (('over', p_over, G.nv_over, G.actual > G.line, G.zc_over),
                                        ('under', p_under, 1 - G.nv_over, G.actual < G.line, -G.zc_over)):
            m = pp > nvp
            sides.append(pd.DataFrame(dict(hit=hit[m].astype(int), imp=nvp[m], zc=zc[m], side=side)))
        S = pd.concat(sides)
        row.update(n_pass=len(S), n_over=int((S.side == 'over').sum()), hit=S.hit.mean(), implied=S.imp.mean(),
                   hit_minus_implied=S.hit.mean() - S.imp.mean(), se_hit=math.sqrt(S.imp.mean() * (1 - S.imp.mean()) / len(S)),
                   mean_zclv=S.zc.mean(), share_zclv_pos=(S.zc > 0).mean(), share_zclv_neg=(S.zc < 0).mean())
    res.append(row)
R = pd.DataFrame(res)
print(f'dates {a.dates}; rows {len(G)} (status OK, result known, shrink computable); games {G.gameId.nunique()}')
print(R.round(4).to_string(index=False))

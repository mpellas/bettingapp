"""Market-free sanity check of the CFB ratings (NOT a test against lines): walk-forward 2026 weeks 3+, refit before
each week's first game, predict that week's final margins and totals. Compares MAE with naive baselines
(margin = home field only; total = 2*mean points) and with prior-season weight 0.15 vs 0.5 vs 1.0. Game-level
bootstrap 95% CI on the MAE difference vs naive."""
import os, sys, numpy as np, pandas as pd
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__))); import cfb_evidence as C
G = C.load(); cur = G[(G.season == 2026) & (G.seasontype == 2)]
def boot(d, B=2000):
    rng = np.random.default_rng(0); m = d[rng.integers(0, len(d), (B, len(d)))].mean(1); return d.mean(), *np.percentile(m, [2.5, 97.5])
for pw in (0.15, 0.5, 1.0):
    C.PRIOR_W = pw; R = []
    for w in sorted(cur.week.unique()):
        if w < 3: continue
        g = cur[cur.week == w]; F = C.fit(G, 2026, g.date.min())
        for x in g.itertuples():
            if 'FCS' in (x.home, x.away): continue
            pm = C.pred_margin(F, x.home, x.away, x.neutral); pt = C.pred_total(F, x.home, x.away)
            am, at = x.home_pts - x.away_pts, x.home_pts + x.away_pts
            R.append(dict(week=w, em=abs(am - pm), en=abs(am - (0 if x.neutral else F['hfa'])), et=abs(at - pt), etn=abs(at - 2 * F['mu'])))
    R = pd.DataFrame(R)
    dm = boot((R.em - R.en).values); dt_ = boot((R.et - R.etn).values)
    print(f'prior-season weight {pw}: {len(R)} FBS-vs-FBS games, weeks {R.week.min()}-{R.week.max()}: margin MAE {R.em.mean():.2f} vs naive {R.en.mean():.2f} '
          f'(diff {dm[0]:+.2f} [{dm[1]:+.2f}, {dm[2]:+.2f}]); total MAE {R.et.mean():.2f} vs naive {R.etn.mean():.2f} (diff {dt_[0]:+.2f} [{dt_[1]:+.2f}, {dt_[2]:+.2f}])')

import sys, pickle, numpy as np, pandas as pd
sys.path.insert(0, "/workspace/nfl-props/src")
from nflprops.betting import add_probs, select_bets
from nflprops.metrics import _ll
pd.set_option("display.width", 220); pd.set_option("display.max_columns", 30)
Z = pickle.load(open("out/zfits.pkl", "rb"))
def F(zs, z):
    n = len(zs); return np.interp(z, zs, (np.arange(1, n + 1) - 0.5) / n, left=0.0, right=1.0)
# 1) reproduction check
real = pd.read_parquet("/workspace/nfl-props/data/cache/preds/preds_04cd0d349a_2025.parquet")
chk = []
for mk, g in real[real.line.notna()].groupby("market"):
    p = 1 - F(Z[(2025, mk)]["z_sorted"], (g.line.values - g.mu.values) / g.s.values)
    chk.append(np.abs(p - g.p_over_model.values).max())
print("max |p_over reproduced - cached| per market:", np.round(chk, 8))
# 2) PIT on all walk-forward predictions 2019-2025 (champion; mu/s do not depend on line source)
pp = pd.concat([pd.read_parquet(f"/workspace/nfl-props/data/cache/preds/preds_63785e6609_{s}.parquet") for s in range(2019, 2026)])
pp["z"] = (pp.actual - pp.mu) / pp.s
pp["pit"] = np.nan
for (S, mk), idx in pp.groupby(["season", "market"]).groups.items():
    pp.loc[idx, "pit"] = F(Z[(S, mk)]["z_sorted"], pp.loc[idx, "z"].values)
pp = pp.reset_index(drop=True)
def pit_tab(g):
    return pd.Series({"n": len(g), "P(y<model median)": (g.pit < 0.5).mean(), "cov50 [.25,.75]": g.pit.between(.25, .75).mean(),
                      "cov80 [.1,.9]": g.pit.between(.1, .9).mean(), "P(y=0)": (g.actual == 0).mean(), "mean pit": g.pit.mean()})
print("\n== PIT calibration of the full predictive distribution, walk-forward 2019-2025 (ideal: .5/.5/.8/.5) ==")
print(pp.groupby("market").apply(pit_tab).round(3).to_string())
print("\n-- by market x season --"); print(pp.groupby(["market", "season"]).apply(pit_tab)[["n", "P(y<model median)", "cov50 [.25,.75]"]].round(3).unstack(0).to_string())
pp["mu_q"] = pp.groupby("market").mu.transform(lambda x: pd.qcut(x, 5, labels=False))
print("\n-- by market x mu quintile (0=lowest projection) --")
print(pp.groupby(["market", "mu_q"]).apply(pit_tab)[["n", "P(y<model median)", "cov50 [.25,.75]", "cov80 [.1,.9]", "P(y=0)"]].round(3).to_string())
print("\n-- rec_yds/rush_yds by position --")
print(pp[pp.market != "pass_yds"].groupby(["market", "position"]).apply(pit_tab)[["n", "P(y<model median)", "cov50 [.25,.75]", "cov80 [.1,.9]"]].round(3).to_string())
# 3) player-specific variance: does a player's PRIOR-season mean |z| predict this season's |z| (beyond s)?
pz = pp.groupby(["market", "player_id", "season"]).agg(az=("z", lambda x: np.abs(x).mean()), n=("z", "size")).reset_index()
pz["prev_az"] = pz.sort_values("season").groupby(["market", "player_id"]).az.shift(1)
pz["prev_n"] = pz.sort_values("season").groupby(["market", "player_id"]).n.shift(1)
q = pz[(pz.prev_n >= 6) & (pz.n >= 6)]
print("\n== player-specific dispersion: corr(prior-season mean|z|, this-season mean|z|), player-seasons with >=6 games both ==")
for mk, g in q.groupby("market"):
    from scipy import stats
    r = stats.pearsonr(g.prev_az, g.az); print(f"  {mk}: n={len(g)} r={r[0]:.3f} p={r[1]:.4f}")
pp.to_pickle("out/pit_2019_2025.pkl")

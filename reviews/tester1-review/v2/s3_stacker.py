"""The 300-line minimum and the ridge stacker on the frozen 2025 real lines. EXPLORATORY on the frozen holdout:
for understanding the mechanism only, NOT for re-tuning the 2025 decision."""
import sys, numpy as np, pandas as pd
sys.path.insert(0, "/workspace/tester1-review/v2/proj/src")
from nflprops.calibration import stacked_probs, fit_stacker, _logit
from nflprops.betting import select_bets, simulate_bankroll
from nflprops.metrics import _ll, cluster_bootstrap_roi
pd.set_option("display.width", 220)
p = pd.read_pickle("out/holdout_p_real.pkl"); coefs = pd.read_pickle("out/holdout_coefs_real.pkl")
BC = dict(edge_threshold=0.04, kelly_fraction=0.25, max_bet_frac=0.02, max_game_frac=0.04, max_bets_per_game=3,
          max_team_frac=0.03, max_bets_per_player=1, max_week_exposure=0.2, start_bankroll=1000)
print("lines per market per week (2025 real, priced, non-push):")
print(p[~p.push].groupby(["week", "market"]).size().unstack().to_string())
print("cumulative lines BEFORE week t:"); cum = p[~p.push].groupby(["market", "week"]).size().groupby(level=0).cumsum().unstack(0).shift(1).fillna(0).astype(int); print(cum.to_string())

# decomposition of the 18 bets
b18 = pd.read_pickle("out/holdout_bets_18.pkl")
c = coefs.dropna().assign(week=lambda d: d.t % 100)
m = b18.merge(c[["market", "week", "a", "b", "c"]], on=["market", "week"])
lm, ld = _logit(m.p_mkt_over), _logit(m.p_over_model)
print("\n18 bets: mean logit contributions  a = %.3f, (b-1)*logit(p_mkt) = %.3f, c*logit(p_model) = %.3f; mean logit(p_mkt) = %.3f" % (
    m.a.mean(), ((m.b - 1) * lm).mean(), (m.c * ld).mean(), lm.mean()))
print("18 bets: prices (over/under):", (m.over_price.astype(int).astype(str) + "/" + m.under_price.astype(int).astype(str)).value_counts().to_dict())
print("18 bets: raw model side agrees with bet side (p_model<0.5 for unders):", int((m.p_over_model < 0.5).sum()), "of", len(m))

# Fisher information / effective shrinkage of c by the ridge prior
print("\nRidge lambda=50 adds 2*lambda=100 to the curvature for c. Data curvature I_c = sum p(1-p) x^2 (x = logit p_model, centred):")
for mk, g in p[~p.push].groupby("market"):
    for n_ in [300, len(g)]:
        gg = g.sort_values(["week"]).head(n_); x = _logit(gg.p_over_model); x = x - x.mean(); q = gg.p_mkt_over
        I = float((q * (1 - q) * x ** 2).sum())
        print(f"  {mk}: n={n_:5d}  I_c={I:7.1f}  MLE SE(c)={1/np.sqrt(I):.3f}  shrink factor I/(I+100)={I/(I+100):.2f}")

def run(lam, min_n, pooled=False):
    if pooled:
        q = p.assign(market_orig=p.market, market="ALL")
        ps, cf = stacked_probs(q, None, lam, min_n)
    else:
        ps, cf = stacked_probs(p, None, lam, min_n)
    pp = p.assign(p_over=ps.clip(1e-4, 1 - 1e-4))
    b = select_bets(pp, BC); b, _ = simulate_bankroll(b, BC)
    nb = pp[~pp.push]
    gain = (_ll(nb.p_mkt_over, nb.over_hit) - _ll(nb.p_over, nb.over_hit))
    g = nb.assign(d=gain).groupby("game_id").d.agg(["sum", "size"]); rng = np.random.default_rng(0)
    idx = rng.integers(0, len(g), (4000, len(g))); bs = g["sum"].values[idx].sum(1) / g["size"].values[idx].sum(1)
    lo, hi = cluster_bootstrap_roi(b) if len(b) > 1 else (np.nan, np.nan)
    return {"lambda": lam, "min_n": min_n, "pooled": pooled, "bets": len(b), "by_mkt": b.groupby("market").size().to_dict() if len(b) else {},
            "unders": int((b.side == "under").sum()) if len(b) else 0, "flat_roi": b.flat_profit.mean() if len(b) else np.nan,
            "roi_ci": (round(lo, 3), round(hi, 3)), "LL gain stacked vs mkt": float(gain.mean()), "LLgain CI": (round(np.quantile(bs, .025), 4), round(np.quantile(bs, .975), 4)),
            "c_last": cf.dropna().groupby("market").c.last().round(3).to_dict()}
rows = []
for lam in [1e-6, 10, 50, 200]:
    for mn in [50, 100, 200, 300, 500]:
        rows.append(run(lam, mn))
for mn in [100, 300]:
    rows.append(run(50, mn, pooled=True))
T = pd.DataFrame(rows); print("\n" + T.to_string(index=False)); T.to_csv("out/s3_stacker_grid.csv", index=False)

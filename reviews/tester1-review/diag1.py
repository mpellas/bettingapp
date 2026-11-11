"""Diagnostics on the 2025 real-ESPN-open holdout using the builder's cached predictions (read-only)."""
import sys, numpy as np, pandas as pd
sys.path.insert(0, "/workspace/nfl-props/src")
from nflprops.betting import add_probs, select_bets, simulate_bankroll, american_to_decimal
from nflprops.metrics import _ll
pd.set_option("display.width", 200); pd.set_option("display.max_columns", 30)
P = "/workspace/nfl-props/data/cache/preds/preds_04cd0d349a_2025.parquet"
pr = pd.read_parquet(P)
DP = {"market_blend": 0.5, "edge_threshold": 0.04, "kelly_fraction": 0.25, "max_bet_frac": 0.02, "max_week_exposure": 0.2, "start_bankroll": 1000.0}

def roi_ci(b):
    x = b["flat_profit"]; return x.mean(), 1.96 * x.std(ddof=1) / np.sqrt(len(x)) if len(x) > 1 else np.nan

def summarize(b, by):
    rows = []
    for k, g in b.groupby(by, observed=True):
        m, ci = roi_ci(g); nb = g[~g.push]
        rows.append({**dict(zip(by if isinstance(by, list) else [by], k if isinstance(k, tuple) else [k])),
                     "n": len(g), "hit": round(nb.won.mean(), 3), "flat_roi": round(m, 3), "ci95": round(ci, 3),
                     "avg_edge": round(g.edge.mean(), 3)})
    return pd.DataFrame(rows)

p = add_probs(pr, 0.5)
b = select_bets(p, DP)
bb, curve = simulate_bankroll(b, DP)
m, ci = roi_ci(b)
print(f"REPRO diagnostic policy: n={len(b)} overs={int((b.side=='over').sum())} unders={int((b.side=='under').sum())} "
      f"hit={b[~b.push].won.mean():.4f} flat ROI={m:.4f} ± {ci:.4f}; bankroll -> {curve.bankroll.iloc[-1]:.1f}")
print("pushes:", int(b.push.sum()))
# significance
from scipy import stats
t = stats.ttest_1samp(b.flat_profit, 0); print(f"t-test flat ROI vs 0: t={t.statistic:.2f} p={t.pvalue:.3f}")
be = (1 / b["dec"]).mean(); nb = b[~b.push]
print(f"avg breakeven win prob at actual prices={be:.4f}; binom p(hit>=obs | p=breakeven)={stats.binomtest(int(nb.won.sum()), len(nb), be, alternative='greater').pvalue:.3f}")
# week-block and game-cluster bootstrap
rng = np.random.default_rng(0)
for key in ["week", "game_id"]:
    g = b.groupby(key).flat_profit.agg(["sum", "size"])
    idx = rng.integers(0, len(g), (10000, len(g)))
    r = g["sum"].values[idx].sum(1) / g["size"].values[idx].sum(1)
    print(f"cluster bootstrap by {key} ({len(g)} clusters): 95% CI [{np.quantile(r,.025):.3f}, {np.quantile(r,.975):.3f}], P(ROI>0)={np.mean(r>0):.3f}")

print("\n== by market x side ==");      print(summarize(b, ["market", "side"]).to_string(index=False))
print("\n== by market ==");             print(summarize(b, ["market"]).to_string(index=False))
print("\n== by side ==");               print(summarize(b, ["side"]).to_string(index=False))
b["edge_bucket"] = pd.cut(b.edge, [0.04, 0.05, 0.06, 0.08, 0.10, 1.0], right=False)
print("\n== by edge bucket (edge after 0.5 blend) =="); print(summarize(b, ["edge_bucket"]).to_string(index=False))
print("\n== by edge bucket x side =="); print(summarize(b, ["edge_bucket", "side"]).to_string(index=False))
b["month"] = pd.cut(b.week, [0, 4, 8, 13], labels=["wk1-4", "wk5-8", "wk9-13"])
print("\n== by week block =="); print(summarize(b, ["month"]).to_string(index=False))

# exposure / correlation
print("\n== exposure ==")
print("bets per game: mean %.2f max %d" % (b.groupby("game_id").size().mean(), b.groupby("game_id").size().max()))
tg = b.groupby(["game_id", "team"]).agg(n=("side", "size"), unders=("side", lambda s: (s == "under").sum()))
print("team-games with >=2 bets:", int((tg.n >= 2).sum()), "of", len(tg), "; of those all-same-side(under):", int(((tg.n >= 2) & (tg.unders == tg.n)).sum()))
qb = b[b.market == "pass_yds"][["game_id", "team", "side"]]
rec = b[b.market == "rec_yds"][["game_id", "team", "side"]]
j = qb.merge(rec, on=["game_id", "team"], suffixes=("_qb", "_rec"))
print("QB pass bet + same-team rec bet pairs:", len(j), "; same side:", int((j.side_qb == j.side_rec).sum()))
pp = b.groupby(["player_id", "game_id"]).size(); print("player-games with 2 bets (rush+rec same player):", int((pp >= 2).sum()))
b.drop(columns=["edge_bucket","month"]).to_pickle("/workspace/tester1-review/out/diag_bets_2025.pkl")

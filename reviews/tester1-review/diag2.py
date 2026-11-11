"""Base rates, calibration, under-lean source, blend/shrink sweeps on the 2025 real-line holdout (IN-SAMPLE for any choice of w)."""
import sys, numpy as np, pandas as pd
sys.path.insert(0, "/workspace/nfl-props/src")
from nflprops.betting import add_probs, select_bets, american_to_decimal
from nflprops.metrics import _ll
pd.set_option("display.width", 220); pd.set_option("display.max_columns", 30)
pr = pd.read_parquet("/workspace/nfl-props/data/cache/preds/preds_04cd0d349a_2025.parquet")
p = add_probs(pr, 0.0)
np_ = p[~p.push].copy()
print("priced lines:", len(p), "pushes:", int(p.push.sum()))
print("\n== base rates on ALL priced lines (no pushes) ==")
rows = []
for mk, g in list(np_.groupby("market")) + [("ALL", np_)]:
    dec_o, dec_u = american_to_decimal(g.over_price), american_to_decimal(g.under_price)
    roi_u = np.where(g.over_hit == 0, dec_u - 1, -1).mean(); roi_o = np.where(g.over_hit == 1, dec_o - 1, -1).mean()
    rows.append({"market": mk, "n": len(g), "obs_over_rate": g.over_hit.mean(), "mean_p_mkt_over(novig)": g.p_mkt_over.mean(),
                 "mean_p_model_over": g.p_over_model.mean(), "always_under_roi": roi_u, "always_over_roi": roi_o,
                 "mean(actual-line)": (g.actual - g.line).mean(), "median(actual-line)": (g.actual - g.line).median(),
                 "mean(mu-line)": (g.mu - g.line).mean(), "median(mu-line)": (g.mu - g.line).median(),
                 "share mu>line": (g.mu > g.line).mean(), "share p_model<0.5": (g.p_over_model < 0.5).mean(),
                 "LL model": _ll(g.p_over_model, g.over_hit).mean(), "LL mkt": _ll(g.p_mkt_over, g.over_hit).mean(),
                 "MAE mu": (g.mu - g.actual).abs().mean(), "MAE line": (g.line - g.actual).abs().mean()})
print(pd.DataFrame(rows).round(4).T.to_string())
# always-under CI
g = np_; dec_u = american_to_decimal(g.under_price); x = np.where(g.over_hit == 0, dec_u - 1, -1)
print(f"\nalways-under ALL: ROI {x.mean():.4f} ± {1.96*x.std(ddof=1)/np.sqrt(len(x)):.4f} (n={len(x)})")

print("\n== when mu > line, how often does the model still say under (skew handling)? ==")
for mk, g in np_.groupby("market"):
    a = g[g.mu > g.line]
    print(f"{mk}: rows mu>line={len(a)}, of which p_model_over<0.5: {(a.p_over_model<0.5).mean():.3f}; overall obs over-rate when mu>line: {a.over_hit.mean():.3f}; when mu<=line: {g[g.mu<=g.line].over_hit.mean():.3f}")

print("\n== reliability: raw model P(over) vs observed (all markets) ==")
np_["bin"] = pd.cut(np_.p_over_model, [0, .3, .4, .45, .5, .55, .6, .7, 1])
print(np_.groupby("bin", observed=True).agg(n=("over_hit", "size"), pred=("p_over_model", "mean"), mkt=("p_mkt_over", "mean"), obs=("over_hit", "mean")).round(3).to_string())
np_["dbin"] = pd.cut(np_.p_over_model - np_.p_mkt_over, [-1, -.15, -.08, -.04, 0, .04, .08, .15, 1])
print("\n== model minus market P(over) (disagreement) vs observed minus market ==")
print(np_.groupby("dbin", observed=True).agg(n=("over_hit", "size"), model_minus_mkt=("p_over_model", "mean"), mkt=("p_mkt_over", "mean"), obs=("over_hit", "mean")).assign(obs_minus_mkt=lambda d: d.obs - d.mkt).round(3).to_string())

print("\n== logistic recalibration (IN-SAMPLE 2025): logit(over) ~ a + b*logit(p_mkt) + c*logit(p_model) ==")
import statsmodels.api as sm
lg = lambda q: np.log(np.clip(q, 1e-4, 1-1e-4) / (1 - np.clip(q, 1e-4, 1-1e-4)))
X = sm.add_constant(np.column_stack([lg(np_.p_mkt_over), lg(np_.p_over_model)]))
r = sm.Logit(np_.over_hit.values, X).fit(disp=0); print(r.summary2().tables[1].round(4).to_string())
for mk, g in np_.groupby("market"):
    X = sm.add_constant(np.column_stack([lg(g.p_mkt_over), lg(g.p_over_model)]))
    rr = sm.Logit(g.over_hit.values, X).fit(disp=0)
    print(f"  {mk}: const={rr.params[0]:.3f} b_mkt={rr.params[1]:.3f} c_model={rr.params[2]:.3f} (se {rr.bse[2]:.3f}, p={rr.pvalues[2]:.3f})")

print("\n== probability blend sweep: p = w*model + (1-w)*market  [IN-SAMPLE on 2025 holdout] ==")
rows = []
for w in [0, .1, .2, .3, .5, .75, 1.0]:
    q = add_probs(pr, 1 - w); qq = q[~q.push]
    d = {"w_model": w, "LL": _ll(qq.p_over, qq.over_hit).mean(), "LL_mkt": _ll(qq.p_mkt_over, qq.over_hit).mean(),
         "Brier": ((qq.p_over - qq.over_hit) ** 2).mean()}
    for thr in [0.02, 0.03, 0.04]:
        b = select_bets(q, {"edge_threshold": thr})
        d[f"n@{thr}"] = len(b); d[f"roi@{thr}"] = b.flat_profit.mean() if len(b) else np.nan
        d[f"under%@{thr}"] = (b.side == "under").mean() if len(b) else np.nan
    rows.append(d)
print(pd.DataFrame(rows).round(4).to_string(index=False))

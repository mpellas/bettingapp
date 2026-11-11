import sys, pickle, numpy as np, pandas as pd
sys.path.insert(0, "/workspace/nfl-props/src")
from nflprops.betting import add_probs, select_bets, no_vig_over
from nflprops.metrics import _ll
from scipy.stats import norm
pd.set_option("display.width", 220); pd.set_option("display.max_columns", 30)
Z = pickle.load(open("out/zfits.pkl", "rb"))
def F(zs, z):
    n = len(zs); return np.interp(z, zs, (np.arange(1, n + 1) - 0.5) / n, left=0.0, right=1.0)
real = pd.read_parquet("/workspace/nfl-props/data/cache/preds/preds_04cd0d349a_2025.parquet")
r = real[real.line.notna()].copy()
r["p_mkt"] = no_vig_over(r.over_price, r.under_price); r["y"] = (r.actual > r.line).astype(float)
def ll(p, y=None): return float(_ll(np.clip(p, 1e-4, 1-1e-4), r.y if y is None else y).mean())
def bets(p, thr=0.04, mask=None):
    q = r.assign(p_over_model=p)
    if mask is not None: q = q[mask]
    b = select_bets(add_probs(q, 0.0), {"edge_threshold": thr}); return len(b), (b.flat_profit.mean() if len(b) else np.nan)
def blend(p, w): return w * p + (1 - w) * r.p_mkt
print(f"baseline: LL model {ll(r.p_over_model):.4f}  LL mkt {ll(r.p_mkt):.4f}")

# (A) OOS mean recalibration: actual ~ a + b*mu fitted on walk-forward 2019-2024 (no 2025 info), applied to 2025
pp = pd.concat([pd.read_parquet(f"/workspace/nfl-props/data/cache/preds/preds_63785e6609_{s}.parquet") for s in range(2019, 2025)])
pA = np.zeros(len(r)); coef = {}
for mk in ["pass_yds", "rush_yds", "rec_yds"]:
    g = pp[pp.market == mk]; b_, a_ = np.polyfit(g.mu, g.actual, 1); coef[mk] = (round(a_, 2), round(b_, 3))
    m = (r.market == mk).values
    mu2 = a_ + b_ * r.mu.values[m]
    pA[m] = 1 - F(Z[(2025, mk)]["z_sorted"], (r.line.values[m] - mu2) / r.s.values[m])
print("\n(A) OOS linear recalibration of mu (fit 2019-24 walk-forward: actual = a + b*mu):", coef)
print(f"    LL raw {ll(pA):.4f}; blended w=0.3 {ll(blend(pA,.3)):.4f} (vs baseline w=0.3 {ll(blend(r.p_over_model,.3)):.4f}); bets@4% raw {bets(pA)}, w=.5 {bets(blend(pA,.5))}")

# (B) normal residual instead of empirical (same mu, s)
pB = 1 - norm.cdf((r.line - r.mu) / r.s, scale=np.sqrt(np.pi / 2))
print(f"\n(B) symmetric normal residual: LL raw {ll(pB):.4f}, w=0.3 {ll(blend(pB,.3)):.4f}; mean P(over) {pB.mean():.3f} vs empirical {r.p_over_model.mean():.3f} vs obs {r.y.mean():.3f}; bets@4% w=.5 {bets(blend(pB,.5))}, under share:",
      round((select_bets(add_probs(r.assign(p_over_model=blend(pB,.5)),0), {'edge_threshold':.04}).side=='under').mean(),3))

# (C) conditional Z by training-mu tercile (shape/scale varies with projection level); z from TRAINING OOF only => OOS for 2025
pC = np.zeros(len(r))
for mk in ["pass_yds", "rush_yds", "rec_yds"]:
    t = Z[(2025, mk)]["train"]; edges = np.quantile(t.oof, [1/3, 2/3])
    tb = np.digitize(t.oof, edges); m = (r.market == mk).values; rb = np.digitize(r.mu.values[m], edges)
    zz = (r.line.values[m] - r.mu.values[m]) / r.s.values[m]; out = np.zeros(m.sum())
    for k in range(3):
        zs = np.sort(np.clip(t.z.values[tb == k], -8, 8)); out[rb == k] = 1 - F(zs, zz[rb == k])
    pC[m] = out
print(f"\n(C) Z conditional on projection tercile: LL raw {ll(pC):.4f}, w=0.3 {ll(blend(pC,.3)):.4f}; bets@4% w=.5 {bets(blend(pC,.5))}")

# (D) shrink the model MEDIAN toward the line: med' = line + k*(med - line)  [IN-SAMPLE]
print("\n(D) shrink model median toward line, k = weight on model [IN-SAMPLE 2025]:")
for k in [1.0, .75, .5, .35, .25, .1]:
    pD = np.zeros(len(r))
    for mk in ["pass_yds", "rush_yds", "rec_yds"]:
        zs = Z[(2025, mk)]["z_sorted"]; m = (r.market == mk).values; zmed = np.median(zs)
        med = r.mu.values[m] + r.s.values[m] * zmed; med2 = r.line.values[m] + k * (med - r.line.values[m])
        pD[m] = 1 - F(zs, (r.line.values[m] - (med2 - r.s.values[m] * zmed)) / r.s.values[m])
    print(f"   k={k:<5} LL {ll(pD):.4f}  bets@4% {bets(pD)}")

# (E) per-market blend weight [IN-SAMPLE] + pseudo-OOS: choose w on weeks 1-6, evaluate weeks 7-13
print("\n(E) per-market LL by model weight w [IN-SAMPLE 2025]:")
ws = [0, .1, .2, .3, .4, .5, .75, 1]
tab = {mk: [float(_ll(blend(r.p_over_model, w)[r.market == mk], r.y[r.market == mk]).mean()) for w in ws] for mk in ["pass_yds", "rush_yds", "rec_yds"]}
print(pd.DataFrame(tab, index=ws).round(4).T.to_string())
early, late = r.week <= 6, r.week > 6
grid = np.round(np.arange(0, 1.01, .05), 2)
ll_e = [float(_ll(blend(r.p_over_model, w)[early], r.y[early]).mean()) for w in grid]; w_star = grid[int(np.argmin(ll_e))]
for nm, w in [("w chosen on wk1-6", w_star), ("w=0 (pure market)", 0.0), ("w=0.5 (diagnostic)", .5), ("w=1 (raw)", 1.0)]:
    p = blend(r.p_over_model, w); n, roi = bets(p, .04, late.values)
    print(f"   pseudo-OOS wk7-13 | {nm:<20} w={w:.2f}: LL {float(_ll(p[late], r.y[late]).mean()):.4f} (mkt {float(_ll(r.p_mkt[late], r.y[late]).mean()):.4f}); bets@4% n={n} roi={roi if n else float('nan'):.3f}")
# same with per-market w
pm = np.array(r.p_mkt); pl = np.zeros(len(r))
for mk in ["pass_yds", "rush_yds", "rec_yds"]:
    m = (r.market == mk).values
    l = [float(_ll((w * r.p_over_model + (1 - w) * r.p_mkt)[m & early.values], r.y[m & early.values]).mean()) for w in grid]
    w_mk = grid[int(np.argmin(l))]; pl[m] = w_mk * r.p_over_model.values[m] + (1 - w_mk) * pm[m]; print(f"   per-market w on wk1-6: {mk} -> {w_mk}")
n, roi = bets(pl, .04, late.values); print(f"   pseudo-OOS wk7-13 per-market w: LL {float(_ll(pl[late.values], r.y[late]).mean()):.4f}; bets@4% n={n} roi={roi:.3f}")

# (F) open -> 'current' line movement (CAVEAT: ESPN 'current' for finished events = last listed value, timestamps post-kickoff)
cu = pd.read_csv("/workspace/nfl-props/data/lines/espn_current.csv", dtype={"player_id": str})
m = r.merge(cu[["season", "week", "player_id", "market", "line"]].rename(columns={"line": "line_cur"}), on=["season", "week", "player_id", "market"])
print(f"\n(F) ESPN open vs 'current' on {len(m)} matched holdout lines: MAE open {np.abs(m.line-m.actual).mean():.2f}, MAE current {np.abs(m.line_cur-m.actual).mean():.2f}; share moved {(m.line!=m.line_cur).mean():.3f}")
b = pd.read_pickle("out/diag_bets_2025.pkl").merge(cu[["season", "week", "player_id", "market", "line"]].rename(columns={"line": "line_cur"}), on=["season", "week", "player_id", "market"], how="left")
mv = np.where(b.side == "under", b.line - b.line_cur, b.line_cur - b.line)  # + = moved in our favour
print(f"    diagnostic bets with a current line: {b.line_cur.notna().sum()}/{len(b)}; moved our way {np.mean(mv[~np.isnan(mv)]>0):.3f}, against {np.mean(mv[~np.isnan(mv)]<0):.3f}, mean move {np.nanmean(mv):+.2f} yds")
for side in ["over", "under"]:
    x = mv[(b.side == side).values]; x = x[~np.isnan(x)]; print(f"     {side}: n={len(x)} our-way {np.mean(x>0):.3f} against {np.mean(x<0):.3f} mean {x.mean():+.2f}")
# placebo: all lines, did current move down (toward under) on average?
print(f"    all holdout lines: mean(current-open) {(m.line_cur-m.line).mean():+.2f} yds; share down {(m.line_cur<m.line).mean():.3f}, up {(m.line_cur>m.line).mean():.3f}")

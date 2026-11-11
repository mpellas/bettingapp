"""Q1: can a bettor extract the simulator's CONSTRUCTION (not football skill) from simulated lines?"""
import sys, numpy as np, pandas as pd, statsmodels.api as sm, lightgbm as lgb
sys.path.insert(0, "/workspace/tester1-review/v2/proj/src")
from nflprops.betting import add_probs, select_bets
from nflprops.metrics import _ll
pd.set_option("display.width", 220); pd.set_option("display.max_columns", 40)
S = add_probs(pd.read_pickle("out/frame_sim.pkl"), 0.0); R = add_probs(pd.read_pickle("out/frame_real.pkl"), 0.0)
S, R = S[~S.push].copy(), R[~R.push].copy()
def feats(d):
    sc = d.s.clip(lower=5)
    return pd.DataFrame({"line_minus_base": (d.line - d.base) / sc, "ref_minus_cpub": (d.ref_med - d.c * d.mkt_proj) / sc,
                         "line_minus_ref": (d.line - d.ref_med) / sc, "line_minus_cpub": (d.line - d.c * d.mkt_proj) / sc}, index=d.index)
for d in (S, R): d[list(feats(d).columns)] = feats(d)
lg = lambda p: np.log(np.clip(p, 1e-4, 1 - 1e-4) / (1 - np.clip(p, 1e-4, 1 - 1e-4)))

print("== over-rate on SIMULATED lines by market x season (a constant bias = free edge for 'always under/over') ==")
print(S.pivot_table(index="season", columns="market", values="over_hit", aggfunc="mean").round(3).to_string())
print("real 2025:", R.groupby("market").over_hit.mean().round(3).to_dict())

def bet_eval(d, p, thr=0.04):
    b = select_bets(d.assign(p_over=p), {"edge_threshold": thr})
    if len(b) == 0: return 0, np.nan, np.nan
    return len(b), b[~b.push].won.mean(), b.flat_profit.mean()

print("\n== T1: structure-only decoders (inputs: line, ref_med, c*pub — all replicable pre-game; NO model of football) ==")
X1 = ["ref_minus_cpub", "line_minus_ref"]
rows = []
for mk in ["pass_yds", "rush_yds", "rec_yds"]:
    tr = S[(S.market == mk) & (S.season <= 2022)]
    lr = sm.Logit(tr.over_hit, sm.add_constant(tr[X1])).fit(disp=0)
    gb = lgb.LGBMClassifier(n_estimators=200, learning_rate=0.03, num_leaves=7, min_child_samples=200, verbose=-1, random_state=0)
    XG = ["line", "ref_med", "mkt_proj", "base", "line_minus_base", "ref_minus_cpub", "line_minus_ref", "s"]
    gb.fit(tr[XG], tr.over_hit)
    for nm, te in [("sim 2023-24", S[(S.market == mk) & S.season.between(2023, 2024)]), ("sim 2025", S[(S.market == mk) & (S.season == 2025)]),
                   ("REAL 2025", R[R.market == mk])]:
        pl = lr.predict(sm.add_constant(te[X1], has_constant="add")); pg = gb.predict_proba(te[XG])[:, 1]
        for dn, p in [("logit", pl), ("lgbm", pg)]:
            n, hit, roi = bet_eval(te, p)
            rows.append({"market": mk, "decoder": dn, "test": nm, "n": len(te), "LL dec": _ll(p, te.over_hit).mean(),
                         "LL mkt": _ll(te.p_mkt_over, te.over_hit).mean(), "bets@4%": n, "hit": hit, "flat ROI": roi})
    print(f"  {mk} logit coefs (train sim 2019-22): " + ", ".join(f"{k}={v:.3f} (z={lr.tvalues[k]:.1f})" for k, v in lr.params.items()))
T1 = pd.DataFrame(rows); T1["LL gain"] = T1["LL mkt"] - T1["LL dec"]
print(T1.round(4).to_string(index=False))
T1.to_csv("out/T1_structure_decoders.csv", index=False)

print("\n== T2: does the model's sim edge survive controlling for the simulator's structure? logit(over) ~ logit(p_model) [+ structure] ==")
rows = []
for nm, d in [("sim 2019-24", S[S.season <= 2024]), ("sim 2025", S[S.season == 2025]), ("REAL 2025", R)]:
    for mk in ["pass_yds", "rush_yds", "rec_yds"]:
        g = d[d.market == mk]
        a = sm.Logit(g.over_hit, sm.add_constant(pd.DataFrame({"lpm": lg(g.p_over_model)}, index=g.index))).fit(disp=0)
        Xb = pd.DataFrame({"lpm": lg(g.p_over_model), "ref_minus_cpub": g.ref_minus_cpub, "line_minus_ref": g.line_minus_ref}, index=g.index)
        b = sm.Logit(g.over_hit, sm.add_constant(Xb)).fit(disp=0)
        rows.append({"data": nm, "market": mk, "n": len(g), "c_model alone": a.params["lpm"], "z": a.tvalues["lpm"],
                     "c_model | structure": b.params["lpm"], "z|s": b.tvalues["lpm"], "coef ref_minus_cpub": b.params["ref_minus_cpub"],
                     "z_rc": b.tvalues["ref_minus_cpub"], "coef line_minus_ref": b.params["line_minus_ref"], "z_lr": b.tvalues["line_minus_ref"]})
print(pd.DataFrame(rows).round(3).to_string(index=False))

print("\n== T2b: same player-games, sim line vs real line (2025 overlap): model weight c (plain logit) ==")
k = ["player_id", "game_id", "market"]
o = S[S.season == 2025].merge(R[k + ["line", "p_over_model", "over_hit", "p_mkt_over"]], on=k, suffixes=("_sim", "_real"))
for mk, g in o.groupby("market"):
    cs = sm.Logit(g.over_hit_sim, sm.add_constant(lg(g.p_over_model_sim))).fit(disp=0)
    cr = sm.Logit(g.over_hit_real, sm.add_constant(np.column_stack([lg(g.p_mkt_over_real), lg(g.p_over_model_real)]))).fit(disp=0)
    print(f"  {mk}: n={len(g)}  c vs SIM line={cs.params.iloc[1]:.3f} (z {cs.tvalues.iloc[1]:.1f}); c vs REAL line={cr.params.iloc[2]:.3f} (z {cr.tvalues.iloc[2]:.1f}); "
          f"LL gain raw model vs mkt: sim {(_ll(g.p_mkt_over_sim if 'p_mkt_over_sim' in g else 0.5, g.over_hit_sim) - _ll(g.p_over_model_sim, g.over_hit_sim)).mean():+.4f}, real {(_ll(g.p_mkt_over_real, g.over_hit_real) - _ll(g.p_over_model_real, g.over_hit_real)).mean():+.4f}")

print("\n== T3: within-season staleness — model raw LL gain vs market by week block ==")
for nm, d in [("sim 2019-24", S[S.season <= 2024]), ("REAL 2025", R)]:
    d = d.assign(blk=pd.cut(d.week, [0, 4, 8, 12, 18], labels=["1-4", "5-8", "9-12", "13-18"]))
    t = d.groupby(["blk", "market"], observed=True).apply(lambda g: pd.Series({"n": len(g), "gain_raw": (_ll(g.p_mkt_over, g.over_hit) - _ll(g.p_over_model, g.over_hit)).mean()}), include_groups=False)
    print(nm); print(t.unstack("market").round(4).to_string())

print("\n== T4: what does the REAL market put on the reference model vs the naive public projection? (2025 overlap; ENVIRONMENT diagnostic) ==")
for mk, g in R.groupby("market"):
    X = sm.add_constant(pd.DataFrame({"ref_med": g.ref_med, "c_pub": g.c * g.mkt_proj, "model_median_proxy": g.mu}, index=g.index))
    r1 = sm.OLS(g.line, sm.add_constant(pd.DataFrame({"ref_med": g.ref_med, "c_pub": g.c * g.mkt_proj}, index=g.index))).fit()
    w = r1.params; print(f"  {mk}: real_line = {w['const']:.1f} + {w['ref_med']:.3f}*ref_med + {w['c_pub']:.3f}*c*pub  (R2 {r1.rsquared:.3f});  implied ref_share = {w['ref_med']/(w['ref_med']+w['c_pub']):.2f}")
    gs = S[(S.season == 2025) & (S.market == mk)]
    r2 = sm.OLS(gs.line, sm.add_constant(pd.DataFrame({"ref_med": gs.ref_med, "c_pub": gs.c * gs.mkt_proj}, index=gs.index))).fit()
    print(f"         sim_line  = {r2.params['const']:.1f} + {r2.params['ref_med']:.3f}*ref_med + {r2.params['c_pub']:.3f}*c*pub (R2 {r2.rsquared:.3f})")

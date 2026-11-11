"""Reproduce the frozen 2025 holdout (18 bets, -6.7%) in a COPY of the project (all writes go to v2/proj)."""
import sys, json, numpy as np, pandas as pd, yaml
sys.path.insert(0, "/workspace/tester1-review/v2/proj/src")
from nflprops import ROOT
assert str(ROOT).startswith("/workspace/tester1-review/"), ROOT
from nflprops.holdout import policy_bc, score, policy_sha1
from nflprops.config import deep_update
from nflprops.backtest import walk_forward, pred_key
from nflprops.metrics import evaluate
from nflprops.features import load_features
pol = yaml.safe_load(open(ROOT / "configs/holdout_policy.yaml"))
st = json.load(open(ROOT / "experiments/champion.json")); cfg = st["champion"]
print("policy sha1", policy_sha1())
bc = policy_bc(cfg, pol)
rc = deep_update(cfg, {"lines": {"source": "csv", "csv_path": "/workspace/nfl-props/" + pol["primary"]["line_source"]}})  # builder's exact string => same cache key; file only READ
print("real-line pred key", pred_key(rc))
cached = walk_forward(rc, [2025])                       # from cache
ev = evaluate(cached, bc); r = score(ev)
b = ev["_bets"]
print(f"CACHED: lines {r['n_lines']} bets {r['n_bets']} hit {r['hit_rate']} flat ROI {r['flat_roi']:.4f} CI {r['roi_ci95_game_clustered']} bankroll {r['final_bankroll']:.1f}")
print("by market bets:", b.groupby("market").size().to_dict(), "first bettable week", r["first_bettable_week_by_market"])
print("coefs last", r["stacker_coefs_last"])
print("LL gain stacked", r["ll_gain_stacked_vs_market"], "raw", r["ll_gain_raw_vs_market"])
fz = json.load(open(ROOT / "experiments/holdout_frozen.json"))["real_espn_uncertain_timing"]
print("FROZEN file: bets", fz["n_bets"], "roi", fz["flat_roi"], "ci", fz["roi_ci95_game_clustered"])
b.drop(columns=[c for c in b.columns if str(b[c].dtype) == "category"]).to_pickle("out/holdout_bets_18.pkl")
ev["_p"].to_pickle("out/holdout_p_real.pkl"); ev["_coefs"].to_pickle("out/holdout_coefs_real.pkl")
# fresh recompute (no cache) to check determinism
feats = load_features(cfg["data"]["first_season"], cfg["data"]["last_season"])
fresh = walk_forward(rc, [2025], feats, use_cache=False)
k = ["player_id", "game_id", "market"]
m = cached.merge(fresh, on=k, suffixes=("_c", "_f"))
print("FRESH vs cached: rows", len(cached), len(fresh), "max|dmu|", float((m.mu_c - m.mu_f).abs().max()),
      "max|dp|", float((m.p_over_model_c - m.p_over_model_f).abs().max(skipna=True)))
ev2 = evaluate(fresh, bc); print("FRESH bets", ev2["overall"]["n_bets"], "roi", round(ev2["overall"]["flat_roi"], 4))
print(b[["week", "market", "player_display_name", "side", "line", "actual", "edge", "won", "flat_profit"]].sort_values("week").to_string(index=False))

"""How the 0.0005 promotion margin interacts with market_blend=0.9: recompute champion-vs-challenger selection-season
log-loss gain on the builder's cached (simulated-line) predictions at several blends."""
import sys, json, numpy as np, pandas as pd
sys.path.insert(0, "/workspace/nfl-props/src")
from nflprops.betting import add_probs
from nflprops.metrics import _ll
runs = [json.loads(l) for l in open("/workspace/nfl-props/experiments/runs.jsonl")]
ch = [(r["iteration"], r["config_hash"], r["changes"], r.get("sel_logloss_gain_vs_champion")) for r in runs if r["role"] == "challenger"]
def load(h): return pd.concat([pd.read_parquet(f"/workspace/nfl-props/data/cache/preds/preds_{h}_{s}.parquet") for s in (2023, 2024)])
A = load("63785e6609")
print("blend used by loop for every run:", sorted({r["betting"]["market_blend"] for r in runs if r.get("betting")}))
for it, h, chg, g_logged in ch:
    B = load(h); row = [f"iter {it} {chg}: logged gain {g_logged:.6f}"]
    for a in [0.9, 0.5, 0.0]:
        pa, pb = add_probs(A, a), add_probs(B, a); pa, pb = pa[~pa.push], pb[~pb.push]
        row.append(f"gain@blend{a}={float(_ll(pa.p_over, pa.over_hit).mean() - _ll(pb.p_over, pb.over_hit).mean()):+.6f}")
    print("  ".join(row))
pa = add_probs(A, 0.0); pa = pa[~pa.push]
print("champion raw (blend 0) selection LL", round(float(_ll(pa.p_over, pa.over_hit).mean()), 5), "vs market", round(float(_ll(pa.p_mkt_over, pa.over_hit).mean()), 5))

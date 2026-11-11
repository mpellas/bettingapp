"""Does the promotion metric (raw LL vs SIMULATED lines) rank configs the same way as projection accuracy (CRPS/MAE on
actuals) and as raw LL vs REAL 2025 lines?  DIAGNOSTIC OF THE METRIC ONLY — uses the frozen 2025 holdout, so these
numbers must not be used to pick a model. Runs in the project COPY."""
import sys, json, numpy as np, pandas as pd
sys.path.insert(0, "/workspace/tester1-review/v2/proj/src")
from nflprops import ROOT
assert str(ROOT).startswith("/workspace/tester1-review/")
from nflprops.backtest import walk_forward
from nflprops.betting import add_probs
from nflprops.metrics import _ll
from nflprops.features import load_features
from scipy.stats import spearmanr
runs = [json.loads(l) for l in open(ROOT / "experiments/runs.jsonl")]
cfgs = {}
for r in runs:
    if r["role"] in ("initial_champion", "candidate") and r["period"] == "validation":
        cfgs.setdefault(r["config_hash"], (r["run_id"], ",".join(r["changes"]) or "initial", r["config"]))
feats = load_features(2015, 2025)
rows = []
for h, (rid, ch, cfg) in cfgs.items():
    val = walk_forward(cfg, [2019, 2020, 2021, 2022], feats)
    sel = walk_forward(cfg, [2023, 2024], feats)
    rc = dict(cfg, lines=dict(cfg["lines"], source="csv", csv_path="/workspace/nfl-props/data/lines/espn_bet_2025_open_uncertain_timing.csv"))
    re = walk_forward(rc, [2025], feats)
    d = {"run": rid, "changes": ch}
    for nm, pr in [("val", val), ("sel", sel), ("real25", re)]:
        p = add_probs(pr, 0.0); p = p[~p.push]
        d[f"{nm}_rawLL"] = float(_ll(p.p_over_model, p.over_hit).mean())
        d[f"{nm}_crps"] = float(pr.crps.mean()); d[f"{nm}_mae"] = float((pr.mu - pr.actual).abs().mean())
    rows.append(d); print(d, flush=True)
T = pd.DataFrame(rows); T.to_csv("out/s2_metric_validity.csv", index=False)
print(T.round(5).to_string(index=False))
pairs = [("val_rawLL", "val_crps"), ("val_rawLL", "sel_rawLL"), ("val_crps", "sel_crps"), ("val_rawLL", "real25_rawLL"),
         ("sel_rawLL", "real25_rawLL"), ("val_crps", "real25_rawLL"), ("sel_crps", "real25_rawLL"), ("val_crps", "real25_crps"), ("val_rawLL", "real25_crps")]
for a, b in pairs:
    r = spearmanr(T[a], T[b]); print(f"spearman({a}, {b}) = {r.correlation:+.3f} (p={r.pvalue:.3f}, n={len(T)})")

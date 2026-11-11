"""Assemble simulated-line (2019-2025) and real-line (2025) frames with the simulator's components (copy of project)."""
import sys, json, numpy as np, pandas as pd
sys.path.insert(0, "/workspace/tester1-review/v2/proj/src")
from nflprops import ROOT
assert str(ROOT).startswith("/workspace/tester1-review/")
from nflprops.features import load_features
from nflprops.reference import attach_reference
from nflprops.lines import calibrate_sim, info_projection
from nflprops.backtest import walk_forward
st = json.load(open(ROOT / "experiments/champion.json")); cfg = st["champion"]
feats = load_features(2015, 2025)
before = set((ROOT / "data/cache").glob("ref_preds_*"))
fr = attach_reference(feats, cfg)
after = set((ROOT / "data/cache").glob("ref_preds_*"))
print("ref cache newly computed?", after - before)
cal = calibrate_sim(fr, cfg); print(json.dumps(cal))
json.dump(cal, open("out/sim_calib.json", "w"))
sim = walk_forward(cfg, list(range(2019, 2026)))
rc = dict(cfg, lines=dict(cfg["lines"], source="csv", csv_path="/workspace/nfl-props/data/lines/espn_bet_2025_open_uncertain_timing.csv"))
real = walk_forward(rc, [2025])
keep = ["player_id", "game_id", "ref_med_pass_yds", "ref_med_rush_yds", "ref_med_rec_yds", "attempts", "carries", "targets",
        "p_ypa", "p_ypc", "p_ypt", "p_attempts_ewm6", "p_carries_ewm6", "p_targets_ewm6", "gameday"]
for name, d in [("sim", sim), ("real", real)]:
    d = d.merge(fr[keep].drop(columns="gameday"), on=["player_id", "game_id"], how="left")
    d["ref_med"] = np.select([d.market == m for m in ["pass_yds", "rush_yds", "rec_yds"]],
                             [d.ref_med_pass_yds, d.ref_med_rush_yds, d.ref_med_rec_yds])
    d["c"] = d.market.map({m: v["c"] for m, v in cal.items()}); d["beta"] = d.market.map({m: v["beta"] for m, v in cal.items()})
    d["base"] = 0.5 * d.ref_med + 0.5 * d.c * d.mkt_proj
    info = pd.Series(np.nan, index=d.index)
    for mk in ["pass_yds", "rush_yds", "rec_yds"]:
        m = d.market == mk; info[m] = info_projection(d[m], mk)
    d["info_d"] = d.c * (info.fillna(d.mkt_proj) - d.mkt_proj)       # the market's NOISELESS signal (uses actual volume)
    d.drop(columns=[c for c in d.columns if c.startswith("ref_med_")]).to_pickle(f"out/frame_{name}.pkl")
    print(name, d.shape, d.line.notna().sum(), "ref_med missing among priced:", int(d[d.line.notna()].ref_med.isna().sum()))

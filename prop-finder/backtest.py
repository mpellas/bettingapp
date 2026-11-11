#!/usr/bin/env python
"""Full-season 2025 walk-forward backtest (NFL weeks 2-18, FBS weeks 2-16) + held-out tuning.

Usage: python backtest.py [--workers 3] [--skip-tuning]
Writes output/backtest_2025/ (report.md, report.html, CSVs). See README 'Backtest' section.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

import numpy as np
import pandas as pd

from prop_finder import analysis, backtest as bt, cfb_context, cfbd

ROOT = Path(__file__).resolve().parent
OUT = ROOT / "output" / "backtest_2025"
TUNE_W, HOLD_W = list(range(2, 10)), list(range(10, 19))
# settings the model had BEFORE this backtest (the "live settings" baseline every comparison is made against);
# the tuned values now in analysis.py are documented in output/backtest_2025/report.md
PRE_BACKTEST = {"W_SEASON": 0.45, "W_L3": 0.35, "W_PRIOR": 0.20, "CFB_W_SEASON": 0.55, "CFB_PRIOR_START": 0.70,
                "CFB_PRIOR_DECAY": 0.13, "CFB_PRIOR_FLOOR": 0.05, "MATCHUP_STRENGTH": 0.6, "ENV_STRENGTH": 1.0,
                "CFB_MATCHUP_STRENGTH": 0.6, "CFB_ENV_STRENGTH": 1.0, "SHRINK_K": 0.4, "SHRINK_K_POISSON": 5.0,
                "P_SHRINK": 0.75, "RANK_SHRINK": 0.75, "AGREE_W": 10.0, "GUARD_FAR_F": 0.35,
                "GUARD_MATE_UNDER_F": 0.35, "GUARD_MISSED_F": 0.6, "GUARD_SMALL_F": 0.6}
BASE = {"analysis": PRE_BACKTEST, "cfb_context": {"BETA": 0.012, "LEVEL_BETA": 0.006}}
G: dict = {}   # fork-shared inputs


def log(*a):
    print(time.strftime("%H:%M:%S"), *a, flush=True)


def apply_cfg(cfg: dict):
    for k, v in BASE["analysis"].items():
        setattr(analysis, k, cfg.get(k, v))
    for k, v in BASE["cfb_context"].items():
        setattr(cfb_context, k, cfg.get(k, v))


def run_cfg(job):
    name, league, cfg = job
    apply_cfg(cfg)
    t = time.time()
    if league == "nfl":
        weeks = G["nfl"]
    else:
        weeks = G["cfb"] if not ({"BETA", "LEVEL_BETA"} & set(cfg)) else bt.prepare_cfb(G["ctx"])[0]
    proj = bt.project(weeks, league)
    apply_cfg({})
    if not name.startswith(("baseline", "combined")):   # grid runs only need projection accuracy columns
        proj = proj[["league", "week", "player_id", "event_id", "stat", "projection", "season_avg", "l5_avg"]]
    return name, league, cfg, proj, round(time.time() - t, 1)


# configurations: one knob at a time from the live settings (coordinate search), tuned on weeks 2-9 only
NFL_GRID = {
    "blend 0.55/0.25/0.20": {"W_SEASON": 0.55, "W_L3": 0.25, "W_PRIOR": 0.20},
    "blend 0.40/0.30/0.30": {"W_SEASON": 0.40, "W_L3": 0.30, "W_PRIOR": 0.30},
    "blend 0.50/0.20/0.30": {"W_SEASON": 0.50, "W_L3": 0.20, "W_PRIOR": 0.30},
    "blend 0.35/0.45/0.20": {"W_SEASON": 0.35, "W_L3": 0.45, "W_PRIOR": 0.20},
    "matchup 0.0": {"MATCHUP_STRENGTH": 0.0}, "matchup 0.3": {"MATCHUP_STRENGTH": 0.3},
    "matchup 1.0": {"MATCHUP_STRENGTH": 1.0},
    "env 0.0": {"ENV_STRENGTH": 0.0}, "env 0.5": {"ENV_STRENGTH": 0.5}, "env 1.5": {"ENV_STRENGTH": 1.5},
    "pos-shrink k=0": {"SHRINK_K": 0.0}, "pos-shrink k=1.5": {"SHRINK_K": 1.5},
}
CFB_GRID = {
    "cfb season/L3 0.40": {"CFB_W_SEASON": 0.40}, "cfb season/L3 0.70": {"CFB_W_SEASON": 0.70},
    "cfb prior fade slower (decay 0.08)": {"CFB_PRIOR_DECAY": 0.08},
    "cfb prior fade faster (decay 0.20)": {"CFB_PRIOR_DECAY": 0.20},
    "cfb no prior (ablation)": {"CFB_PRIOR_START": 0.0, "CFB_PRIOR_FLOOR": 0.0},
    "cfb opp-adj BETA 0 (ablation)": {"BETA": 0.0}, "cfb opp-adj BETA 0.018": {"BETA": 0.018},
    "cfb level-jump off (ablation)": {"LEVEL_BETA": 0.0},
    "matchup 0.0": {"CFB_MATCHUP_STRENGTH": 0.0}, "matchup 1.0": {"CFB_MATCHUP_STRENGTH": 1.0},
    "env 0.0": {"CFB_ENV_STRENGTH": 0.0}, "env 1.5": {"CFB_ENV_STRENGTH": 1.5},
}


def main():
    apply_cfg({})   # evaluate everything relative to the pre-backtest settings
    ap = argparse.ArgumentParser()
    ap.add_argument("--workers", type=int, default=3)
    ap.add_argument("--skip-tuning", action="store_true")
    a = ap.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    work = ROOT / "data" / "backtest"
    work.mkdir(parents=True, exist_ok=True)
    calls0 = cfbd.network_calls_logged()
    log("preparing NFL inputs")
    G["nfl"] = bt.prepare_nfl()
    log("preparing FBS inputs (CFBD, cached)")
    G["ctx"] = cfb_context.Context(bt.SEASON, asof_ratings=True)
    G["cfb"], logs25 = bt.prepare_cfb(G["ctx"])
    logs25[["player_id", "player", "team", "position", "position_inferred"]].drop_duplicates("player_id").to_csv(
        work / "cfb_positions.csv", index=False)
    jobs = [("baseline", "nfl", {}), ("baseline", "ncaaf", {})]
    if not a.skip_tuning:
        jobs += [(n, "nfl", c) for n, c in NFL_GRID.items()] + [(n, "ncaaf", c) for n, c in CFB_GRID.items()]
    results = {}
    with ProcessPoolExecutor(a.workers) as ex:
        for name, league, cfg, proj, secs in ex.map(run_cfg, jobs):
            log(f"projected {league:5s} {name:40s} rows={len(proj):6d} {secs}s")
            proj.drop(columns=["vals_cur", "vals_all"], errors="ignore").to_parquet(
                work / f"proj_{league}_{name.replace(' ', '_').replace('/', '-')}.parquet")
            results[(name, league)] = (cfg, proj)
    pd.to_pickle({"results": results, "cfb_ctx_secs": {W: d["ctx_secs"] for W, d in G["cfb"].items()}},
                 work / "projections.pkl")
    # actuals + small inputs for the analysis stage
    pd.to_pickle({lg: {W: {"actuals": d["actuals"], "n_games": len(d["slate"]),
                           "n_implied": sum(1 for s in d["slate"] if s["home_implied"] is not None),
                           "n_injuries": len(d["injuries"])} for W, d in G[k].items()}
                  for lg, k in (("nfl", "nfl"), ("ncaaf", "cfb"))}, work / "actuals.pkl")
    json.dump({"cfbd_network_calls_this_run": cfbd.network_calls_logged() - calls0}, open(work / "run_meta.json", "w"))
    log("done; now run: python backtest_report.py")


if __name__ == "__main__":
    main()

"""Empirical leakage check (v2: also scrambles schedule / game-level fields — Tester1 B4).

For several cutoff dates D, replace with random values, for every game played on/after D:
  * every player outcome (stats, snap shares), and
  * every game-level field that is only known on/after game day: spread_line, total_line (+ moneylines/odds),
    wind, temp, roof open<->closed status, the actual starting QBs (home_qb_id/away_qb_id), scores/result/total.
Then rebuild all features from scratch and assert every model feature for games on/before D is bit-identical.
A feature for a game on date D that depended on that game's own result, its closing line, its observed weather or
its actual starter would change. Also checks no feature is a near-copy of a target.

    python -m nflprops.leakage            # current features  (must PASS)
    python -m nflprops.leakage --legacy   # v1 features      (must FAIL: proves the test catches the old look-ahead)
"""
from __future__ import annotations

import argparse
import sys

import numpy as np
import pandas as pd

from . import data
from .features import FEATURE_GROUPS, SNAP_COLS, TARGETS, build_features

PS_NUM = ["completions", "attempts", "passing_yards", "passing_air_yards", "sacks_suffered", "passing_epa",
          "carries", "rushing_yards", "rushing_epa", "receptions", "targets", "receiving_yards",
          "receiving_air_yards", "receiving_epa", "target_share", "air_yards_share", "wopr"]
SCHED_NUM = ["spread_line", "total_line", "wind", "temp", "home_score", "away_score", "result", "total",
             "away_moneyline", "home_moneyline", "away_spread_odds", "home_spread_odds", "under_odds", "over_odds"]


def all_feats(groups=FEATURE_GROUPS, snap_cols=SNAP_COLS):
    return sorted({c for g in groups.values() for c in g} | set(snap_cols)
                  | {f"mkt_proj_{m}" for m in TARGETS} | {f"naive_{m}" for m in TARGETS})


def scramble_after(d: dict, cutoff: pd.Timestamp, seed: int = 0) -> dict:
    rng = np.random.default_rng(seed)
    out = dict(d)
    sched = d["schedules"].copy()
    gdt = pd.to_datetime(sched["gameday"])
    gd = dict(zip(sched["game_id"], gdt))
    ms = (gdt >= cutoff).values
    for c in SCHED_NUM:
        if c in sched:
            sched.loc[ms, c] = rng.normal(20, 15, ms.sum()).round(1)
    # game-day roof status: swap open <-> closed (dome/outdoors are static stadium attributes)
    r = sched.loc[ms, "roof"]
    sched.loc[ms, "roof"] = np.where(r == "open", "closed", np.where(r == "closed", "open", r))
    # actual starting QBs: replace with a random QB id from the whole table
    pool = pd.concat([sched["home_qb_id"], sched["away_qb_id"]]).dropna().unique()
    for c in ("home_qb_id", "away_qb_id"):
        sched.loc[ms, c] = rng.choice(pool, ms.sum())
    out["schedules"] = sched
    ps = d["player_stats"].copy()
    m = (ps["game_id"].map(gd) >= cutoff).values
    for c in PS_NUM:
        if c in ps:
            ps.loc[m, c] = rng.normal(50, 40, m.sum()).round()
    out["player_stats"] = ps
    sn = d["snap_counts"].copy()
    m2 = (sn["game_id"].map(gd) >= cutoff).values
    sn.loc[m2, "offense_pct"] = rng.uniform(0, 1, m2.sum())
    out["snap_counts"] = sn
    return out


def _same(a: pd.DataFrame, b: pd.DataFrame) -> pd.DataFrame:
    return (a == b) | (a.isna() & b.isna())


def run(first=2015, last=2025, cutoffs=("2019-11-10", "2022-09-11", "2024-12-22"), legacy=False) -> bool:
    if legacy:
        from .legacy import features_v1 as L
        builder, feats_list = L.build_features, all_feats(L.FEATURE_GROUPS, L.SNAP_COLS)
        print("== LEGACY v1 features (expected to FAIL) ==")
    else:
        builder, feats_list = build_features, all_feats()
        print("== current features ==")
    d = data.load(first, last)
    base = builder(d).set_index(["player_id", "game_id"])
    ok = True
    for c in cutoffs:
        cut = pd.Timestamp(c)
        alt = builder(scramble_after(d, cut)).set_index(["player_id", "game_id"])
        rows = base.index[base["gameday"] <= cut].intersection(alt.index)
        diff = ~_same(base.loc[rows, feats_list], alt.loc[rows, feats_list])
        n_bad = int(diff.values.sum())
        on_day = int((base.loc[rows, "gameday"] == cut).sum())
        later = base.index[base["gameday"] > cut + pd.Timedelta(days=7)].intersection(alt.index)
        changed_later = int((~_same(base.loc[later, feats_list], alt.loc[later, feats_list])).values.sum())
        status = "PASS" if n_bad == 0 and changed_later > 0 else "FAIL"
        ok &= status == "PASS"
        print(f"[{status}] cutoff {c}: {len(rows):,} rows checked ({on_day} on the cutoff day itself), "
              f"{n_bad} feature values changed; post-cutoff feature values changed by scramble: {changed_later:,}")
        if n_bad:
            bad = diff.sum()
            print("   offending columns:", {k: int(v) for k, v in bad[bad > 0].sort_values(ascending=False).items()})
    for mk, stat in TARGETS.items():
        cors = base[feats_list].corrwith(base[stat]).abs().sort_values(ascending=False)
        flag = cors.iloc[0] > 0.95
        ok &= not flag
        print(f"[{'FAIL' if flag else 'PASS'}] max |corr(feature, {stat})| = {cors.iloc[0]:.3f} ({cors.index[0]})")
    print("OVERALL:", "PASS" if ok else "FAIL")
    return ok


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--legacy", action="store_true")
    a = ap.parse_args()
    res = run(legacy=a.legacy)
    sys.exit(0 if res else 1)

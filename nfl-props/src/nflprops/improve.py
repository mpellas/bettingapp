"""Experiment loop, v3 rule (after Tester1's second review, N1/N6): promotion on PROJECTION ACCURACY, no lines.

Simulated lines are learnable (Tester1 N1: a decoder of the line recipe alone beats them), so they are no longer
used for promotion or for any betting-policy tuning. The simulator stays available only as an optional diagnostic
(`lines.source: simulated` + `python -m nflprops.run_backtest`). The loop:
  1. proposes N candidate configs by mutating 1-2 knobs of the champion (seeded, reproducible);
  2. walk-forwards each candidate on the VALIDATION seasons (2019-2022) with `lines.source: none` and scores the
     predictive distribution against ACTUAL yards: CRPS (primary), MAE, PIT calibration;
       score = per-market relative CRPS gain vs the champion, (CRPS_champ - CRPS_cand) / mean CRPS_champ(market),
       averaged over all universe player-games (so pass yards' larger scale does not dominate);
  3. challenger = best candidate by validation relative CRPS gain, if the gain is > 0 overall AND > 0 in at least
     `min_val_seasons_better` (= 3) of the 4 validation seasons;
  4. challenger vs champion on the SELECTION seasons (2023-2024): paired game-clustered bootstrap of the relative CRPS
     gain; promote only if gain > z * SE with z = Phi^-1(1 - alpha / M), M = `max_promotion_tests` fixed IN ADVANCE
     (plain Bonferroni over a pre-declared family: FWER <= alpha. v2 used m = tests-so-far, which bounds the FWER by
     alpha * H_m, e.g. 0.075 at m = 2; Tester1 N6). After M tests the loop refuses to test further;
  5. real-line gate: if real lines exist for the selection period (`improve.real_gate_csv`), the challenger's raw
     log loss at those lines must not be worse than the champion's (paired game-clustered 95% CI upper bound >= 0).
     No real lines exist for 2023-24 and 2025 is the frozen holdout, so the gate is currently "not applicable";
     2026 snapshot lines (nflprops.snapshot) will feed it and a CLV gate later.
Every run is appended to experiments/runs.jsonl (+ runs.csv); experiments/champion.json holds the champion, the
history, n_candidates_tried and n_promotion_tests. The holdout (2025) is never touched here.

    python -m nflprops.improve --iterations 4
"""
from __future__ import annotations

import argparse
import copy
import datetime as dt
import json
import logging
import random

import numpy as np
import pandas as pd
from scipy.stats import norm

from . import EXPERIMENTS
from .backtest import walk_forward
from .config import chash, deep_update, load_config, model_key
from .features import load_features

log = logging.getLogger("improve")
RUNS = EXPERIMENTS / "runs.jsonl"
CHAMP = EXPERIMENTS / "champion.json"

SEARCH_SPACE = {
    ("model", "feature_set"): ["player_only", "player_proxy", "no_opponent", "full"],
    ("model", "use_snaps"): [True, False],
    ("model", "use_market_proj"): [True, False],
    ("model", "dist"): ["empirical", "normal"],
    ("model", "retrain_every_weeks"): [2, 4],
    ("model", "lgbm", "num_leaves"): [7, 15],
    ("model", "lgbm", "min_child_samples"): [50, 200],
    ("model", "lgbm", "n_estimators"): [200, 400],
}


def _get(cfg, path):
    for k in path:
        cfg = cfg[k]
    return cfg


def _set(cfg, path, v):
    for k in path[:-1]:
        cfg = cfg.setdefault(k, {})
    cfg[path[-1]] = v


def mutate(champ: dict, rng: random.Random, seen: set) -> tuple[dict, list]:
    for _ in range(500):
        c = copy.deepcopy(champ)
        knobs = rng.sample(list(SEARCH_SPACE), rng.choice([1, 2]))
        changes = []
        for kp in knobs:
            opts = [v for v in SEARCH_SPACE[kp] if v != _get(champ, kp)]
            v = rng.choice(opts)
            _set(c, kp, v)
            changes.append(f"{'.'.join(kp)}={v}")
        h = chash(model_key(c))
        if h not in seen:
            seen.add(h)
            return c, changes
    raise RuntimeError("search space exhausted")


def _flat(prefix, d):
    out = {}
    for k, v in d.items():
        if isinstance(v, dict):
            out.update(_flat(f"{prefix}{k}.", v))
        elif not isinstance(v, (list, pd.DataFrame)):
            out[f"{prefix}{k}"] = v
    return out


def log_run(rec: dict):
    EXPERIMENTS.mkdir(parents=True, exist_ok=True)
    rec = {"run_id": f"r{sum(1 for _ in open(RUNS)) + 1 if RUNS.exists() else 1:04d}",
           "timestamp": dt.datetime.now().astimezone().isoformat(timespec="seconds"), **rec}
    with open(RUNS, "a") as f:
        f.write(json.dumps(rec, default=float) + "\n")
    rows = [json.loads(line) for line in open(RUNS)]
    pd.DataFrame([_flat("", {k: v for k, v in r.items() if k != "config"}) for r in rows]).to_csv(
        EXPERIMENTS / "runs.csv", index=False)
    return rec["run_id"]


# ------------------------------------------------------------------------------------------- projection metrics
def proj_metrics(preds: pd.DataFrame) -> dict:
    def m(g):
        return {"n": int(len(g)), "crps": float(g["crps"].mean()), "mae": float((g["mu"] - g["actual"]).abs().mean()),
                "mae_naive": float((g["naive"] - g["actual"]).abs().mean()),
                "mae_public": float((g["mkt_proj"] - g["actual"]).abs().mean()),
                "pit_cov80": float(g["pit"].between(0.1, 0.9).mean()) if "pit" in g else None,
                "pit_mean": float(g["pit"].mean()) if "pit" in g else None}
    out = {"overall": m(preds), "per_market": {k: m(g) for k, g in preds.groupby("market")},
           "per_season": {str(k): m(g) for k, g in preds.groupby("season")}}
    return out


def _rel(pa: pd.DataFrame, pb: pd.DataFrame) -> pd.DataFrame:
    """Row-level relative CRPS gain of b over a, normalised by a's mean CRPS per market; rows paired exactly."""
    k = ["player_id", "game_id", "market"]
    j = pa[k + ["season", "crps"]].merge(pb[k + ["crps"]], on=k, suffixes=("_a", "_b"))
    if len(j) != len(pa) or len(j) != len(pb):
        raise ValueError("champion and challenger were not scored on identical player-games")
    scale = j.groupby("market")["crps_a"].transform("mean")
    return j.assign(g=(j["crps_a"] - j["crps_b"]) / scale)


def paired_gain(pa, pb, n=4000, seed=0) -> dict:
    j = _rel(pa, pb)
    c = j.groupby("game_id")["g"].agg(["sum", "size"])
    rng = np.random.default_rng(seed)
    idx = rng.integers(0, len(c), size=(n, len(c)))
    boots = c["sum"].values[idx].sum(1) / c["size"].values[idx].sum(1)
    return {"gain": float(j["g"].mean()), "se": float(boots.std(ddof=1)), "p_gain_pos": float((boots > 0).mean()),
            "n_games": int(len(c)), "n_rows": int(len(j))}


def season_gains(pa, pb) -> dict:
    j = _rel(pa, pb)
    return {int(s): float(g["g"].mean()) for s, g in j.groupby("season")}


def real_gate(champ: dict, chal: dict, seasons, feats, csv: str | None) -> dict:
    if not csv:
        return {"status": "not applicable (no real lines for the selection period; 2025 is the frozen holdout)"}
    from .betting import add_probs
    from .metrics import cluster_logloss
    a = walk_forward(deep_update(champ, {"lines": {"source": "csv", "csv_path": csv}}), seasons, feats)
    b = walk_forward(deep_update(chal, {"lines": {"source": "csv", "csv_path": csv}}), seasons, feats)
    ca, cb = cluster_logloss(add_probs(a, 0.0)), cluster_logloss(add_probs(b, 0.0))
    j = ca.join(cb, lsuffix="_a", rsuffix="_b", how="inner")
    d, n_ = (j["ll_sum_a"] - j["ll_sum_b"]).values, j["n_a"].values
    rng = np.random.default_rng(0)
    idx = rng.integers(0, len(j), size=(4000, len(j)))
    g = d[idx].sum(1) / n_[idx].sum(1)
    hi = float(np.quantile(g, 0.975))
    return {"status": "pass" if hi >= 0 else "fail", "ll_gain": float(d.sum() / n_.sum()), "ci_hi": hi,
            "n_lines": int(n_.sum())}


def proj_cfg(cfg: dict) -> dict:
    return deep_update(cfg, {"lines": {"source": "none"}})


def main(iterations: int, base_config: str | None = None, seed: int = 42, init_from: str | None = None):
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(message)s")
    base = load_config(base_config)
    feats = load_features(base["data"]["first_season"], base["data"]["last_season"])
    V, S = base["periods"]["validation_seasons"], base["periods"]["selection_seasons"]
    ic = base["improve"]
    M, alpha = int(ic["max_promotion_tests"]), float(ic["alpha"])
    z = float(norm.ppf(1 - alpha / M))

    if CHAMP.exists():
        state = json.loads(CHAMP.read_text())
    else:
        init = base
        if init_from:   # start from an earlier champion's MODEL settings (e.g. the v2 champion)
            init = deep_update(base, {"model": json.loads(open(init_from).read())["champion"]["model"]})
        init = proj_cfg(init)
        h = chash(model_key(init))
        pv, ps = walk_forward(init, V, feats), walk_forward(init, S, feats)
        state = {"champion": init, "champion_hash": h, "val": proj_metrics(pv), "sel": proj_metrics(ps),
                 "history": [], "iteration": 0, "n_candidates_tried": 0, "n_promotion_tests": 0,
                 "rule": f"v3: projection accuracy (relative CRPS vs actuals), >= {ic['min_val_seasons_better']}/4 "
                         f"validation seasons, selection gain > z*SE, z = Phi^-1(1-{alpha}/{M}) fixed "
                         f"(Bonferroni over max {M} pre-declared tests), real-line gate when real lines exist",
                 "z": z, "max_promotion_tests": M, "init_from": init_from}
        rid = log_run({"iteration": 0, "role": "initial_champion", "period": "validation", "seasons": V,
                       "config_hash": h, "changes": [], "metrics": state["val"], "config": init})
        log_run({"iteration": 0, "role": "initial_champion", "period": "selection", "seasons": S, "config_hash": h,
                 "changes": [], "metrics": state["sel"], "config": init})
        state["history"].append({"iteration": 0, "event": "initial champion", "run_id": rid, "config_hash": h})
        CHAMP.write_text(json.dumps(state, indent=2, default=float))

    seen = {chash(model_key(json.loads(l)["config"])) for l in open(RUNS)} if RUNS.exists() else set()
    for _ in range(iterations):
        it = state["iteration"] + 1
        rng = random.Random(seed * 1000 + it)
        champ = state["champion"]
        cv = walk_forward(champ, V, feats)
        log.info("=== iteration %d | champion %s | val CRPS %.4f", it, state["champion_hash"],
                 state["val"]["overall"]["crps"])
        results = []
        for ci in range(ic["candidates_per_iteration"]):
            cand, changes = mutate(champ, rng, seen)
            pv = walk_forward(cand, V, feats)
            sg = season_gains(cv, pv)
            g = float(_rel(cv, pv)["g"].mean())
            state["n_candidates_tried"] += 1
            rid = log_run({"iteration": it, "role": "candidate", "period": "validation", "seasons": V,
                           "config_hash": chash(model_key(cand)), "changes": changes, "val_rel_crps_gain": g,
                           "val_season_gains": sg, "metrics": proj_metrics(pv), "config": cand})
            log.info("  cand %d %s -> val rel CRPS gain %+.5f; seasons %s", ci, changes, g,
                     {k: round(v, 4) for k, v in sg.items()})
            results.append((g, cand, changes, rid, sg))
        results.sort(key=lambda r: -r[0])
        g, chal, changes, rid, sg = results[0]
        n_better = sum(v > 0 for v in sg.values())
        decision = {"iteration": it, "best_candidate_run": rid, "changes": changes, "val_rel_crps_gain": g,
                    "val_seasons_better": f"{n_better}/{len(sg)}", "n_candidates_tried": state["n_candidates_tried"]}
        if g <= 0:
            decision.update(event="no challenger (no candidate beat the champion on validation)", promoted=False)
        elif n_better < ic["min_val_seasons_better"]:
            decision.update(event=f"no challenger (better in only {n_better}/{len(sg)} validation seasons)",
                            promoted=False)
        elif state["n_promotion_tests"] >= M:
            decision.update(event=f"no test: the pre-declared budget of {M} promotion tests is used up",
                            promoted=False)
        else:
            state["n_promotion_tests"] += 1
            cs, hs = walk_forward(champ, S, feats), walk_forward(chal, S, feats)
            pg = paired_gain(cs, hs)
            gate = real_gate(champ, chal, S, feats, ic.get("real_gate_csv"))
            ok = pg["gain"] > z * pg["se"] and gate["status"] != "fail"
            log_run({"iteration": it, "role": "challenger", "period": "selection", "seasons": S,
                     "config_hash": chash(model_key(chal)), "changes": changes, "metrics": proj_metrics(hs),
                     "sel_rel_crps_gain": pg, "z": z, "test_no": state["n_promotion_tests"], "real_gate": gate,
                     "promoted": ok, "config": chal})
            decision.update(sel_gain=pg["gain"], sel_se=pg["se"], z=z, margin=z * pg["se"],
                            test_no=state["n_promotion_tests"], boot_p_gain_pos=pg["p_gain_pos"], real_gate=gate,
                            sel_crps_challenger=proj_metrics(hs)["overall"]["crps"],
                            sel_crps_champion=proj_metrics(cs)["overall"]["crps"], promoted=ok,
                            event="PROMOTED" if ok else "challenger rejected on selection seasons")
            if ok:
                state.update(champion=chal, champion_hash=chash(model_key(chal)), val=proj_metrics(walk_forward(
                    chal, V, feats)), sel=proj_metrics(hs))
        log.info("  decision: %s", {k: v for k, v in decision.items() if k != "changes"})
        state["history"].append(decision)
        state["iteration"] = it
        CHAMP.write_text(json.dumps(state, indent=2, default=float))
    return state


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--iterations", type=int, default=4)
    ap.add_argument("--config", default=None)
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--init-from", default=None, help="champion.json whose model settings start a fresh loop")
    a = ap.parse_args()
    main(a.iterations, a.config, a.seed, a.init_from)

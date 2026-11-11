"""'Gets better with each backtest' — done without overfitting (v2 rule, after Tester1 finding B2).

Each iteration:
  1. propose N candidate configs by mutating 1-2 knobs of the champion (seeded, reproducible; the search space
     is now mostly feature groups / distribution form rather than LightGBM hyper-parameters);
  2. walk-forward each candidate on the VALIDATION seasons (2019-2022) and score it on RAW model probabilities
     (log loss of P(over) at the line, no market blend: v1 compared 90%-market-blended probabilities, which shrank
     every difference ~10-40x);
  3. challenger = best candidate by validation raw log loss, if it beats the champion overall AND in at least
     `min_val_seasons_better` of the validation seasons (consistency);
  4. challenger vs champion on the SELECTION seasons (2023-2024): paired game-clustered bootstrap of the raw
     log-loss gain; promote only if  gain > z_adj * SE(gain),  z_adj = Phi^-1(1 - alpha/m)  with m = the number of
     promotion tests run so far in this experiment log (Bonferroni across the loop's repeated use of 2023-24);
  5. every run is appended to experiments/runs.jsonl (+ runs.csv); experiments/champion.json holds the champion,
     the promotion history and the number of candidates tried.
Betting parameters (edge threshold, Kelly fraction) are tuned on validation only; betting probabilities come from
the rolling per-market stacker. The holdout (2025) is never touched here.

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
from .betting import add_probs
from .config import chash, load_config, model_key
from .features import load_features
from .metrics import cluster_logloss, evaluate
from .tuning import tune_betting

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


KEEP = ["n_lines", "logloss_raw", "logloss", "logloss_market", "brier", "brier_market", "mae_model",
        "mae_naive_ewma", "mae_market_proxy", "mae_line", "crps_model", "n_bets", "hit_rate", "flat_roi",
        "kelly_roi", "final_bankroll", "max_drawdown"]


def _summ(ev: dict) -> dict:
    o = {k: ev["overall"].get(k) for k in KEEP}
    o["per_market"] = {m: {k: v.get(k) for k in KEEP if k in v} for m, v in ev["per_market"].items()}
    o["per_season_logloss_raw"] = {str(s): v.get("logloss_raw") for s, v in ev["per_season"].items()}
    return o


def tuned_strip(t: dict) -> dict:
    return {k: t.get(k) for k in ("market_blend", "val_logloss_best_blend", "model_adds_nothing", "edge_threshold",
                                  "kelly_fraction", "val_log_growth", "no_bet", "stacker_model_weight_end")}


def evaluate_config(cfg: dict, seasons: list[int], feats, bet_params: dict | None = None,
                    history_seasons: list[int] | None = None):
    preds = walk_forward(cfg, seasons, feats)
    hist = walk_forward(cfg, history_seasons, feats) if history_seasons else None
    tuned = bet_params or tune_betting(preds, cfg, hist)
    bc = dict(cfg["betting"], **{k: tuned[k] for k in ("edge_threshold", "kelly_fraction")})
    ev = evaluate(preds, bc, hist)
    return preds, tuned, bc, ev


def paired_raw_gain(pa: pd.DataFrame, pb: pd.DataFrame, n=4000, seed=0) -> dict:
    """Raw-probability log-loss gain of b over a, paired by game, game-clustered bootstrap."""
    a, b = cluster_logloss(add_probs(pa, 0.0)), cluster_logloss(add_probs(pb, 0.0))
    j = a.join(b, lsuffix="_a", rsuffix="_b", how="inner")
    if not (j["n_a"] == j["n_b"]).all():
        raise ValueError("champion and challenger were not scored on identical lines")
    d, n_ = (j["ll_sum_a"] - j["ll_sum_b"]).values, j["n_a"].values
    rng = np.random.default_rng(seed)
    idx = rng.integers(0, len(j), size=(n, len(j)))
    boots = d[idx].sum(1) / n_[idx].sum(1)
    return {"gain": float(d.sum() / n_.sum()), "se": float(boots.std(ddof=1)), "p_gain_pos": float((boots > 0).mean()),
            "n_games": int(len(j))}


def season_raw_gains(pa: pd.DataFrame, pb: pd.DataFrame) -> dict:
    out = {}
    for s in sorted(pa["season"].unique()):
        a = cluster_logloss(add_probs(pa[pa["season"] == s], 0.0))
        b = cluster_logloss(add_probs(pb[pb["season"] == s], 0.0))
        out[int(s)] = float((a["ll_sum"].sum() - b["ll_sum"].sum()) / a["n"].sum())
    return out


def main(iterations: int, base_config: str | None = None, seed: int = 42):
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(message)s")
    base = load_config(base_config)
    feats = load_features(base["data"]["first_season"], base["data"]["last_season"])
    V, S = base["periods"]["validation_seasons"], base["periods"]["selection_seasons"]
    ic = base["improve"]

    if CHAMP.exists():
        state = json.loads(CHAMP.read_text())
    else:
        _, tuned, _, ev = evaluate_config(base, V, feats)
        _, _, _, evs = evaluate_config(base, S, feats, tuned, history_seasons=V)
        h = chash(model_key(base))
        state = {"champion": base, "champion_hash": h, "betting": tuned_strip(tuned), "val": _summ(ev),
                 "sel": _summ(evs), "history": [], "iteration": 0, "n_candidates_tried": 0,
                 "n_promotion_tests": 0, "rule": "v2: raw-prob LL, val-season consistency, SE margin, Bonferroni"}
        rid = log_run({"iteration": 0, "role": "initial_champion", "period": "validation", "seasons": V,
                       "config_hash": h, "changes": [], "betting": tuned_strip(tuned), "metrics": _summ(ev),
                       "config": base})
        log_run({"iteration": 0, "role": "initial_champion", "period": "selection", "seasons": S, "config_hash": h,
                 "changes": [], "betting": tuned_strip(tuned), "metrics": _summ(evs), "config": base})
        state["history"].append({"iteration": 0, "event": "initial champion", "run_id": rid, "config_hash": h})
        CHAMP.write_text(json.dumps(state, indent=2, default=float))

    seen = {chash(model_key(json.loads(l)["config"])) for l in open(RUNS)} if RUNS.exists() else set()
    for _ in range(iterations):
        it = state["iteration"] + 1
        rng = random.Random(seed * 1000 + it)
        champ = state["champion"]
        champ_val_preds = walk_forward(champ, V, feats)
        log.info("=== iteration %d | champion %s | val raw LL %.5f | sel raw LL %.5f", it, state["champion_hash"],
                 state["val"]["logloss_raw"], state["sel"]["logloss_raw"])
        results = []
        for ci in range(ic["candidates_per_iteration"]):
            cand, changes = mutate(champ, rng, seen)
            cpreds, tuned, _, ev = evaluate_config(cand, V, feats)
            sg = season_raw_gains(champ_val_preds, cpreds)
            state["n_candidates_tried"] += 1
            rid = log_run({"iteration": it, "role": "candidate", "period": "validation", "seasons": V,
                           "config_hash": chash(model_key(cand)), "changes": changes, "betting": tuned_strip(tuned),
                           "val_season_raw_gain_vs_champion": sg, "metrics": _summ(ev), "config": cand})
            log.info("  cand %d %s -> val raw LL %.5f (champ %.5f); season gains %s", ci, changes,
                     ev["overall"]["logloss_raw"], state["val"]["logloss_raw"],
                     {k: round(v, 4) for k, v in sg.items()})
            results.append((ev["overall"]["logloss_raw"], cand, changes, tuned, rid, sg))
        results.sort(key=lambda r: r[0])
        best_ll, chal, changes, tuned, rid, sg = results[0]
        n_better = sum(v > 0 for v in sg.values())
        decision = {"iteration": it, "best_candidate_run": rid, "changes": changes,
                    "val_raw_ll_challenger": best_ll, "val_raw_ll_champion": state["val"]["logloss_raw"],
                    "val_seasons_better": f"{n_better}/{len(sg)}", "n_candidates_tried": state["n_candidates_tried"]}
        if best_ll >= state["val"]["logloss_raw"]:
            decision.update(event="no challenger (no candidate beat the champion on validation)", promoted=False)
        elif n_better < ic["min_val_seasons_better"]:
            decision.update(event=f"no challenger (better in only {n_better}/{len(sg)} validation seasons)",
                            promoted=False)
        else:
            state["n_promotion_tests"] += 1
            m = state["n_promotion_tests"]
            z = float(norm.ppf(1 - ic["alpha"] / m))
            champ_sel = walk_forward(champ, S, feats)
            chal_sel, _, _, evs = evaluate_config(chal, S, feats, tuned, history_seasons=V)
            g = paired_raw_gain(champ_sel, chal_sel)
            ok = g["gain"] > z * g["se"]
            log_run({"iteration": it, "role": "challenger", "period": "selection", "seasons": S,
                     "config_hash": chash(model_key(chal)), "changes": changes, "betting": tuned_strip(tuned),
                     "metrics": _summ(evs), "sel_raw_gain": g, "z_adj": z, "m_tests": m, "promoted": ok,
                     "config": chal})
            decision.update(sel_raw_ll_challenger=evs["overall"]["logloss_raw"],
                            sel_raw_ll_champion=state["sel"]["logloss_raw"], sel_gain=g["gain"], sel_se=g["se"],
                            z_adj=z, m_tests=m, margin=z * g["se"], boot_p_gain_pos=g["p_gain_pos"], promoted=ok,
                            event="PROMOTED" if ok else "challenger rejected on selection seasons")
            if ok:
                vev = evaluate_config(chal, V, feats, tuned)[3]
                state.update(champion=chal, champion_hash=chash(model_key(chal)), betting=tuned_strip(tuned),
                             val=_summ(vev), sel=_summ(evs))
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
    a = ap.parse_args()
    main(a.iterations, a.config, a.seed)

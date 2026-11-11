"""Frozen 2025 holdout — scored ONCE, with the pre-declared policy in configs/holdout_policy.yaml.

Guards (Tester1 B9/B10):
  * refuses to run unless the sha1 of configs/holdout_policy.yaml appears in reports/REPORT.md (i.e. the policy was
    published in the report BEFORE scoring — run `python -m nflprops.summary` first);
  * refuses to run if experiments/holdout_frozen.json exists (it has already been scored) unless --force;
  * nothing is tuned here: the champion's model config + the policy's betting rule are used as declared.
`python -m nflprops.summary` only READS experiments/holdout_frozen.json; it never re-scores 2025.

    python -m nflprops.holdout            # the one real run
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import logging

import numpy as np
import pandas as pd
import yaml

from . import EXPERIMENTS, REPORTS, ROOT
from .backtest import walk_forward
from .betting import add_probs
from .config import chash, deep_update, model_key
from .features import load_features
from .improve import CHAMP, _summ, log_run
from .metrics import cluster_bootstrap_roi, cluster_logloss, evaluate
from .report import write_report

POLICY = ROOT / "configs" / "holdout_policy.yaml"
FROZEN = EXPERIMENTS / "holdout_frozen.json"


def policy_sha1() -> str:
    return hashlib.sha1(POLICY.read_bytes()).hexdigest()


def policy_bc(cfg: dict, pol: dict) -> dict:
    p = pol["primary"]
    return dict(cfg["betting"], prob_method=p["probabilities"]["method"],
                stacker_lambda=p["probabilities"]["lambda"], stacker_min_n=p["probabilities"]["min_n"],
                edge_threshold=p["bet_rule"]["edge_threshold"], **p["staking"])


def paired_ll(p: pd.DataFrame, col: str, n=4000, seed=0) -> dict:
    """Log-loss gain of `col` over the no-vig market, per line, game-clustered bootstrap 95% CI."""
    a, b = cluster_logloss(p, "p_mkt_over"), cluster_logloss(p, col)
    d, nn = (a["ll_sum"] - b["ll_sum"]).values, a["n"].values
    rng = np.random.default_rng(seed)
    idx = rng.integers(0, len(d), size=(n, len(d)))
    g = d[idx].sum(1) / nn[idx].sum(1)
    return {"gain_nats_per_line": float(d.sum() / nn.sum()), "ci95": [float(np.quantile(g, .025)),
                                                                       float(np.quantile(g, .975))],
            "p_gain_pos": float((g > 0).mean()), "n_games": int(len(d)), "n_lines": int(nn.sum())}


def score(ev: dict) -> dict:
    out = _summ(ev)
    b, p = ev["_bets"], ev["_p"]
    p = p[p["line"].notna()]
    out["roi_ci95_game_clustered"] = list(cluster_bootstrap_roi(b))
    out["n_games_bet"] = int(b["game_id"].nunique()) if len(b) else 0
    out["ll_gain_raw_vs_market"] = paired_ll(p, "p_over_raw")
    out["ll_gain_stacked_vs_market"] = paired_ll(p, "p_over")
    for mk in out["per_market"]:
        bm = b[b["market"] == mk] if len(b) else b
        pm = p[p["market"] == mk]
        out["per_market"][mk]["roi_ci95_game_clustered"] = list(cluster_bootstrap_roi(bm))
        out["per_market"][mk]["n_games_bet"] = int(bm["game_id"].nunique()) if len(bm) else 0
        out["per_market"][mk]["ll_gain_raw_vs_market"] = paired_ll(pm, "p_over_raw")
        out["per_market"][mk]["ll_gain_stacked_vs_market"] = paired_ll(pm, "p_over")
    c = ev["_coefs"]
    out["stacker_coefs_last"] = (c.dropna().sort_values("t").groupby("market").tail(1)
                                 .set_index("market")[["t", "n", "a", "b", "c"]].to_dict("index") if len(c) else {})
    out["first_bettable_week_by_market"] = (c.dropna().groupby("market")["t"].min().mod(100).astype(int).to_dict()
                                            if len(c) and c["c"].notna().any() else {})
    return out


def main(force: bool = False):
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(message)s")
    sha = policy_sha1()
    rep = REPORTS / "REPORT.md"
    if not rep.exists() or sha not in rep.read_text():
        raise SystemExit(f"policy sha1 {sha} not found in {rep}: publish the policy first (python -m nflprops.summary)")
    if FROZEN.exists() and not force:
        raise SystemExit(f"{FROZEN} exists: the holdout was already scored. Not re-scoring (use --force only to "
                         "reproduce, never to re-decide).")
    pol = yaml.safe_load(POLICY.read_text())
    st = json.loads(CHAMP.read_text())
    cfg = st["champion"]
    H = pol["holdout_season"]
    V, S = cfg["periods"]["validation_seasons"], cfg["periods"]["selection_seasons"]
    h = chash(model_key(cfg))
    bc = policy_bc(cfg, pol)
    feats = load_features(cfg["data"]["first_season"], cfg["data"]["last_season"])
    results = {"policy_sha1": sha, "champion_hash": h, "champion_model": cfg["model"],
               "scored_at": dt.datetime.now().astimezone().isoformat(timespec="seconds"), "forced": force}
    csv = ROOT / pol["primary"]["line_source"]
    rc = deep_update(cfg, {"lines": {"source": "csv", "csv_path": str(csv)}})
    variants = [("real_espn_uncertain_timing", rc, None, False, pol["primary"]["label"]),
                ("sim", cfg, walk_forward(cfg, V + S, feats), True, "simulated_sharp (history 2019-2024 sim)")]
    all_preds = {}
    for tag, c, hist, sim, label in variants:
        preds = walk_forward(c, [H], feats)
        all_preds[tag] = preds
        ev = evaluate(preds, bc, hist)
        title = (f"HOLDOUT {H} — champion {h} — " +
                 ("SIMULATED lines" if sim else "ESPN BET lines of uncertain timing"))
        coefs_md = ""
        if len(ev["_coefs"]):
            cc = ev["_coefs"].assign(week=lambda d: d["t"] % 100).drop(columns="t")
            coefs_md = ("## Stacker coefficients (fit on strictly earlier weeks; c = model weight)\n\n"
                        + cc.round(3).to_markdown(index=False))
        path = write_report(ev, c, bc, REPORTS / f"holdout_{H}_{tag}", title, sim, label, extra_md=coefs_md,
                            preds=preds, history=hist)
        r = score(ev)
        rid = log_run({"iteration": st["iteration"], "role": "holdout", "period": f"holdout_{tag}", "seasons": [H],
                       "config_hash": h, "changes": [], "betting": {k: bc[k] for k in ("prob_method",
                       "edge_threshold", "kelly_fraction")}, "metrics": {k: v for k, v in r.items()
                       if k not in ("stacker_coefs_last",)}, "policy_sha1": sha, "config": c})
        results[tag] = {"report": str(path.relative_to(ROOT)), "run_id": rid, "label": label, **r}
        print(f"[{tag}] {path}")
    a = all_preds["sim"].dropna(subset=["line"])
    b = all_preds["real_espn_uncertain_timing"].dropna(subset=["line"])
    m = a.merge(b[["player_id", "game_id", "market", "line"]], on=["player_id", "game_id", "market"],
                suffixes=("_sim", "_real"))
    results["sim_vs_real_lines"] = {mk: {
        "n_overlap": int(len(g)),
        "mae_sim_line": float((g["line_sim"] - g["actual"]).abs().mean()),
        "mae_real_line": float((g["line_real"] - g["actual"]).abs().mean()),
        "mae_model_mean": float((g["mu"] - g["actual"]).abs().mean()),
        "over_rate_sim": float((g["actual"] > g["line_sim"]).mean()),
        "over_rate_real": float((g["actual"] > g["line_real"]).mean()),
        "mean_sim_minus_real": float((g["line_sim"] - g["line_real"]).mean()),
        "corr_sim_real": float(g["line_sim"].corr(g["line_real"]))} for mk, g in m.groupby("market")}
    FROZEN.write_text(json.dumps(results, indent=2, default=float))
    st.setdefault("holdout_evaluations", []).append({"config_hash": h, "policy_sha1": sha,
                                                     "timestamp": results["scored_at"], "frozen_file": str(FROZEN)})
    CHAMP.write_text(json.dumps(st, indent=2, default=float))
    print(FROZEN)
    return results


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--force", action="store_true", help="reproduce an already-frozen holdout (never to re-decide)")
    main(ap.parse_args().force)

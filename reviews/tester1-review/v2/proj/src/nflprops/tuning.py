"""Validation-only choice of post-model betting parameters (no retraining needed => cheap).

* Betting probabilities come from the per-market logistic stacker (calibration.py), fit on strictly earlier weeks.
* Diagnostic only: the linear market blend minimising validation log loss over a grid that now INCLUDES 1.0
  (= "the model adds nothing"; Tester1 B2 — v1's grid stopped at 0.9 and every run sat on that edge).
* edge_threshold x kelly_fraction maximise validation log bankroll growth (min bet count); if nothing grows the
  bankroll the tuned policy is "don't bet". Thresholds below the vig hurdle are not offered (Tester1 B8:
  at -110/-110 an edge < 2.4pp can never pass the EV>0 filter, at -115/-115 < 3.5pp).
"""
from __future__ import annotations

import itertools

import numpy as np
import pandas as pd

from .betting import add_probs
from .calibration import betting_probs
from .metrics import _ll, evaluate


def choose_blend(preds: pd.DataFrame, grid) -> tuple[float, float]:
    best = None
    for a in grid:
        p = add_probs(preds, a)
        p = p[~p["push"]]
        ll = float(_ll(p["p_over"], p["over_hit"]).mean())
        if best is None or ll < best[1] - 1e-12:
            best = (float(a), ll)
    return best


def tune_betting(preds: pd.DataFrame, cfg: dict, history: pd.DataFrame | None = None) -> dict:
    g = cfg["improve"]["betting_grid"]
    blend, ll_blend = choose_blend(preds, g["market_blend"])
    base_bc = dict(cfg["betting"])
    p_pre, coefs = betting_probs(preds, base_bc, history)
    best, rows = None, []
    for thr, kf in itertools.product(g["edge_threshold"], g["kelly_fraction"]):
        bc = dict(base_bc, edge_threshold=thr, kelly_fraction=kf)
        o = evaluate(preds, bc, p_pre=(p_pre, coefs))["overall"]
        growth = float(np.log(max(o["final_bankroll"], 1e-9) / bc["start_bankroll"]))
        rows.append({"edge_threshold": thr, "kelly_fraction": kf, "n_bets": o["n_bets"], "log_growth": growth,
                     "flat_roi": o["flat_roi"]})
        if o["n_bets"] >= cfg["improve"]["min_validation_bets"] and (best is None or growth > best[0]):
            best = (growth, thr, kf)
    no_bet = False
    if best is None or (cfg["improve"].get("no_bet_if_negative", True) and best[0] <= 0):
        no_bet = True
        best = (best[0] if best else float("nan"), 1.0, min(g["kelly_fraction"]))
    c = coefs.dropna().groupby("market")["c"].last().to_dict() if len(coefs) else {}
    return {"market_blend": blend, "val_logloss_best_blend": ll_blend, "model_adds_nothing": blend >= 1.0,
            "edge_threshold": best[1], "kelly_fraction": best[2], "val_log_growth": best[0], "no_bet": no_bet,
            "stacker_model_weight_end": c, "grid": rows}

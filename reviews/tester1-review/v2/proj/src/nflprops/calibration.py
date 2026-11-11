"""Per-market logistic stacker that shrinks the model toward the market, fit ONLY on strictly earlier weeks.

    logit p = a_m + b_m * logit(p_market_novig) + c_m * logit(p_model)

Fit by penalised maximum likelihood with a ridge prior centred on "trust the market": (a, b, c) -> (0, 1, 0),
penalty lam * (a^2 + (b-1)^2 + c^2). For week t of a given market the coefficients are fit on every priced line of
that market (same line source) with (season, week) < t — the evaluation frame plus an optional `history` frame of
earlier periods. Until a market has `min_n` prior lines the stacker returns the market probability (=> no bets).
c_m is the effective model weight; Tester1 estimated ~0.19 overall / 0.30 rec / ~0 rush IN-SAMPLE on 2025 —
here it is always estimated out of sample.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
from scipy.optimize import minimize

from .betting import add_probs


def _logit(p):
    p = np.clip(np.asarray(p, float), 1e-4, 1 - 1e-4)
    return np.log(p / (1 - p))


def fit_stacker(x_mkt, x_mod, y, lam: float) -> np.ndarray:
    X = np.column_stack([np.ones_like(x_mkt), x_mkt, x_mod])
    prior = np.array([0.0, 1.0, 0.0])

    def f(th):
        z = X @ th
        nll = np.sum(np.logaddexp(0, z) - y * z)
        g = X.T @ (1 / (1 + np.exp(-z)) - y)
        d = th - prior
        return nll + lam * d @ d, g + 2 * lam * d
    return minimize(f, prior.copy(), jac=True, method="L-BFGS-B").x


def stacked_probs(p: pd.DataFrame, history: pd.DataFrame | None, lam: float, min_n: int):
    """p, history: frames from betting.add_probs (need p_mkt_over, p_over_model, over_hit, push, season, week,
    market). Returns (p_stacked Series aligned to p, coef DataFrame)."""
    allp = pd.concat([history, p], keys=["h", "p"]) if history is not None and len(history) else \
        pd.concat([p], keys=["p"])
    allp = allp.assign(_t=allp["season"] * 100 + allp["week"])
    out = pd.Series(p["p_mkt_over"].values.copy(), index=p.index, dtype=float)
    coefs = []
    for mk, g in allp.groupby("market"):
        tr_all = g[~g["push"]]
        xm, xd, yy, tt = (_logit(tr_all["p_mkt_over"]), _logit(tr_all["p_over_model"]),
                          tr_all["over_hit"].values, tr_all["_t"].values)
        cur = g.loc["p"] if "p" in g.index.get_level_values(0) else None
        if cur is None:
            continue
        for t in sorted(cur["_t"].unique()):
            m = tt < t
            rows = cur.index[cur["_t"] == t]
            if m.sum() < min_n:
                coefs.append({"market": mk, "t": t, "n": int(m.sum()), "a": np.nan, "b": np.nan, "c": np.nan})
                continue
            th = fit_stacker(xm[m], xd[m], yy[m], lam)
            z = th[0] + th[1] * _logit(p.loc[rows, "p_mkt_over"]) + th[2] * _logit(p.loc[rows, "p_over_model"])
            out.loc[rows] = 1 / (1 + np.exp(-z))
            coefs.append({"market": mk, "t": t, "n": int(m.sum()), "a": th[0], "b": th[1], "c": th[2]})
    return out, pd.DataFrame(coefs)


def betting_probs(preds: pd.DataFrame, bc: dict, history: pd.DataFrame | None = None):
    """Probabilities used for betting. bc['prob_method']: 'stacker' (default) or 'blend' (linear market_blend)."""
    p = add_probs(preds, bc.get("market_blend", 0.0))
    p["p_over_raw"] = p["p_over_model"].clip(1e-4, 1 - 1e-4)
    coefs = pd.DataFrame()
    if bc.get("prob_method", "stacker") == "stacker":
        h = add_probs(history, 0.0) if history is not None and len(history) else None
        p["p_over"], coefs = stacked_probs(p, h, bc.get("stacker_lambda", 50.0), bc.get("stacker_min_n", 300))
        p["p_over"] = p["p_over"].clip(1e-4, 1 - 1e-4)
    return p, coefs

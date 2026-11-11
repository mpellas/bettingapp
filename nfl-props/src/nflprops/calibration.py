"""Stackers that shrink the model toward the market, fit ONLY on strictly earlier weeks.

v3 DEFAULT (`prob_method: hier_stacker`, after Tester1 N4/N5) — hierarchical logistic stacker, MAP fit:

    logit p = a_m + b * logit(p_market_novig) + c_m * logit(p_model)          m = market
    priors:  a_m ~ N(0, sigma_a^2)  (separate, TIGHT: sigma_a = 0.02 -> no "bet the season's base rate")
             b   ~ N(1, sigma_b^2)  (shared; sigma_b = 0.1; unidentified when prices are flat -110/-110)
             c_m ~ N(c0, tau^2)     (model weight pooled across markets; tau = 0.05)
             c0  ~ N(0, sigma_c0^2) (sigma_c0 = 0.1: "the model adds nothing" is the prior mean)
  fit on every priced line with (season, week) < t: the `history` frame (for 2026: the 2025 ESPN real lines) plus
  earlier weeks of the evaluation frame. No minimum line count (v2's min_n = 300 double-shrank, Tester1 N5): with
  no history the posterior is the prior, i.e. p = p_market and no bets. A Laplace approximation gives posterior SEs.

LEGACY v2 (`prob_method: stacker_v2_ridge`, kept ONLY so the frozen 2025 holdout can be reproduced bit-for-bit):
per-market ridge, the same lambda on a, b and c, plus min_n. Description of the v2 version:

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


HIER_PRIOR = {"sigma_a": 0.02, "sigma_b": 0.1, "tau": 0.05, "sigma_c0": 0.1}


def fit_hier(mk_idx: np.ndarray, x_mkt, x_mod, y, n_m: int, prior: dict):
    """MAP of theta = [a_1..a_M, b, c_1..c_M, c0]; returns (theta, posterior covariance via Laplace)."""
    M = n_m
    sa, sb, tau, sc0 = prior["sigma_a"], prior["sigma_b"], prior["tau"], prior["sigma_c0"]
    oh = np.eye(M)[mk_idx]                                       # n x M one-hot
    X = np.column_stack([oh, x_mkt, oh * x_mod[:, None], np.zeros(len(y))])   # c0 enters via the prior only
    th0 = np.r_[np.zeros(M), 1.0, np.zeros(M), 0.0]

    def penalty(th):
        a, b, c, c0 = th[:M], th[M], th[M + 1:2 * M + 1], th[-1]
        val = (a @ a) / (2 * sa ** 2) + (b - 1) ** 2 / (2 * sb ** 2) + ((c - c0) @ (c - c0)) / (2 * tau ** 2) \
            + c0 ** 2 / (2 * sc0 ** 2)
        g = np.r_[a / sa ** 2, (b - 1) / sb ** 2, (c - c0) / tau ** 2, -(c - c0).sum() / tau ** 2 + c0 / sc0 ** 2]
        return val, g

    def f(th):
        z = X @ th
        nll = np.sum(np.logaddexp(0, z) - y * z)
        g = X.T @ (1 / (1 + np.exp(-z)) - y)
        pv, pg = penalty(th)
        return nll + pv, g + pg
    th = minimize(f, th0, jac=True, method="L-BFGS-B").x
    z = X @ th
    w = (1 / (1 + np.exp(-z))) * (1 - 1 / (1 + np.exp(-z)))
    H = X.T @ (X * w[:, None])
    P = np.zeros_like(H)
    P[np.arange(M), np.arange(M)] += 1 / sa ** 2
    P[M, M] += 1 / sb ** 2
    ci = np.arange(M + 1, 2 * M + 1)
    P[ci, ci] += 1 / tau ** 2
    P[ci, -1] -= 1 / tau ** 2
    P[-1, ci] -= 1 / tau ** 2
    P[-1, -1] += M / tau ** 2 + 1 / sc0 ** 2
    return th, np.linalg.inv(H + P)


def hier_stacked_probs(p: pd.DataFrame, history: pd.DataFrame | None, prior: dict | None = None,
                       markets=("pass_yds", "rec_yds", "rush_yds")):
    """Rolling weekly MAP fit on strictly earlier lines (history + earlier weeks of p). Returns (p_stacked, coefs)."""
    prior = {**HIER_PRIOR, **(prior or {})}
    mk = {m: i for i, m in enumerate(markets)}
    allp = pd.concat([history, p], keys=["h", "p"]) if history is not None and len(history) else \
        pd.concat([p], keys=["p"])
    allp = allp[allp["p_mkt_over"].notna() & allp["p_over_model"].notna()]
    allp = allp.assign(_t=allp["season"] * 100 + allp["week"])
    tr_all = allp[~allp["push"].astype(bool)]
    xm, xd, yy, tt = (_logit(tr_all["p_mkt_over"]), _logit(tr_all["p_over_model"]),
                      tr_all["over_hit"].values.astype(float), tr_all["_t"].values)
    mi = tr_all["market"].map(mk).values
    out = pd.Series(p["p_mkt_over"].values.copy(), index=p.index, dtype=float)
    sd = pd.Series(0.0, index=p.index)
    cur = allp.loc["p"] if "p" in allp.index.get_level_values(0) else allp.iloc[0:0]
    coefs = []
    M = len(markets)
    for t in sorted(cur["_t"].unique()):
        m = tt < t
        rows = cur.index[cur["_t"] == t]
        if m.sum() == 0:
            th, cov = np.r_[np.zeros(M), 1.0, np.zeros(M), 0.0], None
        else:
            th, cov = fit_hier(mi[m], xm[m], xd[m], yy[m], M, prior)
        r = p.loc[rows]
        k = r["market"].map(mk).values
        a, b, c = th[:M][k], th[M], th[M + 1:2 * M + 1][k]
        z = a + b * _logit(r["p_mkt_over"]) + c * _logit(r["p_over_model"])
        out.loc[rows] = 1 / (1 + np.exp(-z))
        if cov is not None:            # SE of the linear predictor (delta method)
            J = np.zeros((len(r), len(th)))
            J[np.arange(len(r)), k] = 1
            J[:, M] = _logit(r["p_mkt_over"])
            J[np.arange(len(r)), M + 1 + k] = _logit(r["p_over_model"])
            sd.loc[rows] = np.sqrt(np.einsum("ij,jk,ik->i", J, cov, J))
        se = np.sqrt(np.diag(cov)) if cov is not None else np.full(len(th), np.nan)
        rec = {"t": t, "n": int(m.sum()), "b": th[M], "c0": th[-1], "se_c0": se[-1]}
        for name, i in mk.items():
            rec.update({f"a_{name}": th[i], f"c_{name}": th[M + 1 + i], f"se_c_{name}": se[M + 1 + i]})
        coefs.append(rec)
    return out, sd, pd.DataFrame(coefs)


def betting_probs(preds: pd.DataFrame, bc: dict, history: pd.DataFrame | None = None):
    """Probabilities used for betting. bc['prob_method']: 'hier_stacker' (v3 default), 'stacker_v2_ridge' (legacy,
    frozen-holdout reproduction only; 'stacker' is an alias) or 'blend' (linear market_blend)."""
    p = add_probs(preds, bc.get("market_blend", 0.0))
    p["p_over_raw"] = p["p_over_model"].clip(1e-4, 1 - 1e-4)
    coefs = pd.DataFrame()
    meth = bc.get("prob_method", "hier_stacker")
    h = add_probs(history, 0.0) if history is not None and len(history) else None
    if meth == "hier_stacker":
        p["p_over"], p["logit_sd"], coefs = hier_stacked_probs(p, h, bc.get("stacker_prior"))
    elif meth in ("stacker", "stacker_v2_ridge"):
        p["p_over"], coefs = stacked_probs(p, h, bc.get("stacker_lambda", 50.0), bc.get("stacker_min_n", 300))
    p["p_over"] = p["p_over"].clip(1e-4, 1 - 1e-4)
    return p, coefs

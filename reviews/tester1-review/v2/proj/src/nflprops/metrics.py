"""Forecast-quality and betting metrics."""
from __future__ import annotations

import numpy as np
import pandas as pd

from .betting import select_bets, simulate_bankroll


def _ll(p, y):
    p = np.clip(p, 1e-6, 1 - 1e-6)
    return -(y * np.log(p) + (1 - y) * np.log(1 - p))


def reliability(p: pd.DataFrame, bins=10) -> pd.DataFrame:
    q = pd.cut(p["p_over"], np.linspace(0, 1, bins + 1), include_lowest=True)
    return p.groupby(q, observed=True).agg(n=("over_hit", "size"), mean_pred=("p_over", "mean"),
                                           obs_rate=("over_hit", "mean")).reset_index(drop=True)


def max_drawdown(curve: pd.Series) -> float:
    if len(curve) == 0:
        return 0.0
    peak = curve.cummax()
    return float(((curve - peak) / peak).min())


def forecast_metrics(preds: pd.DataFrame, p: pd.DataFrame) -> dict:
    d = {"n_rows": int(len(preds)),
         "mae_model": float((preds["mu"] - preds["actual"]).abs().mean()),
         "mae_naive_ewma": float((preds["naive"] - preds["actual"]).abs().mean()),
         "mae_market_proxy": float((preds["mkt_proj"] - preds["actual"]).abs().mean()),
         "crps_model": float(preds["crps"].mean())}
    if len(p):
        np_ = p[~p["push"]]
        d.update({"n_lines": int(len(p)),
                  "mae_line": float((p["line"] - p["actual"]).abs().mean()),
                  "over_rate": float(np_["over_hit"].mean()),
                  "brier": float(((np_["p_over"] - np_["over_hit"]) ** 2).mean()),
                  "brier_market": float(((np_["p_mkt_over"] - np_["over_hit"]) ** 2).mean()),
                  "logloss": float(_ll(np_["p_over"], np_["over_hit"]).mean()),
                  "logloss_raw": float(_ll(np_["p_over_model"], np_["over_hit"]).mean()),
                  "logloss_market": float(_ll(np_["p_mkt_over"], np_["over_hit"]).mean())})
    return d


def bet_metrics(bets: pd.DataFrame) -> dict:
    if len(bets) == 0:
        return {"n_bets": 0, "hit_rate": np.nan, "flat_roi": np.nan, "kelly_roi": np.nan, "turnover": 0.0,
                "profit": 0.0, "n_over": 0, "n_under": 0, "avg_edge": np.nan}
    nb = bets[~bets["push"]]
    return {"n_bets": int(len(bets)), "hit_rate": float(nb["won"].mean()),
            "flat_roi": float(bets["flat_profit"].sum() / len(bets)),
            "kelly_roi": float(bets["profit"].sum() / bets["stake"].sum()) if bets["stake"].sum() > 0 else np.nan,
            "turnover": float(bets["stake"].sum()), "profit": float(bets["profit"].sum()),
            "n_over": int((bets["side"] == "over").sum()), "n_under": int((bets["side"] == "under").sum()),
            "avg_edge": float(bets["edge"].mean())}


def evaluate(preds: pd.DataFrame, bc: dict, history: pd.DataFrame | None = None, p_pre=None) -> dict:
    """Full evaluation for one config on one period. `history` = earlier-period predictions (same line source) the
    stacker may learn from. Returns dict with overall/per-market metrics + artefacts."""
    from .calibration import betting_probs
    p, coefs = p_pre if p_pre is not None else betting_probs(preds, bc, history)
    bets = select_bets(p, bc)
    bets, curve = simulate_bankroll(bets, bc)
    start = bc.get("start_bankroll", 1000.0)
    full_curve = pd.concat([pd.Series([start]), curve["bankroll"]]) if len(curve) else pd.Series([start])
    overall = {**forecast_metrics(preds, p), **bet_metrics(bets),
               "final_bankroll": float(full_curve.iloc[-1]), "max_drawdown": max_drawdown(full_curve)}
    per_market = {}
    for mk, g in preds.groupby("market"):
        pm, bm = p[p["market"] == mk], bets[bets["market"] == mk] if len(bets) else bets
        per_market[mk] = {**forecast_metrics(g, pm), **bet_metrics(bm)}
    per_season = {}
    for s, g in preds.groupby("season"):
        bs = bets[bets["season"] == s] if len(bets) else bets
        per_season[int(s)] = {**forecast_metrics(g, p[p["season"] == s]), **bet_metrics(bs)}
    return {"overall": overall, "per_market": per_market, "per_season": per_season,
            "_p": p, "_bets": bets, "_curve": curve, "_coefs": coefs}


def cluster_logloss(p: pd.DataFrame, col: str = "p_over_model", by=("game_id",)) -> pd.DataFrame:
    """Per-cluster (default: per game) sum of log loss and count — for paired cluster bootstraps."""
    np_ = p[~p["push"]]
    return np_.assign(ll=_ll(np_[col], np_["over_hit"])).groupby(list(by)).agg(ll_sum=("ll", "sum"),
                                                                                 n=("ll", "size"))


def cluster_bootstrap_roi(bets: pd.DataFrame, n=4000, seed=0, key="game_id"):
    """Game-clustered bootstrap of flat-stake ROI: resample games with replacement. Returns (lo, hi) 95% CI."""
    if len(bets) < 2:
        return (np.nan, np.nan)
    g = bets.groupby(key)["flat_profit"].agg(["sum", "size"])
    rng = np.random.default_rng(seed)
    idx = rng.integers(0, len(g), size=(n, len(g)))
    r = g["sum"].values[idx].sum(1) / g["size"].values[idx].sum(1)
    return float(np.quantile(r, 0.025)), float(np.quantile(r, 0.975))

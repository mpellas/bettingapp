"""Market definitions + the pre-game 'which player-games would a book post a line for' universe filter."""
from __future__ import annotations

import pandas as pd

MARKETS = {
    "pass_yds": {"stat": "passing_yards", "label": "QB passing yards"},
    "rush_yds": {"stat": "rushing_yards", "label": "RB/WR/TE rushing yards"},
    "rec_yds": {"stat": "receiving_yards", "label": "RB/WR/TE receiving yards"},
}


def universe_mask(f: pd.DataFrame, market: str, min_proj: float = 20.0) -> pd.Series:
    """Pre-game only: uses position, PROJECTED-starter flag (last game's starter), prior-game count and the public
    projection. (v1 used the actual starter of the game itself: look-ahead, Tester1 B1.)"""
    prior = f["p_n_prior"] >= 2
    if market == "pass_yds":
        return prior & (f["position"] == "QB") & (f["is_proj_starter"] == 1) & f["mkt_proj_pass_yds"].notna()
    if market == "rush_yds":
        return prior & f["position"].isin(["RB", "FB", "WR", "TE"]) & (f["mkt_proj_rush_yds"] >= min_proj)
    if market == "rec_yds":
        return prior & f["position"].isin(["RB", "FB", "WR", "TE"]) & (f["mkt_proj_rec_yds"] >= min_proj)
    raise KeyError(market)

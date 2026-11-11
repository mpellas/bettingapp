import numpy as np
import pandas as pd

from nflprops.betting import simulate_bankroll
from nflprops.calibration import stacked_probs


def _frame(n_weeks=8, per_week=200, seed=0):
    rng = np.random.default_rng(seed)
    rows = []
    for w in range(1, n_weeks + 1):
        pm = rng.uniform(0.4, 0.6, per_week)
        pd_ = np.clip(pm + rng.normal(0, 0.05, per_week), 0.05, 0.95)
        y = (rng.uniform(size=per_week) < pm).astype(float)
        rows.append(pd.DataFrame({"season": 2020, "week": w, "market": "rec_yds", "p_mkt_over": pm,
                                  "p_over_model": pd_, "over_hit": y, "push": False}))
    return pd.concat(rows, ignore_index=True)


def test_stacker_uses_only_earlier_weeks():
    p = _frame()
    a, _ = stacked_probs(p, None, 50.0, 300)
    q = p.copy()
    last = q["week"] == q["week"].max()
    q.loc[last, "over_hit"] = 1 - q.loc[last, "over_hit"]  # change this week's outcomes
    b, _ = stacked_probs(q, None, 50.0, 300)
    assert np.allclose(a[last], b[last])
    # before min_n prior lines the stacker returns the market probability
    first = p["week"] <= 1
    assert np.allclose(a[first], p.loc[first, "p_mkt_over"])


def test_exposure_caps():
    n = 6
    bets = pd.DataFrame({"season": 2020, "week": 1, "game_id": "g1", "team": ["A"] * 4 + ["B"] * 2,
                         "player_id": ["p1", "p1", "p2", "p3", "p4", "p5"], "market": ["rec_yds", "rush_yds"] * 3,
                         "p_side": 0.6, "dec": 1.91, "edge": np.linspace(0.1, 0.05, n), "won": True, "push": False,
                         "flat_profit": 0.91, "kelly_f": 0.16})
    bc = {"kelly_fraction": 1.0, "max_bet_frac": 0.02, "max_game_frac": 0.04, "max_team_frac": 0.03,
          "max_bets_per_game": 3, "max_bets_per_player": 1, "max_week_exposure": 0.2, "start_bankroll": 1000.0}
    out, _ = simulate_bankroll(bets, bc)
    assert out["player_id"].is_unique
    assert len(out) <= 3
    assert out["stake"].sum() <= 0.04 * 1000 + 1e-9
    assert out.groupby("team")["stake"].sum().max() <= 0.03 * 1000 + 1e-9

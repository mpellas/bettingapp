import numpy as np
import pandas as pd

from nflprops.calibration import hier_stacked_probs
from nflprops.config import model_key
from nflprops.snaplines import pick_dc
from nflprops.snapshot import parse_items


def _frame(weeks, per_week=300, c_true=0.5, seed=0, season=2025):
    rng = np.random.default_rng(seed)
    out = []
    for w in weeks:
        for mk in ("pass_yds", "rec_yds", "rush_yds"):
            pm = np.full(per_week, 0.5)
            lm = rng.normal(0, 0.6, per_week)
            y = (rng.uniform(size=per_week) < 1 / (1 + np.exp(-c_true * lm))).astype(float)
            out.append(pd.DataFrame({"season": season, "week": w, "market": mk, "p_mkt_over": pm,
                                     "p_over_model": 1 / (1 + np.exp(-lm)), "over_hit": y, "push": False}))
    return pd.concat(out, ignore_index=True)


def test_hier_stacker_prior_and_no_lookahead():
    p = _frame(range(1, 6))
    a, _, co = hier_stacked_probs(p, None)
    first = p["week"] == 1
    assert np.allclose(a[first], p.loc[first, "p_mkt_over"])          # no history -> market prob (no min_n needed)
    q = p.copy()
    last = q["week"] == 5
    q.loc[last, "over_hit"] = 1 - q.loc[last, "over_hit"]
    b, _, _ = hier_stacked_probs(q, None)
    assert np.allclose(a[last], b[last])                               # week-5 probs use weeks < 5 only
    assert co["c0"].iloc[-1] > 0.1                                     # learns a positive pooled model weight
    assert abs(co[["a_pass_yds", "a_rec_yds", "a_rush_yds"]].iloc[-1]).max() < 0.05   # tight intercept prior


def test_hier_stacker_uses_history():
    h = _frame(range(1, 14), seed=1, season=2025)
    p = _frame([1], seed=2, season=2026)
    _, _, co = hier_stacked_probs(p, h)
    assert co["n"].iloc[0] == len(h) and co["c0"].iloc[0] > 0.1


def test_cache_key_path_independent(tmp_path):
    base = {"model": {}, "markets": [], "data": {}, "universe": {}}
    a = model_key({**base, "lines": {"source": "csv", "csv_path": "data/lines/espn_bet_2025_open_uncertain_timing.csv"}})
    from nflprops import ROOT
    b = model_key({**base, "lines": {"source": "csv",
                                     "csv_path": str(ROOT / "data/lines/espn_bet_2025_open_uncertain_timing.csv")}})
    assert a == b and a["lines"]["csv_sha1"]


def test_snapshot_parse_and_dc():
    items = [{"athlete": {"$ref": ".../athletes/123?x"}, "provider": {"$ref": ".../casinos/100?x"},
              "type": {"name": "Total Receiving Yards (incl. overtime)"}, "lastUpdated": "2026-10-08T20:00Z",
              "current": {"target": {"value": 55.5}}, "open": {"target": {"value": 52.5}}}] * 2 + \
            [{"athlete": {"$ref": ".../athletes/123?x"}, "type": {"name": "Receiving Yards Milestones"},
              "current": {"target": {"value": 100}}}]
    rows = parse_items(items)
    assert len(rows) == 1 and rows[0]["line"] == 55.5 and rows[0]["over_price"] is None
    kick = pd.Timestamp("2026-10-09T00:15Z")
    g = pd.DataFrame({"captured": pd.to_datetime(["2026-10-08T18:00Z", "2026-10-08T21:10Z", "2026-10-08T21:20Z",
                                                  "2026-10-08T23:50Z", "2026-10-09T00:20Z"])})
    d, c = pick_dc(g, kick)
    assert d["captured"].iloc[-1] == pd.Timestamp("2026-10-08T21:10Z")   # last at or before kickoff - 3h
    assert c["captured"].iloc[-1] == pd.Timestamp("2026-10-08T23:50Z")   # last before kickoff, within 30 min


def test_pregame_asof_equivalence():
    """Pre-game rows for a played week must get exactly the features the post-game build gives them."""
    from nflprops import data
    from nflprops.features import feature_columns, load_features
    from nflprops.pregame import pregame_features
    d = data.load(2015, 2024, max_age_h=1e9)
    f, _, _, _, _ = pregame_features(d, 2024, 7)
    full = load_features(2015, 2024, max_age_h=1e9)
    cols = feature_columns("full", True, True)
    a = f[(f["is_pregame_row"] == 1) & (f["season"] == 2024) & (f["week"] == 7)]
    b = full[(full["season"] == 2024) & (full["week"] == 7)]
    m = a.merge(b, on=["player_id", "game_id"], suffixes=("_pre", "_full"))
    assert len(m) > 250
    for c in cols:
        assert np.allclose(m[f"{c}_pre"].astype(float), m[f"{c}_full"].astype(float), equal_nan=True), c

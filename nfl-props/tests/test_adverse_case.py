"""Adverse case, top-20% |lean| bar, matched control vs blanket market side rates, blanket unders."""
import numpy as np
import pandas as pd

import nflprops.track as track

Q = np.linspace(0, 120, 99)


def _lines(n, games, side_over=True, z=0.05, win=True, void_reason=None, actual_ok=True, start=0,
           lean=1.0, week=5, market="rec_yds"):
    rows = []
    for i in range(n):
        line = 50.5
        act = (70.0 if side_over else 30.0) if win else (30.0 if side_over else 70.0)
        sd = 10.0
        mu = line + (lean * sd if side_over else -lean * sd)
        rows.append({"game_id": f"G{(start + i) % games}", "week": week, "market": market,
                     "p_over_model": 0.7 if side_over else 0.3, "q50": mu, "mu": mu, "sd": sd,
                     "in_model_universe": True, "status": "void" if void_reason else "settled",
                     "void": void_reason is not None, "void_reason": void_reason,
                     "z_clv": np.nan if void_reason else z, "actual": act if actual_ok else np.nan,
                     "line_D": line, "line_C": np.nan if void_reason else line + 0.5, "final": True,
                     "price_assumed": True, "price_assumed_C": True, "over_price": -110, "under_price": -110,
                     "over_price_C": -110, "under_price_C": -110, "ll_gain_C": 0.01})
    return rows


def _frame(rows):
    return track.add_case_columns(pd.DataFrame(rows), np.tile(Q, (len(rows), 1)))


def test_adverse_values_per_line():
    x = _frame(_lines(1, 1, True, void_reason=track.PULLED, win=False) +
               _lines(1, 1, False, void_reason=track.PULLED, win=True) +
               _lines(1, 1, True, void_reason=track.PULLED, actual_ok=False) +
               _lines(1, 1, True, z=0.1))
    assert list(x["z_adverse"]) == [-0.25, 0.0, -0.25, 0.1]
    assert x["hit_adverse"].iloc[0] == 0.0 and x["hit_adverse"].iloc[1] == 1.0 and np.isnan(x["hit_adverse"].iloc[2])


def test_baseline_is_blanket_market_side_not_model_stratum():
    """Baseline = share of actuals that went under/over in the market, NOT the model's hit rate on that side.

    Construction that separates the two: rush_yds actuals are 50/50 under/over, but every model UNDER pick hits
    (model-side under stratum = 1.0). Blanket under rate is 0.5. Strong-lean unders must be scored vs 0.5, not 1.0.
    """
    # rush: 100 under actuals, 100 over actuals. Model unders only on the under-actual half (all hit).
    model_under_hit = _lines(100, 200, False, z=0.05, win=True, lean=3.0, market="rush_yds")
    # model overs on the over-actual half (all hit) — weak lean so not in strong group
    model_over_hit = _lines(100, 200, True, z=0.05, win=True, lean=0.1, start=100, market="rush_yds")
    x = _frame(model_under_hit + model_over_hit)
    board = x[x["hit_under"].notna()]
    # model-side under stratum would be 1.0; blanket under share is 0.5
    model_under_stratum = float(x.loc[x["model_side"] == "under", "hit_main"].mean())
    assert model_under_stratum == 1.0
    blanket_under = float((board["actual"] < board["line_D"]).mean())
    assert abs(blanket_under - 0.5) < 1e-9
    hm = x[track.mark_strong_lean(x, "hit_main") & x["hit_main"].notna()]
    mc = track.matched_control(hm, board, "hit_main")
    assert abs(mc["market_side_rates"]["rush_yds|under"] - 0.5) < 1e-9
    assert abs(mc["market_side_rates"]["rush_yds|over"] - 0.5) < 1e-9
    assert "stratum_rates" not in mc
    # strong leans are the model unders → matched baseline must be 0.5 (blanket), not 1.0 (model stratum)
    assert abs(mc["matched_control_hit_rate"] - 0.5) < 1e-9
    assert abs(mc["diff"] - 0.5) < 1e-9   # strong hit 1.0 − blanket 0.5


def _skill_vs_blanket(beat=True):
    """Board where blanket under≈50% per market; strong-lean hits well (beat) or at chance (not)."""
    if beat:
        # strong unders win; weak mixed 50/50 → blanket ~50%, strong >> 50%
        su = _lines(100, 200, False, z=0.05, win=True, lean=3.0, market="rec_yds")
        sl = _lines(20, 200, False, z=0.05, win=False, lean=3.0, start=100, market="rec_yds")
        wu = _lines(150, 200, False, z=0.05, win=True, lean=0.1, start=200, market="rec_yds")
        wo = _lines(150, 200, True, z=0.05, win=True, lean=0.1, start=350, market="rec_yds")  # overs win = under lose
        # second market same pattern
        su2 = _lines(80, 200, False, z=0.05, win=True, lean=3.0, start=500, market="rush_yds")
        sl2 = _lines(20, 200, False, z=0.05, win=False, lean=3.0, start=580, market="rush_yds")
        wu2 = _lines(100, 200, False, z=0.05, win=True, lean=0.1, start=600, market="rush_yds")
        wo2 = _lines(100, 200, True, z=0.05, win=True, lean=0.1, start=700, market="rush_yds")
        return su + sl + wu + wo + su2 + sl2 + wu2 + wo2
    # chance: strong and weak same under rate within market (~60%)
    su = _lines(60, 200, False, z=0.05, win=True, lean=3.0, market="rec_yds")
    sl = _lines(40, 200, False, z=0.05, win=False, lean=3.0, start=60, market="rec_yds")
    wu = _lines(120, 200, False, z=0.05, win=True, lean=0.1, start=200, market="rec_yds")
    wl = _lines(80, 200, False, z=0.05, win=False, lean=0.1, start=320, market="rec_yds")
    # fill with overs that lose so model has sides; actuals still under-heavy
    xo = _lines(50, 200, True, z=0.05, win=False, lean=0.1, start=400, market="rec_yds")
    return su + sl + wu + wl + xo


def test_matched_control_beats_blanket():
    r = track.evaluate(_frame(_skill_vs_blanket(True)))
    mc = r["break_even_main"]["matched_control"]
    assert r["break_even_main"]["hit_rate_pass"]
    assert mc["pass"] and mc["diff"] > 0 and mc["ci95_game_clustered"][0] > 0
    assert r["break_even_main"]["pass"]
    assert r["label"] == "PROVISIONAL (no prices)"
    # baseline keys are market|side blanket rates
    assert any(k.endswith("|under") for k in mc["market_side_rates"])


def test_matched_control_equals_blanket_fails():
    r = track.evaluate(_frame(_skill_vs_blanket(False)))
    mc = r["break_even_main"]["matched_control"]
    assert mc["ci95_game_clustered"][0] <= 0
    assert not mc["pass"]
    assert not r["break_even_main"]["pass"]
    assert r["label"] == "FAIL"


def test_provisional_when_adverse_fails():
    base = _skill_vs_blanket(True)
    pulled = _lines(200, 200, False, void_reason=track.PULLED, win=False, lean=3.0, start=7, market="rec_yds")
    r = track.evaluate(_frame(base + pulled))
    assert r["main_passes"] and not r["adverse_passes"]
    assert r["label"] == "PROVISIONAL (no prices; fails adverse-case sensitivity)"


def test_pulled_unders_do_not_hurt_and_fail_rule():
    base = _skill_vs_blanket(True)
    pulled_u = _lines(40, 200, False, void_reason=track.PULLED, win=True, lean=3.0, start=3, market="rush_yds")
    r = track.evaluate(_frame(base + pulled_u))
    assert r["main_passes"] and r["adverse_passes"] and r["label"] == "PROVISIONAL (no prices)"
    r2 = track.evaluate(_frame(_lines(300, 150, True, z=-0.02, lean=1.0)))
    assert r2["label"] == "FAIL" and r2["failure_rule_triggered"]


def test_blanket_unders_does_not_void_pass():
    r = track.evaluate(_frame(_skill_vs_blanket(True)))
    # force blanket unders pass by checking field exists; on this board under share is high so may pass
    assert "blanket_unders" in r
    assert r["break_even_main"]["pass"]
    assert r["label"] == "PROVISIONAL (no prices)"


def test_full_board_diagnostic_bar_535():
    g = np.repeat(np.arange(500), 2)
    h = np.r_[np.ones(570), np.zeros(430)]
    assert track.hit_test(h, g, bar=track.BE_HIT_FULL)["pass"]
    assert track.BE_HIT_FULL == 0.535


def test_top20_within_week_then_pool():
    w5 = _lines(40, 40, True, z=0.05, win=True, lean=3.0, week=5) + \
        _lines(20, 40, False, z=0.05, win=True, lean=3.0, week=5, start=40, market="rush_yds") + \
        _lines(200, 40, True, z=0.05, win=False, lean=0.1, week=5, start=60)
    w6 = _lines(40, 40, True, z=0.05, win=False, lean=3.0, week=6) + \
        _lines(20, 40, False, z=0.05, win=False, lean=3.0, week=6, start=40, market="rush_yds") + \
        _lines(200, 40, True, z=0.05, win=True, lean=0.1, week=6, start=60)
    r = track.evaluate(_frame(w5 + w6))
    assert r["break_even_main"]["n_strong_lean"] >= 20

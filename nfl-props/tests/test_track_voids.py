"""Track scoring starts from the D snapshot, voids every unscorable line with a reason, writes a void report, and
reports the primary metric voids-excluded and voids-as-zero."""
import json

import numpy as np
import pandas as pd

import nflprops.data as data_mod
import nflprops.track as track


def test_track_voids(tmp_path, monkeypatch):
    D_ = tmp_path / "data"
    (D_ / "lines").mkdir(parents=True)
    pdir = D_ / "predictions" / "2026_wk05"
    pdir.mkdir(parents=True)
    monkeypatch.setattr(track, "DATA", D_)
    monkeypatch.setattr(track, "TRACK", D_ / "track")
    sch = pd.DataFrame({"season": [2026, 2026], "week": [5, 5], "game_id": ["G_DONE", "G_LATER"],
                        "espn": ["1", "2"], "gameday": ["2026-10-04", "2099-01-01"], "gametime": ["13:00", "13:00"],
                        "home_score": [21.0, np.nan], "game_type": ["REG", "REG"]})
    monkeypatch.setattr(data_mod, "load", lambda *a, **k: {"schedules": sch})
    monkeypatch.setattr(track, "history", lambda cfg: pd.DataFrame())
    act = pd.DataFrame({"player_id": ["A"], "game_id": ["G_DONE"], "market": ["rec_yds"], "actual": [55.0]})
    monkeypatch.setattr(track, "actuals", lambda d, s, w: act)
    base = dict(season=2026, week=5, over_price=-110, under_price=-110, price_assumed=True, book="t")
    rows = [("A", "a", "1", "rec_yds", 50.5), ("B", "b", "1", "rec_yds", 40.5), ("C", "c", "1", "rec_yds", 30.5),
            ("X", "x", "1", "rush_yds", 20.5), ("E", "e", "2", "rec_yds", 60.5)]
    D = pd.DataFrame([dict(base, player_id=p, espn_id=p.lower(), player_name=p, event_id=e, market=m, line=L,
                           line_open=L) for p, _, e, m, L in rows])
    D.to_csv(D_ / "lines" / "snap_2026_wk5_D.csv", index=False)
    C = D[D["player_id"].isin(["A", "C", "E"])].assign(line=lambda t: t["line"] + 2)
    C.to_csv(D_ / "lines" / "snap_2026_wk5_C.csv", index=False)
    q = np.linspace(0, 120, 99)
    P = pd.DataFrame([{"player_id": p, "game_id": "G_DONE" if e == "1" else "G_LATER", "market": m, "mu": 60.0,
                       "median": 60.0, "p_over_D": 0.6, "line_D": _L, "in_model_universe": True, **{c: v for c, v in zip(track.QCOLS, q)}}
                      for p, _, e, m, _L in rows if p != "X"])
    P.to_parquet(pdir / "pregame_T.parquet")
    pd.DataFrame([{"season": 2026, "week": 5, "event_id": "1", "game_id": "G_DONE", "player_id": None,
                   "player_name": "X", "market": "rush_yds", "line_D": 20.5,
                   "void_reason": "no player row: ESPN athlete id has no GSIS match in the nflverse players table",
                   "stage": "pregame"}]).to_csv(pdir / "pregame_T_voids.csv", index=False)
    (pdir / "pregame_T.meta.json").write_text(json.dumps({
        "mode": "snapshot (D lines)", "created_at_utc": "2026-10-01T00:00:00+00:00",
        "files": ["data/predictions/2026_wk05/pregame_T.parquet"], "sha256_parquet": "x",
        "void_report": "data/predictions/2026_wk05/pregame_T_voids.csv"}))
    cfg = {"data": {"first_season": 2015}, "betting": {"stacker_prior": None, "edge_threshold": 0.04},
           "diagnostic_policy": {}}
    s = track.week(2026, 5, cfg)
    assert s["n_lines_D"] == 5 and s["n_scored"] == 1 and s["n_pending"] == 1 and s["n_void"] == 3
    v = pd.read_csv(D_ / "track" / "2026_wk05_voids.csv")
    reasons = dict(zip(v["player_name"], v["void_reason"]))
    assert reasons["B"] == "pulled_before_close"     # game has a C capture; B is missing from it
    assert reasons["C"].startswith("player inactive")
    assert reasons["X"].startswith("no player row")
    z = s["z_clv"]
    assert z["voids_excluded"]["n"] == 1 and z["voids_as_zero"]["n"] == 4
    assert np.isclose(z["voids_as_zero"]["mean"], z["voids_excluded"]["mean"] / 4)
    assert s["n_out_of_model_scope"] == 0
    assert s["ll_gain_vs_ln2_at_C"]["n"] == 1     # only the settled, non-void line with a C counts


def test_break_even_with_prices():
    q = np.tile(np.linspace(0, 120, 99), (40, 1))
    base = pd.DataFrame({"game_id": np.repeat([f"G{i}" for i in range(20)], 2), "line_D": 50.5, "line_C": 50.5,
                         "p_over_model": 0.7, "price_assumed": False, "price_assumed_C": False})
    # flat -110/-110 everywhere = treated as no prices
    flat = base.assign(over_price=-110, under_price=-110, over_price_C=-110, under_price_C=-110)
    assert track.break_even_with_prices(flat, q)["eligible"] is False
    # real, varying prices; close moved strongly to the model's (over) side -> passes the bar
    rng = np.random.default_rng(0)
    op = rng.choice([-105, -110, -115, -120], 40)
    real = base.assign(over_price=op, under_price=-110, over_price_C=-250, under_price_C=190)
    r = track.break_even_with_prices(real, q)
    assert r["eligible"] and r["pass"] and r["mean_q_side"] > r["break_even_bar"]
    # assumed prices on most lines -> not eligible
    assert track.break_even_with_prices(real.assign(price_assumed=True), q)["eligible"] is False


def _bet(void, reason, actual, line=50.5, side="over"):
    won = (actual > line) if side == "over" else (actual < line)
    fp = np.nan if actual is None or np.isnan(actual) else (0.0 if actual == line else (0.909 if won else -1.0))
    return {"void": void, "void_reason": reason, "final": True, "actual": actual, "line": line, "side": side,
            "flat_profit": fp}


def test_dk_settlement_pulled_lines():
    b = pd.DataFrame([
        _bet(True, track.PULLED, 70.0),            # pulled but played: stands, settled on the stat (over wins)
        _bet(True, track.PULLED, 10.0),            # pulled but played: stands, loses
        _bet(True, track.PULLED, np.nan),          # pulled and did not play: refund
        _bet(True, track.INACTIVE, np.nan),        # inactive: refund
        _bet(False, None, 60.0),                   # normal settled line
        _bet(True, track.NO_C, 0.0),               # our close capture failed, he played (0 yds snap): stands
    ])
    s = track.settle_bets(b)
    assert list(s["bet_status"]) == ["settled", "settled", "refunded", "refunded", "settled", "settled"]
    assert np.allclose(s["flat_profit"].values, [0.909, -1.0, 0.0, 0.0, 0.909, -1.0])

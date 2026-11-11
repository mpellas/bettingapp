"""Snapshot-level voids: duplicate/alternate lines (same player+market, >1 line in D) and kickoff moved earlier
(D < 3 h before the ACTUAL kickoff). Both must be voided with a reason, never re-picked or silently deduped."""
import hashlib
import json

import numpy as np
import pandas as pd

import nflprops.data as data_mod
import nflprops.snaplines as sl
import nflprops.track as track


def _item(espn, line, market="Total Receiving Yards (incl. overtime)"):
    return {"athlete": {"$ref": f".../athletes/{espn}?x"}, "provider": {"$ref": ".../casinos/100?x"},
            "type": {"name": market}, "lastUpdated": "2026-10-04T15:00Z",
            "current": {"target": {"value": line}}, "open": {"target": {"value": line}}}


def _setup(tmp_path, monkeypatch, captures):
    snap = tmp_path / "data" / "snapshots"
    cache = tmp_path / "data" / "cache"
    cache.mkdir(parents=True)
    log = snap / "capture_log.jsonl"
    recs = []
    for ev, cap_utc, kick_utc, items in captures:
        day = snap / pd.Timestamp(cap_utc).tz_convert(sl.PT).strftime("%Y-%m-%d")
        day.mkdir(parents=True, exist_ok=True)
        name = f"{ev}_100_{pd.Timestamp(cap_utc).strftime('%Y%m%dT%H%M%SZ')}_p1.json"
        b = json.dumps({"items": items}).encode()
        (day / name).write_bytes(b)
        recs.append({"captured_at_utc": cap_utc, "captured_at_pt": pd.Timestamp(cap_utc).tz_convert(sl.PT).isoformat(),
                     "event_id": ev, "season": 2026, "season_type": 2, "week": 5, "name": f"G{ev}",
                     "kickoff_utc": kick_utc, "files": [{"file": name, "sha256": hashlib.sha256(b).hexdigest()}]})
    log.write_text("".join(json.dumps(r) + "\n" for r in recs))
    pd.DataFrame({"gsis_id": ["00-A", "00-B", "00-C"], "display_name": ["A", "B", "C"],
                  "espn_id": ["1", "2", "3"]}).to_parquet(cache / "players.parquet")
    monkeypatch.setattr(sl, "LOG", log)
    monkeypatch.setattr(sl, "SNAP", snap)
    monkeypatch.setattr(sl, "CACHE", cache)
    monkeypatch.setattr(sl, "DATA", tmp_path / "data")
    return tmp_path / "data"


def test_duplicate_and_kickoff_moved(tmp_path, monkeypatch):
    caps = [
        # event 10: kickoff reported 20:00Z at D time (D at 16:30Z = 3.5 h before) ...
        ("10", "2026-10-04T16:30:00+00:00", "2026-10-04T20:00:00+00:00", [_item(1, 50.5)]),
        # ... a later capture reports kickoff moved EARLIER to 18:00Z -> D is only 1.5 h before the actual kickoff
        ("10", "2026-10-04T17:45:00+00:00", "2026-10-04T18:00:00+00:00", [_item(1, 52.5)]),
        # event 11: normal timing; athlete 2 has two different rec lines (alternate) -> both void; athlete 3 fine
        ("11", "2026-10-04T16:30:00+00:00", "2026-10-04T20:00:00+00:00",
         [_item(2, 40.5), _item(2, 45.5), _item(3, 30.5)]),
        ("11", "2026-10-04T19:45:00+00:00", "2026-10-04T20:00:00+00:00", [_item(2, 41.5), _item(3, 31.5)]),
    ]
    D_ = _setup(tmp_path, monkeypatch, caps)
    r = sl.derive(2026, 5)
    D = pd.read_csv(D_ / "lines" / "snap_2026_wk5_D.csv", dtype={"event_id": str, "espn_id": str})
    cov = {c["event_id"]: c for c in r["coverage"]}
    # event 10: actual kickoff = earliest reported (18:00Z), D is the real-time decision capture, voided
    assert cov["10"]["kickoff_actual_pt"].startswith("2026-10-04T11:00")
    v10 = D[D["event_id"] == "10"]["void_reason"]
    assert len(v10) == 1 and v10.iloc[0].startswith("kickoff_moved")
    assert cov["10"]["C"] is not None        # the 17:45Z capture is within 30 min of the ACTUAL kickoff
    # event 11: both alternate lines of athlete 2 are void; athlete 3 is not
    e11 = D[D["event_id"] == "11"].set_index("line")
    assert e11.loc[40.5, "void_reason"].startswith("duplicate_line")
    assert e11.loc[45.5, "void_reason"].startswith("duplicate_line")
    assert pd.isna(e11.loc[30.5, "void_reason"])
    assert r["files"]["D"]["void_rows"] == 3


def test_latest_kickoff_not_used():
    """Regression: with an earlier kickoff reported later, a capture inside the 3 h window of the actual kickoff
    must not become D for that kickoff, and C is measured from the actual (earliest) kickoff."""
    g = pd.DataFrame({"captured": pd.to_datetime(["2026-10-04T14:00Z", "2026-10-04T16:30Z", "2026-10-04T17:45Z"]),
                      "kick": pd.to_datetime(["2026-10-04T20:00Z", "2026-10-04T20:00Z", "2026-10-04T18:00Z"])})
    kick, _ = sl.actual_kickoff(g)
    assert kick == pd.Timestamp("2026-10-04T18:00Z")
    d, c = sl.pick_dc(g, kick)
    assert d["captured"].iloc[-1] == pd.Timestamp("2026-10-04T16:30Z")   # real-time decision (then voided)
    assert d["captured"].iloc[-1] > kick - pd.Timedelta(hours=3)
    assert c["captured"].iloc[-1] == pd.Timestamp("2026-10-04T17:45Z")


def test_track_honors_snapshot_voids(tmp_path, monkeypatch):
    D_ = tmp_path / "data"
    (D_ / "lines").mkdir(parents=True)
    monkeypatch.setattr(track, "DATA", D_)
    monkeypatch.setattr(track, "TRACK", D_ / "track")
    sch = pd.DataFrame({"season": [2026], "week": [5], "game_id": ["G1"], "espn": ["1"], "gameday": ["2026-10-04"],
                        "gametime": ["13:00"], "home_score": [21.0], "game_type": ["REG"]})
    monkeypatch.setattr(data_mod, "load", lambda *a, **k: {"schedules": sch})
    monkeypatch.setattr(track, "history", lambda cfg: pd.DataFrame())
    monkeypatch.setattr(track, "actuals", lambda d, s, w: pd.DataFrame(
        {"player_id": ["A", "B"], "game_id": ["G1"] * 2, "market": ["rec_yds"] * 2, "actual": [10.0, 20.0]}))
    base = dict(season=2026, week=5, event_id="1", market="rec_yds", over_price=-110, under_price=-110,
                price_assumed=True, line_open=1.0, kickoff_actual_utc="2026-10-04T17:00:00+00:00")
    D = pd.DataFrame([dict(base, player_id="A", espn_id="a", player_name="A", line=50.5,
                           void_reason="kickoff_moved: test"),
                      dict(base, player_id="B", espn_id="b", player_name="B", line=40.5,
                           void_reason="duplicate_line: test"),
                      dict(base, player_id="B", espn_id="b", player_name="B", line=45.5,
                           void_reason="duplicate_line: test")])
    D.to_csv(D_ / "lines" / "snap_2026_wk5_D.csv", index=False)
    D.assign(void_reason=np.nan).drop_duplicates("player_id").to_csv(D_ / "lines" / "snap_2026_wk5_C.csv",
                                                                     index=False)
    cfg = {"data": {"first_season": 2015}, "betting": {"stacker_prior": None}, "diagnostic_policy": {}}
    s = track.week(2026, 5, cfg)
    assert s["n_lines_D"] == 3 and s["n_void"] == 3
    v = pd.read_csv(D_ / "track" / "2026_wk05_voids.csv")
    assert sorted(v["void_reason"].str.split(":").str[0]) == ["duplicate_line", "duplicate_line", "kickoff_moved"]


def test_c_only_from_last_capture(tmp_path, monkeypatch):
    """C is the last capture before kickoff only: a line seen earlier in the window but missing from the last capture
    is pulled (recorded with last-seen / first-missing times), never filled from an earlier capture. A last capture
    > 30 min before kickoff means no C at all (capture failure)."""
    caps = [("20", "2026-10-04T16:00:00+00:00", "2026-10-04T20:00:00+00:00", [_item(1, 50.5), _item(3, 30.5)]),
            ("20", "2026-10-04T19:40:00+00:00", "2026-10-04T20:00:00+00:00", [_item(1, 51.5), _item(3, 31.5)]),
            ("20", "2026-10-04T19:55:00+00:00", "2026-10-04T20:00:00+00:00", [_item(3, 32.5)]),
            # event 21: last capture before kickoff is 40 min out -> no C
            ("21", "2026-10-04T16:00:00+00:00", "2026-10-04T20:00:00+00:00", [_item(2, 40.5)]),
            ("21", "2026-10-04T19:20:00+00:00", "2026-10-04T20:00:00+00:00", [_item(2, 40.5)])]
    D_ = _setup(tmp_path, monkeypatch, caps)
    r = sl.derive(2026, 5)
    C = pd.read_csv(D_ / "lines" / "snap_2026_wk5_C.csv", dtype={"event_id": str, "espn_id": str})
    assert set(C["event_id"]) == {"20"} and list(C["espn_id"]) == ["3"] and C["line"].iloc[0] == 32.5
    pu = pd.read_csv(D_ / "lines" / "snap_2026_wk5_pulled.csv", dtype={"espn_id": str})
    assert list(pu["espn_id"]) == ["1"]
    assert pu["last_seen_pt"].iloc[0].startswith("2026-10-04T12:40")
    assert pu["first_missing_pt"].iloc[0].startswith("2026-10-04T12:55")
    cov = {c["event_id"]: c for c in r["coverage"]}
    assert cov["21"]["C"] is None


def test_empty_last_pass_skipped(tmp_path, monkeypatch):
    """An empty last pass in the close window is skipped: C comes from the full capture 3 minutes earlier. A window
    in which every capture is empty means no C (capture failure). Missing lines in the chosen capture are pulled."""
    caps = [("30", "2026-10-04T16:00:00+00:00", "2026-10-04T20:00:00+00:00", [_item(1, 50.5), _item(3, 30.5)]),
            ("30", "2026-10-04T19:54:00+00:00", "2026-10-04T20:00:00+00:00", [_item(3, 31.5)]),
            ("30", "2026-10-04T19:57:00+00:00", "2026-10-04T20:00:00+00:00", []),          # empty last pass
            ("31", "2026-10-04T16:00:00+00:00", "2026-10-04T20:00:00+00:00", [_item(2, 40.5)]),
            ("31", "2026-10-04T19:45:00+00:00", "2026-10-04T20:00:00+00:00", []),
            ("31", "2026-10-04T19:57:00+00:00", "2026-10-04T20:00:00+00:00", [])]
    D_ = _setup(tmp_path, monkeypatch, caps)
    r = sl.derive(2026, 5)
    cov = {c["event_id"]: c for c in r["coverage"]}
    assert cov["30"]["C"].startswith("2026-10-04T12:54") and cov["30"]["C_empty_captures_skipped"] == 1
    C = pd.read_csv(D_ / "lines" / "snap_2026_wk5_C.csv", dtype={"event_id": str, "espn_id": str})
    assert list(C["espn_id"]) == ["3"] and C["line"].iloc[0] == 31.5
    pu = pd.read_csv(D_ / "lines" / "snap_2026_wk5_pulled.csv", dtype={"espn_id": str})
    assert list(pu["espn_id"]) == ["1"]              # missing from the chosen capture: pulled, no fallback
    assert cov["31"]["C"] is None and "no lines" in cov["31"]["C_note"]


def test_empty_d_skipped(tmp_path, monkeypatch):
    """An empty last D-eligible capture is skipped: D comes from the prior non-empty decision-window capture.
    If every D-eligible capture is empty, there is no D (capture failure)."""
    caps = [
        # event 40: D window has a full capture then an empty later one (still <= kick-3h)
        ("40", "2026-10-04T15:00:00+00:00", "2026-10-04T20:00:00+00:00", [_item(1, 50.5), _item(3, 30.5)]),
        ("40", "2026-10-04T16:50:00+00:00", "2026-10-04T20:00:00+00:00", []),   # empty, still D-eligible
        ("40", "2026-10-04T19:50:00+00:00", "2026-10-04T20:00:00+00:00", [_item(1, 51.5), _item(3, 31.5)]),
        # event 41: only empty captures in the D window
        ("41", "2026-10-04T15:00:00+00:00", "2026-10-04T20:00:00+00:00", []),
        ("41", "2026-10-04T16:50:00+00:00", "2026-10-04T20:00:00+00:00", []),
        ("41", "2026-10-04T19:50:00+00:00", "2026-10-04T20:00:00+00:00", [_item(2, 40.5)]),
    ]
    D_ = _setup(tmp_path, monkeypatch, caps)
    r = sl.derive(2026, 5)
    cov = {c["event_id"]: c for c in r["coverage"]}
    assert cov["40"]["D"].startswith("2026-10-04T08:00") and cov["40"]["D_empty_captures_skipped"] == 1
    D = pd.read_csv(D_ / "lines" / "snap_2026_wk5_D.csv", dtype={"event_id": str, "espn_id": str})
    assert set(D.loc[D["event_id"] == "40", "espn_id"]) == {"1", "3"}
    assert D.loc[D["event_id"] == "40", "line"].tolist() == [50.5, 30.5]
    assert cov["41"]["D"] is None and "no lines" in cov["41"]["D_note"]
    assert "41" not in set(D["event_id"])

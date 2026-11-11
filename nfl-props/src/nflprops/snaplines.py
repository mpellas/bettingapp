"""Derive the DECISION line (D) and the CLOSE (C) per game from the raw snapshots (data/snapshots/).

    D = the LAST capture in the decision window (captured <= kickoff-as-reported-in-that-capture - 3 h) that has
        pass/rush/rec yards lines for the game; empty captures (zero such lines) are skipped. Only if no capture in
        the window has lines is there no D (capture failure).                           (the line any bet is placed at)
    C = the LAST capture in the close window (actual kickoff - 30 min <= captured < kickoff) that has lines for the
        game; empty captures are skipped the same way. Line by line there is no fallback: a D line missing from that
        C capture was pulled before the close (track voids it as 'pulled_before_close'); when it disappeared is
        written to ..._pulled.csv. Only if no capture in the window has lines is there no C (capture failure).
ACTUAL kickoff = the EARLIEST kickoff reported for the event by any capture or by the nflverse schedule (a kickoff
that moves earlier must not let a late capture count as D or C). If D turns out to be < 3 h before the actual
kickoff, every line of that game gets d_void_reason "kickoff_moved" (never re-picked from an older capture).
A (player, market) with more than one line in a snapshot gets void_reason "duplicate_line" (ESPN/DraftKings items
carry no main-line flag, so no line is preferred; all of them are voided, never the first row kept).
Only the raw files listed in capture_log.jsonl are read, and each file's sha256 is re-checked against the log.
Output (CsvLines schema + extras): data/lines/snap_<season>_wk<week>_D.csv and ..._C.csv, plus a coverage summary.
DraftKings-via-ESPN carries no prices: rows then get over/under = -110 with price_assumed = True (flagged).

    python -m nflprops.snaplines --season 2026 --week 5
"""
from __future__ import annotations

import argparse
import datetime as dt
import json

import pandas as pd

from . import CACHE, DATA
from .snapshot import LOG, PT, SNAP, parse_items, sha256


def _captures(season: int, week: int) -> pd.DataFrame:
    recs = [json.loads(line) for line in LOG.read_text().splitlines()] if LOG.exists() else []
    df = pd.DataFrame([r for r in recs if r["season"] == season and r["week"] == week and r.get("season_type", 2) == 2])
    if len(df):
        df["captured"] = pd.to_datetime(df["captured_at_utc"], utc=True)
        df["kick"] = pd.to_datetime(df["kickoff_utc"], utc=True)
    return df


def _rows(rec: dict) -> list[dict]:
    day = SNAP / pd.Timestamp(rec["captured_at_utc"]).tz_convert(PT).strftime("%Y-%m-%d")
    items = []
    for f in rec["files"]:
        if "_odds_" in f["file"]:
            continue
        b = (day / f["file"]).read_bytes()
        if sha256(b) != f["sha256"]:
            raise ValueError(f"hash mismatch for {f['file']}: snapshot was modified")
        items += json.loads(b).get("items", [])
    return parse_items(items)


def pick_dc(g: pd.DataFrame, kick: pd.Timestamp, d_hours: float = 3.0, c_minutes: float = 30.0):
    """Candidate captures for D (captured <= kickoff-as-reported-in-that-capture - d_hours; column `kick`) and the
    close window (actual kickoff - c_minutes <= captured < actual kickoff). derive takes D and C from the LAST
    NON-EMPTY capture in each window (empty = zero pass/rush/rec yards lines for the game)."""
    rep = g["kick"] if "kick" in g else pd.Series(kick, index=g.index)
    d = g[g["captured"] <= rep - pd.Timedelta(hours=d_hours)]
    c = g[(g["captured"] < kick) & (g["captured"] >= kick - pd.Timedelta(minutes=c_minutes))]
    return d, c


def schedule_kickoffs(season: int, week: int) -> dict:
    """ESPN event id -> nflverse scheduled kickoff (UTC), if the schedule cache has it."""
    p = CACHE / "schedules.parquet"
    if not p.exists():
        return {}
    s = pd.read_parquet(p)
    s = s[(s["season"] == season) & (s["week"] == week) & s["espn"].notna() & s["gametime"].notna()]
    k = pd.to_datetime(s["gameday"] + " " + s["gametime"]).dt.tz_localize("America/New_York").dt.tz_convert("UTC")
    return dict(zip(s["espn"].astype(str).str.replace(r"\.0$", "", regex=True), k))


def actual_kickoff(g: pd.DataFrame, sched_kick=None) -> tuple[pd.Timestamp, str]:
    """Earliest kickoff reported by any capture or the nflverse schedule."""
    k, src = g["kick"].min(), "ESPN (earliest reported in captures)"
    if sched_kick is not None and pd.notna(sched_kick) and sched_kick < k:
        k, src = sched_kick, "nflverse schedule (earlier than ESPN)"
    return k, src


def flag_duplicates(df: pd.DataFrame) -> pd.Series:
    """True for every row whose (player, market) has more than one distinct line in the same event/snapshot."""
    who = df["player_id"].fillna("espn:" + df["espn_id"].astype(str))
    n = df.assign(_w=who).groupby(["event_id", "_w", "market"])["line"].transform("nunique")
    return n > 1


def derive(season: int, week: int, d_hours: float = 3.0, c_minutes: float = 30.0) -> dict:
    cap = _captures(season, week)
    out, cov, pulled = {"D": [], "C": []}, [], []
    if len(cap) == 0:
        return {"coverage": [], "files": {}}
    pl = pd.read_parquet(CACHE / "players.parquet")[["gsis_id", "display_name", "espn_id"]].dropna(subset=["espn_id"])
    pl["espn_id"] = pl["espn_id"].astype(str).str.replace(r"\.0$", "", regex=True)
    sk = schedule_kickoffs(season, week)
    for ev, g in cap.groupby("event_id"):
        g = g.sort_values("captured")
        kick, ksrc = actual_kickoff(g, sk.get(str(ev)))
        d, c = pick_dc(g, kick, d_hours, c_minutes)
        row = {"event_id": ev, "name": g["name"].iloc[-1], "kickoff_actual_pt": kick.tz_convert(PT).isoformat(),
               "kickoff_source": ksrc, "kickoffs_reported": g["kick"].nunique(), "n_captures": len(g)}
        d_rec = c_rec = None
        for kind, sel in (("D", d), ("C", c)):
            if len(sel) == 0:
                row[kind] = None
                continue
            # last NON-EMPTY capture in the window; empty passes (zero yardage lines) are skipped
            rec, rows, n_empty = None, [], 0
            for cand in reversed(sel.to_dict("records")):
                rows = _rows(cand)
                if rows:
                    rec = cand
                    break
                n_empty += 1
            row[f"{kind}_empty_captures_skipped"] = n_empty
            if rec is None:
                win = "decision" if kind == "D" else "close"
                row[kind] = None
                row[f"{kind}_note"] = f"all {n_empty} captures in the {win} window had no lines"
                continue
            vr = None
            if kind == "D" and rec["captured"] > kick - pd.Timedelta(hours=d_hours):
                vr = (f"kickoff_moved: D captured {rec['captured_at_pt']} for kickoff "
                      f"{rec['kick'].tz_convert(PT).isoformat()}, but actual kickoff is "
                      f"{kick.tz_convert(PT).isoformat()} (< {d_hours:g} h)")
            row[kind] = rec["captured_at_pt"]
            row[f"n_lines_{kind}"] = len(rows)
            if kind == "D":
                row["D_void"] = vr
                d_rec = rec
            else:
                c_rec = rec
            for r in rows:
                out[kind].append({**r, "season": season, "week": week, "event_id": ev,
                                  "captured_at_utc": rec["captured_at_utc"],
                                  "kickoff_at_capture_utc": rec["kick"].isoformat(),
                                  "kickoff_actual_utc": kick.isoformat(),
                                  "minutes_before_kickoff": round((kick - rec["captured"]).total_seconds() / 60, 1),
                                  "void_reason": vr})
        # pulled lines: in D but absent from the C capture -> when did they disappear?
        if row.get("D") and row.get("C") and d_rec is not None:
            dset = {(r["espn_id"], r["market"]) for r in out["D"] if r["event_id"] == ev}
            cset = {(r["espn_id"], r["market"]) for r in out["C"] if r["event_id"] == ev}
            gone = dset - cset
            if gone:
                after = g[g["captured"] >= d_rec["captured"]]
                seen = {k: None for k in gone}
                first_missing = {k: None for k in gone}
                for rec in after.to_dict("records"):
                    have = {(r["espn_id"], r["market"]) for r in _rows(rec)}
                    if not have:                 # empty pass: says nothing about individual lines
                        continue
                    for k in gone:
                        if k in have:
                            seen[k], first_missing[k] = rec["captured_at_pt"], None
                        elif first_missing[k] is None:
                            first_missing[k] = rec["captured_at_pt"]
                for k in sorted(gone):
                    pulled.append({"season": season, "week": week, "event_id": ev, "espn_id": k[0], "market": k[1],
                                   "last_seen_pt": seen[k], "first_missing_pt": first_missing[k],
                                   "c_capture_pt": row["C"]})
            row["n_pulled_before_close"] = len(gone)
        cov.append(row)
    files = {}
    pp = DATA / "lines" / f"snap_{season}_wk{week}_pulled.csv"
    pp.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(pulled, columns=["season", "week", "event_id", "espn_id", "market", "last_seen_pt",
                                  "first_missing_pt", "c_capture_pt"]).to_csv(pp, index=False)
    files["pulled"] = {"path": str(pp.relative_to(DATA.parent)), "rows": len(pulled)}
    for kind, rows in out.items():
        if not rows:
            continue
        df = pd.DataFrame(rows).merge(pl, on="espn_id", how="left").rename(columns={"gsis_id": "player_id",
                                                                                   "display_name": "player_name"})
        df["price_assumed"] = df["over_price"].isna() | df["under_price"].isna()
        df.loc[df["price_assumed"], ["over_price", "under_price"]] = -110
        df["book"] = "DraftKings via ESPN core API (provider " + df["provider"].astype(str) + ")"
        dup = flag_duplicates(df)
        df.loc[dup, "void_reason"] = df.loc[dup, "void_reason"].fillna("").map(
            lambda v: (v + "; " if v else "") + "duplicate_line: more than one line for this player+market in the snapshot")
        p = DATA / "lines" / f"snap_{season}_wk{week}_{kind}.csv"
        p.parent.mkdir(parents=True, exist_ok=True)
        cols = ["season", "week", "player_id", "player_name", "market", "line", "over_price", "under_price",
                "price_assumed", "line_open", "book", "event_id", "espn_id", "captured_at_utc",
                "minutes_before_kickoff", "kickoff_at_capture_utc", "kickoff_actual_utc", "espn_last_updated",
                "void_reason"]
        df[cols].to_csv(p, index=False)
        files[kind] = {"path": str(p.relative_to(DATA.parent)), "rows": len(df),
                       "unmatched_gsis": int(df["player_id"].isna().sum()),
                       "void_rows": df["void_reason"].notna().sum().item()}
    return {"coverage": cov, "files": files}


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--season", type=int, required=True)
    ap.add_argument("--week", type=int, required=True)
    ap.add_argument("--d-hours", type=float, default=3.0)
    ap.add_argument("--c-minutes", type=float, default=30.0)
    a = ap.parse_args()
    r = derive(a.season, a.week, a.d_hours, a.c_minutes)
    print(pd.DataFrame(r["coverage"]).to_string(index=False) if r["coverage"] else "no captures for that week")
    print(json.dumps(r["files"], indent=1))
    _ = dt

#!/usr/bin/env python3
"""Paper-only NHL SOG team-volume shadow log.

Locked rule (do not refit):
  pred_team_sog = 0.5 * team_sf_r20 + 0.5 * opp_sa_r20
  proj_vol      = share_w_r10 * pred_team_sog
  share_w_r10   = (mean SOG in the player's prior 10 games)
                  / (mean team SOG in those same 10 games)
  team_sf_r20   = the shooter's team's shots-for, prior 20 games (min 3)
  opp_sa_r20    = the opponent's shots-against, prior 20 games (min 3)

All rates are strictly as-of the game (prior games only). This script does not
change the frozen model, gates, picks/, or sheets/, and it places no bets.

Usage:  python3 majority/shadow_volume.py

Writes majority/shadow_volume.csv idempotently (one row per
(date, gameId, nhl_id, side, line)). Existing cohort labels are kept.
Sides with slate date before 2026-11-11 are tagged pre-registration and do
not count toward the 100-side forward bar. Result and units are copied from
majority/graded_sides.csv at the recorded price; no prices are invented.

No Odds API or Fliff credits. No network: features come from data/s*.pkl.
"""
from __future__ import annotations

import glob
import os
import sys
from datetime import datetime
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
os.chdir(ROOT)

OUT = os.path.join(HERE, "shadow_volume.csv")
GRADED = os.path.join(HERE, "graded_sides.csv")
FORWARD_START = 20261111  # slate date; forward bar starts at 0 on first run
PT = ZoneInfo("America/Los_Angeles")

# Official names as they appear in graded_sides.csv "Away at Home" strings.
TEAM_ABBREV = {
    "Anaheim Ducks": "ANA",
    "Boston Bruins": "BOS",
    "Buffalo Sabres": "BUF",
    "Calgary Flames": "CGY",
    "Carolina Hurricanes": "CAR",
    "Chicago Blackhawks": "CHI",
    "Colorado Avalanche": "COL",
    "Columbus Blue Jackets": "CBJ",
    "Dallas Stars": "DAL",
    "Detroit Red Wings": "DET",
    "Edmonton Oilers": "EDM",
    "Florida Panthers": "FLA",
    "Los Angeles Kings": "LAK",
    "Minnesota Wild": "MIN",
    "Montreal Canadiens": "MTL",
    "Montréal Canadiens": "MTL",
    "Nashville Predators": "NSH",
    "New Jersey Devils": "NJD",
    "New York Islanders": "NYI",
    "New York Rangers": "NYR",
    "Ottawa Senators": "OTT",
    "Philadelphia Flyers": "PHI",
    "Pittsburgh Penguins": "PIT",
    "San Jose Sharks": "SJS",
    "Seattle Kraken": "SEA",
    "St. Louis Blues": "STL",
    "Tampa Bay Lightning": "TBL",
    "Toronto Maple Leafs": "TOR",
    "Utah Mammoth": "UTA",
    "Utah Hockey Club": "UTA",
    "Vancouver Canucks": "VAN",
    "Vegas Golden Knights": "VGK",
    "Washington Capitals": "WSH",
    "Winnipeg Jets": "WPG",
}

KEY = ["date", "gameId", "nhl_id", "side", "line"]
COLS = [
    "date", "list_id", "game", "gameId", "nhl_id", "player", "side", "line",
    "team", "opponent",
    "team_sf_r20", "opp_sa_r20", "pred_team_sog",
    "shots_r10", "team_sog_r10", "share_w_r10", "n_prior",
    "proj_vol", "vol_edge", "vol_agree",
    "exposure_same_team_dir",
    "cohort",
    "price", "price_source", "in_band", "actual", "game_finished", "result", "units",
    "computed_at",
]


def wilson(k, n, z=1.96):
    if n <= 0:
        return (float("nan"), float("nan"), float("nan"))
    k, n = float(k), float(n)
    p = k / n
    den = 1 + z * z / n
    mid = (p + z * z / (2 * n)) / den
    half = z * ((p * (1 - p) / n + z * z / (4 * n * n)) ** 0.5) / den
    return p, mid - half, mid + half


def fmt_wl(w, l, units):
    n = w + l
    p, lo, hi = wilson(w, n)
    s = f"{w}-{l}"
    if n:
        s += f" ({100*p:.1f}%, 95% Wilson CI {100*lo:.1f}%–{100*hi:.1f}%; n={n})"
    if units is not None and not (isinstance(units, float) and np.isnan(units)):
        s += f", {units:+.2f}u"
    if 0 < n < 30:
        s += " [SMALL SAMPLE]"
    return s


def parse_game(name):
    if not isinstance(name, str) or " at " not in name:
        return None, None
    away, home = name.split(" at ", 1)
    return TEAM_ABBREV.get(away.strip()), TEAM_ABBREV.get(home.strip())


def load_logs():
    files = sorted(glob.glob("data/s20*.pkl"))
    if not files:
        sys.exit("no data/s20*.pkl logs found")
    df = pd.concat([pd.read_pickle(f) for f in files], ignore_index=True)
    df = df.drop_duplicates(["playerId", "gameId"])
    df = df[df.timeOnIcePerGame.fillna(0) > 0].copy()
    df["date_ts"] = pd.to_datetime(df.gameDate)
    df = df.sort_values(["date_ts", "gameId", "playerId"]).reset_index(drop=True)
    team = (
        df.groupby(["gameId", "teamAbbrev"], as_index=False)
        .agg(
            team_sog=("shots", "sum"),
            date_ts=("date_ts", "first"),
            gameDate=("gameDate", "first"),
            opponentTeamAbbrev=("opponentTeamAbbrev", "first"),
        )
        .sort_values(["teamAbbrev", "date_ts", "gameId"])
        .reset_index(drop=True)
    )
    opp = team.rename(columns={
        "teamAbbrev": "opponentTeamAbbrev",
        "opponentTeamAbbrev": "teamAbbrev",
        "team_sog": "opp_sog",
    })[["gameId", "teamAbbrev", "opp_sog"]]
    team = team.merge(opp, on=["gameId", "teamAbbrev"], how="left")
    df = df.merge(team[["gameId", "teamAbbrev", "team_sog"]], on=["gameId", "teamAbbrev"], how="left")
    return df, team


def trailing_player(df):
    """Trailing 10-game means INCLUDING this game — used as as-of values for the next game."""
    p = df.sort_values(["playerId", "date_ts", "gameId"]).copy()
    g = p.groupby("playerId", sort=False)
    p["shots_r10_incl"] = g["shots"].transform(lambda s: s.rolling(10, min_periods=1).mean())
    p["team_sog_r10_incl"] = g["team_sog"].transform(lambda s: s.rolling(10, min_periods=1).mean())
    p["n_incl"] = g.cumcount() + 1
    return p[["playerId", "gameId", "date_ts", "teamAbbrev", "shots_r10_incl", "team_sog_r10_incl", "n_incl"]]


def trailing_team(team):
    t = team.sort_values(["teamAbbrev", "date_ts", "gameId"]).copy()
    g = t.groupby("teamAbbrev", sort=False)
    t["team_sf_r20_incl"] = g["team_sog"].transform(lambda s: s.shift(0).rolling(20, min_periods=3).mean())
    t["team_sa_r20_incl"] = g["opp_sog"].transform(lambda s: s.rolling(20, min_periods=3).mean())
    return t[["teamAbbrev", "gameId", "date_ts", "team_sf_r20_incl", "team_sa_r20_incl"]]


def asof_player(sides, player_hist):
    """Last player-game strictly before the slate date."""
    left = sides[["nhl_id", "slate_ts", "_i"]].rename(columns={"nhl_id": "playerId"})
    right = player_hist.rename(columns={"date_ts": "hist_ts"})
    m = left.merge(right, on="playerId", how="left")
    m = m[m.hist_ts < m.slate_ts]
    m = m.sort_values(["_i", "hist_ts", "gameId"]).drop_duplicates("_i", keep="last")
    return m[["_i", "teamAbbrev", "shots_r10_incl", "team_sog_r10_incl", "n_incl"]]


def asof_team(keys, team_hist, col_team, prefix):
    left = keys[["_i", "slate_ts", col_team]].rename(columns={col_team: "teamAbbrev"})
    left = left[left.teamAbbrev.notna()]
    right = team_hist.rename(columns={"date_ts": "hist_ts"})
    m = left.merge(right, on="teamAbbrev", how="left")
    m = m[m.hist_ts < m.slate_ts]
    m = m.sort_values(["_i", "hist_ts", "gameId"]).drop_duplicates("_i", keep="last")
    return m[["_i", "team_sf_r20_incl", "team_sa_r20_incl"]].rename(columns={
        "team_sf_r20_incl": f"{prefix}_sf_r20",
        "team_sa_r20_incl": f"{prefix}_sa_r20",
    })


def assign_team(row):
    away, home = row.away_abbrev, row.home_abbrev
    last = row.last_team
    if pd.notna(last) and last == away:
        return away, home
    if pd.notna(last) and last == home:
        return home, away
    return (np.nan, np.nan)


def vol_agree(proj, side, line):
    if pd.isna(proj) or pd.isna(line):
        return "n/a"
    side = str(side).upper()
    if side == "OVER":
        if proj > line:
            return "agrees"
        if proj < line:
            return "disagrees"
        return "neutral"
    if side == "UNDER":
        if proj < line:
            return "agrees"
        if proj > line:
            return "disagrees"
        return "neutral"
    return "n/a"


def build(graded, player_hist, team_hist):
    g = graded.copy()
    g["_i"] = np.arange(len(g))
    g["date"] = g.date.astype(int)
    g["gameId"] = g.gameId.astype(int)
    g["nhl_id"] = g.nhl_id.astype(int)
    g["side"] = g.side.astype(str).str.upper()
    g["line"] = g.line.astype(float)
    parsed = g.game.map(parse_game)
    g["away_abbrev"] = [a for a, h in parsed]
    g["home_abbrev"] = [h for a, h in parsed]
    g["slate_ts"] = pd.to_datetime(g.date.astype(str), format="%Y%m%d")

    ph = asof_player(g, player_hist)
    g = g.merge(ph, on="_i", how="left")
    g = g.rename(columns={"teamAbbrev": "last_team"})
    teams = g.apply(assign_team, axis=1, result_type="expand")
    g["team"] = teams[0]
    g["opponent"] = teams[1]

    own = asof_team(g, team_hist, "team", "own")
    opp = asof_team(g, team_hist, "opponent", "opp")
    g = g.merge(own, on="_i", how="left").merge(opp, on="_i", how="left")

    g["team_sf_r20"] = g["own_sf_r20"]
    g["opp_sa_r20"] = g["opp_sa_r20"]
    g["pred_team_sog"] = 0.5 * g["team_sf_r20"] + 0.5 * g["opp_sa_r20"]
    g["shots_r10"] = g["shots_r10_incl"]
    g["team_sog_r10"] = g["team_sog_r10_incl"]
    g["n_prior"] = g["n_incl"]
    g["share_w_r10"] = np.where(g.team_sog_r10 > 0, g.shots_r10 / g.team_sog_r10, np.nan)
    # Locked rule uses a 10-game player window; require it, plus both team rates.
    ok = (g.n_prior >= 10) & g.pred_team_sog.notna() & g.share_w_r10.notna()
    g["proj_vol"] = np.where(ok, g.share_w_r10 * g.pred_team_sog, np.nan)
    g["vol_edge"] = np.where(
        g.side == "OVER", g.proj_vol - g.line,
        np.where(g.side == "UNDER", g.line - g.proj_vol, np.nan),
    )
    g["vol_agree"] = [vol_agree(p, s, ln) for p, s, ln in zip(g.proj_vol, g.side, g.line)]
    # Same-game same-direction exposure on this slate (cluster size, including self).
    exp = g.groupby(["date", "gameId", "team", "side"], dropna=False)["nhl_id"].transform("size")
    g["exposure_same_team_dir"] = exp.astype("Int64")
    g.loc[g.team.isna(), "exposure_same_team_dir"] = pd.NA
    g["cohort"] = np.where(g.date >= FORWARD_START, "forward", "pre-registration")
    return g


def upsert(new, old_path):
    if not os.path.exists(old_path):
        return new
    old = pd.read_csv(old_path)
    if "cohort" not in old.columns:
        return new
    for c in KEY:
        if c not in old.columns:
            return new
    old["_key"] = list(zip(old.date.astype(int), old.gameId.astype(int),
                           old.nhl_id.astype(int), old.side.astype(str).str.upper(),
                           old.line.astype(float)))
    new = new.copy()
    new["_key"] = list(zip(new.date.astype(int), new.gameId.astype(int),
                           new.nhl_id.astype(int), new.side.astype(str).str.upper(),
                           new.line.astype(float)))
    keep = old.drop_duplicates("_key").set_index("_key")["cohort"]
    new["cohort"] = new["_key"].map(keep).fillna(new["cohort"])
    return new.drop(columns="_key")


def summarize(df):
    decided = df[df.result.isin(["W", "L"])].copy()
    fwd = df[df.cohort == "forward"]
    fwd_dec = decided[decided.cohort == "forward"]
    print("NHL SOG volume shadow (paper only; locked 50/50 blend)")
    print(f"wrote {OUT}  rows={len(df)}")
    n_fwd, n_bar = int(len(fwd_dec)), 100
    print(f"forward decided since {FORWARD_START}: {n_fwd} of {n_bar} "
          f"({max(0, n_bar - n_fwd)} to the pre-registered bar)"
          + (f"; {int(len(fwd) - len(fwd_dec))} pending" if len(fwd) > len(fwd_dec) else ""))
    print(f"pre-registration sides: {int((df.cohort == 'pre-registration').sum())} "
          f"(backfilled tags only; do not count toward the bar)")

    def block(part, title):
        print(f"\n{title}")
        if part.empty:
            print("  no decided sides")
            return
        for label in ("agrees", "disagrees", "neutral", "n/a"):
            sub = part[part.vol_agree == label]
            if sub.empty:
                continue
            w = int((sub.result == "W").sum())
            l = int((sub.result == "L").sum())
            units = float(sub.units.sum()) if sub.units.notna().any() else float("nan")
            print(f"  {label:10s} {fmt_wl(w, l, units)}")
        w = int((part.result == "W").sum())
        l = int((part.result == "L").sum())
        units = float(part.units.sum()) if part.units.notna().any() else float("nan")
        print(f"  {'all':10s} {fmt_wl(w, l, units)}")

    block(decided, "Cumulative decided (recorded prices, including pre-registration)")
    block(fwd_dec, "Forward decided only (counts toward the 100-side bar)")

    print("\nExposure buckets (same game, same team, same direction, including self)")
    for scope, part in (("all sides", df), ("decided", decided)):
        if part.empty or part.exposure_same_team_dir.isna().all():
            print(f"  {scope}: n/a")
            continue
        b = part.copy()
        b["bucket"] = np.where(b.exposure_same_team_dir >= 5, "5+",
                               b.exposure_same_team_dir.astype("Int64").astype(str))
        print(f"  {scope}:")
        for bk, sub in b.groupby("bucket", dropna=False):
            if scope == "decided":
                w = int((sub.result == "W").sum())
                l = int((sub.result == "L").sum())
                units = float(sub.units.sum())
                print(f"    {bk}: n={len(sub)}  {fmt_wl(w, l, units)}")
            else:
                print(f"    {bk}: n={len(sub)}")


def main():
    if not os.path.exists(GRADED):
        sys.exit(f"missing {GRADED}")
    graded = pd.read_csv(GRADED)
    print("loading skater logs...")
    logs, team = load_logs()
    print(f"  {len(logs):,} player-games, {team.gameId.nunique()} games")
    print("trailing as-of features...")
    player_hist = trailing_player(logs)
    team_hist = trailing_team(team)
    print("tagging sides...")
    out = build(graded, player_hist, team_hist)
    out = upsert(out, OUT)
    out["computed_at"] = datetime.now(PT).strftime("%Y-%m-%d %H:%M:%S PT")
    # Keep result/units from the current grader file (recorded prices only).
    out = out[COLS]
    out = out.sort_values(["date", "gameId", "player", "side", "line"]).reset_index(drop=True)
    tmp = OUT + ".tmp"
    out.to_csv(tmp, index=False)
    os.replace(tmp, OUT)
    summarize(out)


if __name__ == "__main__":
    main()

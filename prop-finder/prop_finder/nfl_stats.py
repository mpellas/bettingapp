"""NFL data via nflverse release files (no key)."""
from __future__ import annotations

import pandas as pd

from .net import ROOT, get_file
from .stats_common import add_derived, pos_group

BASE = "https://github.com/nflverse/nflverse-data/releases/download"
RAW = ROOT / "data" / "raw" / "nfl"
ESPN_TO_NFLVERSE = {"WSH": "WAS", "LAR": "LA"}


def _csv(path: str, name: str, ttl=6 * 3600) -> pd.DataFrame:
    p = get_file(f"{BASE}/{path}", RAW / name, ttl=ttl)
    return pd.read_csv(p, low_memory=False)


def load_games() -> pd.DataFrame:
    return _csv("schedules/games.csv", "games.csv")


def load_players() -> pd.DataFrame:
    return _csv("players/players.csv", "players.csv", ttl=24 * 3600)


def load_injuries(season: int) -> pd.DataFrame:
    try:
        return _csv(f"injuries/injuries_{season}.csv", f"injuries_{season}.csv")
    except Exception:  # noqa: BLE001
        return pd.DataFrame()


def load_player_weeks(season: int) -> pd.DataFrame:
    ttl = 6 * 3600 if season >= 2026 else None
    return _csv(f"stats_player/stats_player_week_{season}.csv", f"stats_player_week_{season}.csv", ttl=ttl)


def game_logs(seasons: list[int]) -> pd.DataFrame:
    games = load_games()
    players = load_players()[["gsis_id", "espn_id"]].dropna()
    players["espn_id"] = players["espn_id"].astype("int64").astype(str)
    frames = []
    for s in seasons:
        df = load_player_weeks(s)
        df = df[df["season_type"] == "REG"]
        frames.append(df)
    df = pd.concat(frames, ignore_index=True)
    g = games[["game_id", "gameday", "home_team", "location"]]
    df = df.merge(g, on="game_id", how="left").copy()
    df["home_away"] = "A"
    df.loc[df["team"] == df["home_team"], "home_away"] = "H"
    df.loc[df["location"].eq("Neutral"), "home_away"] = "N"
    out = pd.DataFrame({
        "league": "nfl", "season": df["season"], "week": df["week"], "game_id": df["game_id"],
        "game_date": df["gameday"], "player_id": df["player_id"],
        "player": df["player_display_name"], "position": df["position"],
        "team": df["team"], "opp": df["opponent_team"], "home_away": df["home_away"],
        "completions": df["completions"], "attempts": df["attempts"],
        "pass_yds": df["passing_yards"], "pass_tds": df["passing_tds"],
        "interceptions": df["passing_interceptions"], "carries": df["carries"],
        "rush_yds": df["rushing_yards"], "rush_tds": df["rushing_tds"],
        "receptions": df["receptions"], "targets": df["targets"],
        "rec_yds": df["receiving_yards"], "rec_tds": df["receiving_tds"],
    })
    out = out.merge(players.rename(columns={"gsis_id": "player_id"}), on="player_id", how="left")
    out["pos_group"] = out["position"].map(pos_group)
    out = out[out["pos_group"] != "OTH"]
    return add_derived(out)


def team_points(seasons: list[int]) -> pd.DataFrame:
    """Per team-game points scored (for implied-total vs average comparisons)."""
    g = load_games()
    g = g[g["season"].isin(seasons) & g["game_type"].eq("REG") & g["home_score"].notna()]
    h = pd.DataFrame({"season": g.season, "team": g.home_team, "pts": g.home_score, "opp_pts": g.away_score})
    a = pd.DataFrame({"season": g.season, "team": g.away_team, "pts": g.away_score, "opp_pts": g.home_score})
    return pd.concat([h, a], ignore_index=True)


def injury_report(season: int, week: int) -> pd.DataFrame:
    inj = load_injuries(season)
    if inj.empty:
        return inj
    inj = inj[inj["week"] == week]
    return inj[["gsis_id", "team", "full_name", "report_status", "report_primary_injury", "practice_status"]]

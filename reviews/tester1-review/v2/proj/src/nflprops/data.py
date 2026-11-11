"""Download + cache nflverse data (weekly player stats, schedules, snap counts, player id map).

Primary source: the `nflreadpy` package. Fallback: direct download of the nflverse-data GitHub release files.
Everything is cached as parquet under data/cache/ so reruns are offline and fast.
"""
from __future__ import annotations

import argparse
import io
import logging

import pandas as pd
import requests

from . import CACHE

log = logging.getLogger(__name__)
GH = "https://github.com/nflverse/nflverse-data/releases/download"

PS_COLS = ["player_id", "player_display_name", "position", "position_group", "season", "week", "season_type",
           "game_id", "team", "opponent_team", "completions", "attempts", "passing_yards", "passing_air_yards",
           "sacks_suffered", "passing_epa", "carries", "rushing_yards", "rushing_epa", "receptions", "targets",
           "receiving_yards", "receiving_air_yards", "receiving_epa", "target_share", "air_yards_share", "wopr"]


def _to_pd(x) -> pd.DataFrame:
    return x.to_pandas() if hasattr(x, "to_pandas") else pd.DataFrame(x)


def _gh_parquet(url: str) -> pd.DataFrame:
    r = requests.get(url, timeout=120)
    r.raise_for_status()
    return pd.read_parquet(io.BytesIO(r.content))


def _player_stats(seasons) -> pd.DataFrame:
    try:
        import nflreadpy as nfl
        df = _to_pd(nfl.load_player_stats(list(seasons), summary_level="week"))
    except Exception as e:  # pragma: no cover - network fallback
        log.warning("nflreadpy player stats failed (%s); falling back to GitHub releases", e)
        df = pd.concat([_gh_parquet(f"{GH}/stats_player/stats_player_week_{s}.parquet") for s in seasons])
    return df[[c for c in PS_COLS if c in df.columns]]


def _schedules() -> pd.DataFrame:
    try:
        import nflreadpy as nfl
        return _to_pd(nfl.load_schedules())
    except Exception as e:  # pragma: no cover
        log.warning("nflreadpy schedules failed (%s); falling back to nfldata games.csv", e)
        return pd.read_csv("https://raw.githubusercontent.com/nflverse/nfldata/master/data/games.csv")


def _snaps(seasons) -> pd.DataFrame:
    try:
        import nflreadpy as nfl
        return _to_pd(nfl.load_snap_counts(list(seasons)))
    except Exception as e:  # pragma: no cover
        log.warning("nflreadpy snap counts failed (%s); falling back to GitHub releases", e)
        return pd.concat([_gh_parquet(f"{GH}/snap_counts/snap_counts_{s}.parquet") for s in seasons])


def _players() -> pd.DataFrame:
    try:
        import nflreadpy as nfl
        df = _to_pd(nfl.load_players())
    except Exception as e:  # pragma: no cover
        log.warning("nflreadpy players failed (%s); falling back to GitHub releases", e)
        df = _gh_parquet(f"{GH}/players/players.parquet")
    return df[["gsis_id", "display_name", "position", "pfr_id", "espn_id"]]


def fetch_all(first: int, last: int, refresh: bool = False) -> dict[str, pd.DataFrame]:
    CACHE.mkdir(parents=True, exist_ok=True)
    seasons = range(first, last + 1)
    jobs = {
        f"player_stats_{first}_{last}": lambda: _player_stats(seasons),
        "schedules": _schedules,
        f"snap_counts_{first}_{last}": lambda: _snaps(seasons),
        "players": _players,
    }
    out = {}
    for name, fn in jobs.items():
        p = CACHE / f"{name}.parquet"
        if p.exists() and not refresh:
            df = pd.read_parquet(p)
        else:
            log.info("downloading %s", name)
            df = fn()
            df.to_parquet(p, index=False)
        out[name.split("_2")[0] if name[-4:].isdigit() else name] = df
    return out


def load(first: int, last: int, refresh: bool = False) -> dict[str, pd.DataFrame]:
    """Returns dict with keys player_stats, schedules, snap_counts, players."""
    return fetch_all(first, last, refresh)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    ap = argparse.ArgumentParser()
    ap.add_argument("--first", type=int, default=2015)
    ap.add_argument("--last", type=int, default=2025)
    ap.add_argument("--refresh", action="store_true")
    a = ap.parse_args()
    d = load(a.first, a.last, a.refresh)
    for k, v in d.items():
        print(k, v.shape)

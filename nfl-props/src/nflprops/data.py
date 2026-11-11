"""Download + cache nflverse data (weekly player stats, schedules, snap counts, player id map).

Primary source: the `nflreadpy` package. Fallback: direct download of the nflverse-data GitHub release files.
Everything is cached as parquet under data/cache/ so reruns are offline and fast.
"""
from __future__ import annotations

import argparse
import datetime as dt
import io
import logging
import time
from pathlib import Path

import pandas as pd
import requests

from . import CACHE

log = logging.getLogger(__name__)
RAW = CACHE / "raw"
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


def current_season(today: dt.date | None = None) -> int:
    t = today or dt.date.today()
    return t.year if t.month >= 9 else t.year - 1


def _stale(p: Path, max_age_h: float) -> bool:
    return (not p.exists()) or (time.time() - p.stat().st_mtime > max_age_h * 3600)


def _migrate_combined(kind: str):
    """v2 cached multi-season files (player_stats_2015_2025.parquet): split once into per-season files."""
    for p in CACHE.glob(f"{kind}_*_*.parquet"):
        df = pd.read_parquet(p)
        for s, g in df.groupby("season"):
            q = RAW / f"{kind}_{int(s)}.parquet"
            if not q.exists():
                g.to_parquet(q, index=False)


def fetch_all(first: int, last: int, refresh: bool = False, max_age_h: float = 12.0) -> dict[str, pd.DataFrame]:
    """Per-season raw caches under data/cache/raw/ (Tester1 N3).
    * completed seasons: downloaded once, reused;
    * the current season (and the schedules / players tables, which change in-season): re-downloaded when the cached
      file is older than `max_age_h` hours (or with refresh=True). Every download is logged with its sha256 in
      data/cache/raw/download_log.tsv."""
    RAW.mkdir(parents=True, exist_ok=True)
    cur = current_season()
    out = {}
    for kind, fn in (("player_stats", _player_stats), ("snap_counts", _snaps)):
        _migrate_combined(kind)
        parts = []
        for s in range(first, last + 1):
            p = RAW / f"{kind}_{s}.parquet"
            if refresh or not p.exists() or (s >= cur and _stale(p, max_age_h)):
                try:
                    df = fn([s])
                    df.to_parquet(p, index=False)
                    _log_download(p)
                except Exception as e:  # noqa: BLE001
                    if not p.exists():
                        log.warning("no %s for %s (%s)", kind, s, e)
                        continue
                    log.warning("refresh of %s failed (%s); using cached file", p.name, e)
            parts.append(pd.read_parquet(p))
        out[kind] = pd.concat(parts, ignore_index=True)
    for kind, fn in (("schedules", _schedules), ("players", _players)):
        p = RAW / f"{kind}.parquet"
        old = CACHE / f"{kind}.parquet"
        if not p.exists() and old.exists() and not refresh:
            p.write_bytes(old.read_bytes())
        if refresh or _stale(p, max_age_h):
            try:
                fn().to_parquet(p, index=False)
                _log_download(p)
            except Exception as e:  # noqa: BLE001
                if not p.exists():
                    raise
                log.warning("refresh of %s failed (%s); using cached file", p.name, e)
        out[kind] = pd.read_parquet(p)
    return out


def _log_download(p: Path):
    import hashlib
    with open(RAW / "download_log.tsv", "a") as f:
        f.write(f"{dt.datetime.now().astimezone().isoformat(timespec='seconds')}\t{p.name}\t"
                f"{hashlib.sha256(p.read_bytes()).hexdigest()}\n")


def data_version(d: dict, first: int, last: int) -> str:
    """Content hash of the raw inputs RESTRICTED to seasons first..last (so a 2026 refresh does not invalidate
    2015-2025 caches, but any change to the data actually used does). Used in feature + prediction cache keys."""
    import hashlib
    h = hashlib.sha1()
    sch = d["schedules"]
    parts = [d["player_stats"][d["player_stats"]["season"].between(first, last)],
             d["snap_counts"][d["snap_counts"]["season"].between(first, last)],
             sch[sch["season"].between(first, last)]]
    pfr = set(parts[1]["pfr_player_id"].dropna())
    pl = d["players"]
    parts.append(pl[pl["pfr_id"].isin(pfr)][["pfr_id", "gsis_id", "espn_id"]])
    for df in parts:
        df = df.reindex(sorted(df.columns), axis=1).astype(str)
        df = df.sort_values(list(df.columns)).reset_index(drop=True)
        h.update(pd.util.hash_pandas_object(df, index=False).values.tobytes())
    return h.hexdigest()[:8]


def load(first: int, last: int, refresh: bool = False, max_age_h: float = 12.0) -> dict[str, pd.DataFrame]:
    """Returns dict with keys player_stats, schedules, snap_counts, players."""
    return fetch_all(first, last, refresh, max_age_h)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    ap = argparse.ArgumentParser()
    ap.add_argument("--first", type=int, default=2015)
    ap.add_argument("--last", type=int, default=2025)
    ap.add_argument("--refresh", action="store_true")
    ap.add_argument("--max-age-hours", type=float, default=12.0)
    a = ap.parse_args()
    d = load(a.first, a.last, a.refresh, a.max_age_hours)
    for k, v in d.items():
        print(k, v.shape)
    print("data_version", data_version(d, a.first, a.last))

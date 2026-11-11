"""Leakage-safe, bet-time ("as-of") feature engineering.  FEATURE_VERSION = "v2-asof".

Every player / team / defense feature for a game G is computed from games strictly BEFORE G:
values are `shift(1)`-ed inside each entity's chronological game sequence before any rolling/EWMA op.

v2 (after the Tester1 review, finding B1): nothing recorded on or after game day is used, because we bet against
prop lines posted days before kickoff.
  * nflverse `spread_line`/`total_line` (filled in near/at kickoff; closing-type values) are NOT used. They are
    replaced by a pre-game PROXY built only from prior games' scores (team points for/against EWMAs).
  * observed `wind`/`temp` are NOT used; only the static stadium type (dome / retractable / outdoors).
  * the actual starting QB (`home_qb_id/away_qb_id` of the game itself) is NOT used; the "projected starter" is
    the team's starter in its PREVIOUS game.
`leakage.py` scrambles every post-cutoff outcome AND every game-level field (spread, total, weather, starter,
scores, roof open/closed) and asserts features up to the cutoff are unchanged.
"""
from __future__ import annotations

import logging

import numpy as np
import pandas as pd

from . import CACHE

log = logging.getLogger(__name__)
OFF_POS = ["QB", "RB", "FB", "WR", "TE"]
STATS = ["completions", "attempts", "passing_yards", "passing_air_yards", "sacks_suffered", "carries",
         "rushing_yards", "receptions", "targets", "receiving_yards", "receiving_air_yards"]
SHARES = ["target_share", "air_yards_share", "carry_share", "offense_pct"]
HALFLIVES = (2, 6)
FEATURE_VERSION = "v2-asof"
TARGETS = {"pass_yds": "passing_yards", "rush_yds": "rushing_yards", "rec_yds": "receiving_yards"}


# ----------------------------------------------------------------------------------------------- raw assembly
def _schedule(sched: pd.DataFrame) -> pd.DataFrame:
    s = sched[["game_id", "season", "week", "game_type", "gameday", "home_team", "away_team", "spread_line",
               "total_line", "home_rest", "away_rest", "roof", "wind", "temp", "div_game", "home_qb_id",
               "away_qb_id", "home_score", "away_score"]].copy()
    s["gameday"] = pd.to_datetime(s["gameday"])
    return s


def assemble_player_games(d: dict) -> pd.DataFrame:
    """One row per (player, game) for offensive players who recorded a stat OR logged an offensive snap.
    Players with snaps but no stat line get 0s (important: otherwise "0-yard games" vanish and overs look better)."""
    sched = _schedule(d["schedules"])
    ps = d["player_stats"]
    ps = ps[ps["position"].isin(OFF_POS)].copy()
    ps = ps.rename(columns={"opponent_team": "opponent"})

    pl = d["players"].dropna(subset=["pfr_id"]).drop_duplicates("pfr_id")
    sn = d["snap_counts"].merge(pl[["pfr_id", "gsis_id"]], left_on="pfr_player_id", right_on="pfr_id", how="inner")
    sn = sn[sn["position"].isin(OFF_POS) & (sn["offense_snaps"] > 0)]
    sn = sn[["game_id", "gsis_id", "team", "position", "player", "offense_pct"]].rename(
        columns={"gsis_id": "player_id", "player": "player_display_name"}).drop_duplicates(["game_id", "player_id"])

    df = ps.merge(sn[["game_id", "player_id", "offense_pct"]], on=["game_id", "player_id"], how="left")
    extra = sn.merge(ps[["game_id", "player_id"]], on=["game_id", "player_id"], how="left", indicator=True)
    extra = extra[extra["_merge"] == "left_only"].drop(columns="_merge")
    if len(extra):
        extra = extra.merge(sched[["game_id", "season", "week", "game_type", "home_team", "away_team"]], on="game_id")
        extra["opponent"] = np.where(extra["team"] == extra["home_team"], extra["away_team"], extra["home_team"])
        extra["season_type"] = np.where(extra["game_type"] == "REG", "REG", "POST")
        extra = extra.drop(columns=["home_team", "away_team", "game_type"])
        for c in STATS:
            extra[c] = 0.0
        df = pd.concat([df, extra], ignore_index=True)
    for c in STATS:
        df[c] = df[c].fillna(0.0).astype(float)
    df = df.merge(sched.drop(columns=["season", "week"]), on="game_id", how="inner")
    df["is_home"] = (df["team"] == df["home_team"]).astype(int)
    df = df.sort_values(["player_id", "gameday", "game_id"]).reset_index(drop=True)
    return df


# ----------------------------------------------------------------------------------------------- helpers
def _lagged_ewm(df: pd.DataFrame, key: str, cols: list[str], hl: float, prefix: str) -> pd.DataFrame:
    """EWMA over each entity's PRIOR games (shift(1) first => the current game never enters its own feature)."""
    g = df.groupby(key, sort=False)
    shifted = g[cols].shift(1)
    shifted[key] = df[key].values
    out = shifted.groupby(key, sort=False)[cols].transform(lambda s: s.ewm(halflife=hl, ignore_na=True).mean())
    out.columns = [f"{prefix}{c}_ewm{hl}" for c in cols]
    return out


def _team_tables(pg: pd.DataFrame):
    t = pg.groupby(["game_id", "team"], as_index=False).agg(
        gameday=("gameday", "first"), team_pass_att=("attempts", "sum"), team_carries=("carries", "sum"),
        team_targets=("targets", "sum"), team_pass_yds=("passing_yards", "sum"),
        team_rush_yds=("rushing_yards", "sum"))
    t["team_pass_rate"] = t["team_pass_att"] / (t["team_pass_att"] + t["team_carries"]).clip(lower=1)
    t["team_plays"] = t["team_pass_att"] + t["team_carries"]
    t = t.sort_values(["team", "gameday", "game_id"]).reset_index(drop=True)
    tcols = ["team_pass_att", "team_carries", "team_pass_yds", "team_rush_yds", "team_pass_rate", "team_plays"]
    tf = pd.concat([t[["game_id", "team"]], _lagged_ewm(t, "team", tcols, 4, "")], axis=1)

    def pos_sum(stat, pos):
        m = pg["position"].isin(pos)
        return pg[stat].where(m, 0.0)
    a = pg.assign(qb_pass_yds=pos_sum("passing_yards", ["QB"]), rb_rush_yds=pos_sum("rushing_yards", ["RB", "FB"]),
                  wr_rec_yds=pos_sum("receiving_yards", ["WR"]), te_rec_yds=pos_sum("receiving_yards", ["TE"]),
                  rb_rec_yds=pos_sum("receiving_yards", ["RB", "FB"]))
    dcols = ["qb_pass_yds", "rb_rush_yds", "wr_rec_yds", "te_rec_yds", "rb_rec_yds", "attempts", "carries"]
    dd = a.groupby(["game_id", "opponent"], as_index=False).agg(gameday=("gameday", "first"),
                                                                **{c: (c, "sum") for c in dcols})
    dd = dd.sort_values(["opponent", "gameday", "game_id"]).reset_index(drop=True)
    df_ = pd.concat([dd[["game_id", "opponent"]], _lagged_ewm(dd, "opponent", dcols, 6, "opp_allowed_")], axis=1)
    return t[["game_id", "team", "team_carries", "team_targets"]], tf, df_


def _game_proxies(sched: pd.DataFrame) -> pd.DataFrame:
    """Per (game_id, team): pre-game proxies for implied team total / spread / total, and the projected starting QB,
    all from the team's (and opponent's) PRIOR games only."""
    s = _schedule(sched)
    home = s.assign(team=s["home_team"], opp=s["away_team"], pf=s["home_score"], pa=s["away_score"],
                    starter=s["home_qb_id"], is_home=1)
    away = s.assign(team=s["away_team"], opp=s["home_team"], pf=s["away_score"], pa=s["home_score"],
                    starter=s["away_qb_id"], is_home=0)
    t = pd.concat([home, away])[["game_id", "gameday", "team", "opp", "pf", "pa", "starter", "is_home"]]
    t = t.sort_values(["team", "gameday", "game_id"]).reset_index(drop=True)
    g = t.groupby("team", sort=False)
    for c in ("pf", "pa"):
        t[f"team_{c}_ewm"] = g[c].transform(lambda x: x.shift(1).ewm(halflife=6, ignore_na=True).mean())
    t["proj_starter_id"] = g["starter"].shift(1)          # last game's starter (known before this game)
    o = t[["game_id", "team", "team_pf_ewm", "team_pa_ewm"]].rename(
        columns={"team": "opp", "team_pf_ewm": "opp_pf_ewm", "team_pa_ewm": "opp_pa_ewm"})
    t = t.merge(o, on=["game_id", "opp"], how="left")
    hfa = 0.75
    t["proxy_tt"] = 0.5 * (t["team_pf_ewm"] + t["opp_pa_ewm"]) + np.where(t["is_home"] == 1, hfa, -hfa)
    t["proxy_opp_tt"] = 0.5 * (t["opp_pf_ewm"] + t["team_pa_ewm"]) + np.where(t["is_home"] == 1, -hfa, hfa)
    t["proxy_spread"] = t["proxy_tt"] - t["proxy_opp_tt"]          # + => team projected to win
    t["proxy_total"] = t["proxy_tt"] + t["proxy_opp_tt"]
    return t[["game_id", "team", "team_pf_ewm", "team_pa_ewm", "opp_pf_ewm", "opp_pa_ewm", "proxy_tt",
              "proxy_spread", "proxy_total", "proj_starter_id"]]


# ----------------------------------------------------------------------------------------------- main builder
def build_features(d: dict, extra_rows: pd.DataFrame | None = None) -> pd.DataFrame:
    """extra_rows: PRE-GAME rows for scheduled, unplayed games (pregame.py). Their stats are NaN; they enter every
    table only through shift(1)-ed history, so their features use prior games only (Tester1 N2)."""
    pg = assemble_player_games(d)
    if extra_rows is not None and len(extra_rows):
        sched = _schedule(d["schedules"])
        x = extra_rows.merge(sched.drop(columns=["season", "week"]), on="game_id", how="inner")
        x["is_home"] = (x["team"] == x["home_team"]).astype(int)
        x["is_pregame_row"] = 1
        pg = pd.concat([pg.assign(is_pregame_row=0), x], ignore_index=True)
        pg = pg.sort_values(["player_id", "gameday", "game_id"]).reset_index(drop=True)
    team_raw, team_f, def_f = _team_tables(pg)
    pg = pg.merge(team_raw, on=["game_id", "team"], how="left")
    pg["carry_share"] = pg["carries"] / pg["team_carries"].clip(lower=1)
    pg["target_share"] = np.where(pg["team_targets"] > 0, pg["targets"] / pg["team_targets"].clip(lower=1), np.nan)
    pg["air_yards_share"] = pg["air_yards_share"].fillna(0.0)
    pg = pg.drop(columns=["team_carries", "team_targets"])
    pg = pg.sort_values(["player_id", "gameday", "game_id"]).reset_index(drop=True)

    feats = [pg]
    for hl in HALFLIVES:
        feats.append(_lagged_ewm(pg, "player_id", STATS + SHARES, hl, "p_"))
    g = pg.groupby("player_id", sort=False)
    lag = g[["passing_yards", "rushing_yards", "receiving_yards", "attempts", "carries", "targets"]].shift(1)
    lag.columns = [f"p_{c}_lag1" for c in lag.columns]
    feats.append(lag)
    f = pd.concat(feats, axis=1)

    f["p_n_prior"] = g.cumcount()
    f["p_n_prior_season"] = f.groupby(["player_id", "season"]).cumcount()
    f["p_days_since_last"] = g["gameday"].diff().dt.days.clip(upper=60)
    f["p_team_changed"] = (g["team"].shift(1) != f["team"]).astype(int).where(f["p_n_prior"] > 0, 0)

    def ratio(num, den, hl=6, min_den=1.0):
        n, dd = f[f"p_{num}_ewm{hl}"], f[f"p_{den}_ewm{hl}"]
        return (n / dd).where(dd >= min_den)
    f["p_ypa"] = ratio("passing_yards", "attempts", min_den=5)
    f["p_ypc"] = ratio("rushing_yards", "carries", min_den=1)
    f["p_ypt"] = ratio("receiving_yards", "targets", min_den=1)
    f["p_catch_rate"] = ratio("receptions", "targets", min_den=1)
    f["p_adot"] = ratio("receiving_air_yards", "targets", min_den=1)
    f["p_pass_adot"] = ratio("passing_air_yards", "attempts", min_den=5)

    f = f.merge(team_f, on=["game_id", "team"], how="left").merge(def_f, on=["game_id", "opponent"], how="left")
    f = f.merge(_game_proxies(d["schedules"]), on=["game_id", "team"], how="left")

    # bet-time context: schedule facts known when the week's props are posted (no closing lines, no game-day
    # weather, no actual starter). Raw nflverse game-day columns are dropped so nothing downstream can use them.
    f["implied_tt"] = f["proxy_tt"]          # name kept for the public projection; it is the PRIOR-DATA proxy now
    f["rest_days"] = np.where(f["is_home"] == 1, f["home_rest"], f["away_rest"])
    f["dome"] = (f["roof"] == "dome").astype(int)                       # static stadium type
    f["retractable"] = f["roof"].isin(["open", "closed"]).astype(int)   # static; open/closed status NOT used
    f["is_post"] = (f["game_type"] != "REG").astype(int)
    f["is_proj_starter"] = (f["player_id"] == f["proj_starter_id"]).astype(int)
    f = f.drop(columns=["spread_line", "total_line", "wind", "temp", "home_qb_id", "away_qb_id", "home_score",
                        "away_score"])
    f["pos_code"] = f["position"].map({"QB": 0, "RB": 1, "FB": 1, "WR": 2, "TE": 3}).astype(int)

    # "public projection": simple usage-EWMA scaled by the PRIOR-DATA implied-team-total proxy. Used (a) as a
    # baseline and (b) in the simulated line. Fixed constants => no fitted parameters, no leakage.
    for mk, stat in TARGETS.items():
        base = 0.5 * f[f"p_{stat}_ewm2"] + 0.5 * f[f"p_{stat}_ewm6"]
        expo = 0.3 if mk == "rush_yds" else 0.5
        env = (f["implied_tt"].fillna(22.0) / 22.0).clip(0.6, 1.5) ** expo
        f[f"mkt_proj_{mk}"] = (base * env).where(f["p_n_prior"] > 0)
        f[f"naive_{mk}"] = f[f"p_{stat}_ewm2"].where(f["p_n_prior"] > 0)
    return f


FEATURE_GROUPS = {
    "player_short": [f"p_{c}_ewm2" for c in STATS + SHARES],
    "player_long": [f"p_{c}_ewm6" for c in STATS + SHARES],
    "player_misc": ["p_passing_yards_lag1", "p_rushing_yards_lag1", "p_receiving_yards_lag1", "p_attempts_lag1",
                    "p_carries_lag1", "p_targets_lag1", "p_n_prior", "p_n_prior_season", "p_days_since_last",
                    "p_team_changed", "pos_code", "is_proj_starter"],
    "rates": ["p_ypa", "p_ypc", "p_ypt", "p_catch_rate", "p_adot", "p_pass_adot"],
    "team": ["team_pass_att_ewm4", "team_carries_ewm4", "team_pass_yds_ewm4", "team_rush_yds_ewm4",
             "team_pass_rate_ewm4", "team_plays_ewm4"],
    "opponent": [f"opp_allowed_{c}_ewm6" for c in ["qb_pass_yds", "rb_rush_yds", "wr_rec_yds", "te_rec_yds",
                                                    "rb_rec_yds", "attempts", "carries"]],
    "game_proxy": ["proxy_tt", "proxy_spread", "proxy_total", "team_pf_ewm", "team_pa_ewm", "opp_pf_ewm",
                   "opp_pa_ewm"],
    "context": ["is_home", "rest_days", "dome", "retractable", "div_game", "week", "is_post"],
}
SNAP_COLS = ["p_offense_pct_ewm2", "p_offense_pct_ewm6"]

FEATURE_SETS = {
    "player_only": ["player_short", "player_long", "player_misc", "rates"],
    "player_proxy": ["player_short", "player_long", "player_misc", "rates", "game_proxy"],
    "no_opponent": ["player_short", "player_long", "player_misc", "rates", "team", "game_proxy", "context"],
    "full": list(FEATURE_GROUPS),
}


def feature_columns(feature_set: str, use_snaps: bool = True, extra_market_proj: bool = True) -> list[str]:
    cols = [c for grp in FEATURE_SETS[feature_set] for c in FEATURE_GROUPS[grp]]
    if not use_snaps:
        cols = [c for c in cols if c not in SNAP_COLS]
    if extra_market_proj:
        cols = cols + ["mkt_proj_pass_yds", "mkt_proj_rush_yds", "mkt_proj_rec_yds"]
    return cols


def code_version(files: list[str]) -> str:
    """Short hash of the given source files in this package + FEATURE_VERSION: caches are keyed on code, not only
    on config (Tester1 B7)."""
    import hashlib
    from pathlib import Path
    h = hashlib.sha1(FEATURE_VERSION.encode())
    for fn in files:
        h.update((Path(__file__).parent / fn).read_bytes())
    return h.hexdigest()[:8]


_DV: dict = {}


def load_features(first: int, last: int, refresh: bool = False, max_age_h: float = 12.0) -> pd.DataFrame:
    """Feature cache key = seasons + code version + DATA version (content hash of the raw inputs for those seasons;
    Tester1 N3). The data loader refreshes in-season files older than `max_age_h` hours."""
    from . import data
    d = data.load(first, last, max_age_h=max_age_h)
    dv = data.data_version(d, first, last)
    p = CACHE / f"features_{first}_{last}_{code_version(['data.py', 'features.py'])}_{dv}.parquet"
    if p.exists() and not refresh:
        f = pd.read_parquet(p)
    else:
        f = build_features(d)
        f.to_parquet(p, index=False)
    f.attrs["data_version"] = dv
    _DV[(first, last)] = dv
    return f


def data_version_for(first: int, last: int) -> str:
    if (first, last) not in _DV:
        load_features(first, last)
    return _DV[(first, last)]

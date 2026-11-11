"""LEGACY v1 FEATURES - DO NOT USE. Kept only so tests can prove the extended leakage test catches their look-ahead
(closing spread/total, observed weather, actual starting QB).

Leakage-safe feature engineering.

Every player / team / defense feature for a game G is computed from games strictly BEFORE G:
values are `shift(1)`-ed inside each entity's chronological game sequence before any rolling/EWMA op.
Schedule features (spread, total, rest, roof, home/away) are known pre-kickoff (nflverse spread/total are closing
lines, i.e. available at kickoff). The starting-QB flag uses nflverse's `home_qb_id/away_qb_id` (the actual starter;
in practice announced pre-game — documented as a mild assumption).
`leakage.py` verifies this empirically by scrambling all post-cutoff outcomes and asserting features are unchanged.
"""
from __future__ import annotations

import logging

import numpy as np
import pandas as pd

from .. import CACHE

log = logging.getLogger(__name__)
OFF_POS = ["QB", "RB", "FB", "WR", "TE"]
STATS = ["completions", "attempts", "passing_yards", "passing_air_yards", "sacks_suffered", "carries",
         "rushing_yards", "receptions", "targets", "receiving_yards", "receiving_air_yards"]
SHARES = ["target_share", "air_yards_share", "carry_share", "offense_pct"]
HALFLIVES = (2, 6)
TARGETS = {"pass_yds": "passing_yards", "rush_yds": "rushing_yards", "rec_yds": "receiving_yards"}


# ----------------------------------------------------------------------------------------------- raw assembly
def _schedule(sched: pd.DataFrame) -> pd.DataFrame:
    s = sched[["game_id", "season", "week", "game_type", "gameday", "home_team", "away_team", "spread_line",
               "total_line", "home_rest", "away_rest", "roof", "wind", "temp", "div_game", "home_qb_id",
               "away_qb_id"]].copy()
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


# ----------------------------------------------------------------------------------------------- main builder
def build_features(d: dict) -> pd.DataFrame:
    pg = assemble_player_games(d)
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

    # schedule / market-context features (pre-kickoff information)
    f["team_spread"] = np.where(f["is_home"] == 1, f["spread_line"], -f["spread_line"])  # + => team favored
    f["implied_tt"] = f["total_line"] / 2 + f["team_spread"] / 2
    f["rest_days"] = np.where(f["is_home"] == 1, f["home_rest"], f["away_rest"])
    f["dome"] = f["roof"].isin(["dome", "closed"]).astype(int)
    f["is_post"] = (f["game_type"] != "REG").astype(int)
    f["is_starting_qb"] = ((f["player_id"] == f["home_qb_id"]) & (f["is_home"] == 1)
                           | (f["player_id"] == f["away_qb_id"]) & (f["is_home"] == 0)).astype(int)
    f["pos_code"] = f["position"].map({"QB": 0, "RB": 1, "FB": 1, "WR": 2, "TE": 3}).astype(int)

    # "market-proxy" public projection: simple usage-EWMA scaled by Vegas implied team total. Used (a) as a baseline
    # and (b) as the base of the simulated sharp line. Fixed constants => no fitted parameters, no leakage.
    for mk, stat in TARGETS.items():
        base = 0.5 * f[f"p_{stat}_ewm2"] + 0.5 * f[f"p_{stat}_ewm6"]
        expo = 0.3 if mk == "rush_yds" else 0.5
        env = (f["implied_tt"] / 22.0).clip(0.6, 1.5) ** expo
        f[f"mkt_proj_{mk}"] = (base * env).where(f["p_n_prior"] > 0)
        f[f"naive_{mk}"] = f[f"p_{stat}_ewm2"].where(f["p_n_prior"] > 0)
    return f


FEATURE_GROUPS = {
    "player_short": [f"p_{c}_ewm2" for c in STATS + SHARES],
    "player_long": [f"p_{c}_ewm6" for c in STATS + SHARES],
    "player_misc": ["p_passing_yards_lag1", "p_rushing_yards_lag1", "p_receiving_yards_lag1", "p_attempts_lag1",
                    "p_carries_lag1", "p_targets_lag1", "p_n_prior", "p_n_prior_season", "p_days_since_last",
                    "p_team_changed", "pos_code", "is_starting_qb"],
    "rates": ["p_ypa", "p_ypc", "p_ypt", "p_catch_rate", "p_adot", "p_pass_adot"],
    "team": ["team_pass_att_ewm4", "team_carries_ewm4", "team_pass_yds_ewm4", "team_rush_yds_ewm4",
             "team_pass_rate_ewm4", "team_plays_ewm4"],
    "opponent": [f"opp_allowed_{c}_ewm6" for c in ["qb_pass_yds", "rb_rush_yds", "wr_rec_yds", "te_rec_yds",
                                                    "rb_rec_yds", "attempts", "carries"]],
    "vegas": ["team_spread", "total_line", "implied_tt"],
    "context": ["is_home", "rest_days", "dome", "wind", "temp", "div_game", "week", "is_post"],
}
SNAP_COLS = ["p_offense_pct_ewm2", "p_offense_pct_ewm6"]

FEATURE_SETS = {
    "player_only": ["player_short", "player_long", "player_misc", "rates"],
    "player_vegas": ["player_short", "player_long", "player_misc", "rates", "vegas"],
    "full": list(FEATURE_GROUPS),
}


def feature_columns(feature_set: str, use_snaps: bool = True, extra_market_proj: bool = True) -> list[str]:
    cols = [c for grp in FEATURE_SETS[feature_set] for c in FEATURE_GROUPS[grp]]
    if not use_snaps:
        cols = [c for c in cols if c not in SNAP_COLS]
    if extra_market_proj:
        cols = cols + ["mkt_proj_pass_yds", "mkt_proj_rush_yds", "mkt_proj_rec_yds"]
    return cols


def load_features(first: int, last: int, refresh: bool = False) -> pd.DataFrame:
    from . import data
    p = CACHE / f"features_{first}_{last}.parquet"
    if p.exists() and not refresh:
        return pd.read_parquet(p)
    d = data.load(first, last)
    f = build_features(d)
    f.to_parquet(p, index=False)
    return f

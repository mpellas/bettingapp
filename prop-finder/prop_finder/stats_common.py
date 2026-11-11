"""Standardized game-log schema shared by NFL and college pipelines."""
STAT_COLS = ["completions", "attempts", "pass_yds", "pass_tds", "interceptions",
             "carries", "rush_yds", "rush_tds", "receptions", "targets", "rec_yds", "rec_tds"]
ID_COLS = ["league", "season", "week", "game_id", "game_date", "player_id", "espn_id", "player",
           "position", "team", "opp", "home_away"]


def add_derived(df):
    df = df.copy()
    for c in STAT_COLS:
        if c not in df:
            df[c] = 0.0
        df[c] = df[c].fillna(0.0).astype(float)
    df["rush_rec_yds"] = df["rush_yds"] + df["rec_yds"]
    df["pass_rush_yds"] = df["pass_yds"] + df["rush_yds"]
    df["rush_rec_tds"] = df["rush_tds"] + df["rec_tds"]
    return df


def pos_group(pos: str | None) -> str:
    p = pos.upper() if isinstance(pos, str) else ""
    if p in ("QB",):
        return "QB"
    if p in ("RB", "FB", "HB"):
        return "RB"
    if p in ("WR",):
        return "WR"
    if p in ("TE",):
        return "TE"
    return "OTH"

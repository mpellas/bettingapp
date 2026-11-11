"""PRE-GAME scoring for scheduled, unplayed games (Tester1 N2).

The backtest builds rows only from post-game stats. This module builds a row for every plausible player of every
team scheduled in (season, week), BEFORE the games are played, using prior data only:
  * data are truncated to games strictly before the week's first game day (a no-op live; it makes dry runs on past
    weeks honest);
  * WHO is scored comes from the DECISION snapshot (data/lines/snap_<season>_wk<week>_D.csv, the last capture
    >= 3 h before kickoff; nflprops.snaplines): one pre-game row per player-game that has a line there, never from
    post-game stats or snaps. A line that cannot be scored is written to a VOID report with a reason
    (no GSIS id match, no prior NFL data, event not in the schedule, player's last team not in that game) instead of
    being dropped silently. Without a D snapshot the run is a DRY RUN: candidates = players who appeared for the team
    in its last `lookback` games, predictions limited to the model universe; it is labelled as such;
  * stats of the new rows are NaN and enter every table only through shift(1)-ed history, so features = as-of;
  * QB universe = projected starter (the team's starter in its previous game);
  * the champion model is fit exactly as the walk-forward would: residual/scale model on data before the season's
    first game, mean model on data before the first game of the current `retrain_every_weeks` block.
Writes data/predictions/<season>_wk<WW>/pregame_<UTC>.parquet (99 predictive quantiles per row) + .csv summary, with
sha256 sidecars, and appends to data/predictions/pred_log.jsonl. If snapshot D-lines exist for that week
(nflprops.snaplines), P(over D-line) is attached.

    python -m nflprops.pregame --season 2026 --week 5
    python -m nflprops.pregame --season 2025 --week 10 --check     # dry run on a played week + as-of equivalence check
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import logging

import numpy as np
import pandas as pd

from . import DATA, EXPERIMENTS, ROOT
from .backtest import CODE_FILES
from .config import chash, deep_update, load_config, model_key
from .data import data_version, load
from .features import STATS, assemble_player_games, build_features, code_version, feature_columns
from .markets import MARKETS, universe_mask
from .model import QLEVELS, DistModel

log = logging.getLogger("pregame")
PRED = DATA / "predictions"


def champion_cfg() -> tuple[dict, str]:
    p = EXPERIMENTS / "champion.json"
    if p.exists():
        st = json.loads(p.read_text())
        return st["champion"], st["champion_hash"]
    c = load_config()
    return c, chash(model_key(c))


def truncate(d: dict, cutoff: pd.Timestamp) -> dict:
    """Drop every stat/snap row from games on/after `cutoff` and blank those games' outcome fields."""
    sch = d["schedules"].copy()
    gd = pd.to_datetime(sch["gameday"])
    later = set(sch.loc[gd >= cutoff, "game_id"])
    for c in ("home_score", "away_score", "result", "total", "home_qb_id", "away_qb_id", "spread_line",
              "total_line", "wind", "temp"):
        if c in sch:
            sch.loc[gd >= cutoff, c] = np.nan
    return {**d, "schedules": sch,
            "player_stats": d["player_stats"][~d["player_stats"]["game_id"].isin(later)],
            "snap_counts": d["snap_counts"][~d["snap_counts"]["game_id"].isin(later)]}


def candidate_rows(d: dict, season: int, week: int, lookback: int = 2) -> pd.DataFrame:
    sch = d["schedules"]
    games = sch[(sch["season"] == season) & (sch["week"] == week) & (sch["game_type"] == "REG")]
    pg = assemble_player_games(d)
    last = pg.sort_values(["gameday", "game_id"]).groupby("player_id").tail(1)
    tg = pg[["team", "game_id", "gameday"]].drop_duplicates().sort_values(["team", "gameday"])
    recent = tg.groupby("team").tail(lookback)
    appeared = pg.merge(recent[["team", "game_id"]], on=["team", "game_id"])["player_id"].unique()
    rows = []
    for g in games.itertuples():
        for team, opp in ((g.home_team, g.away_team), (g.away_team, g.home_team)):
            c = last[(last["team"] == team) & last["player_id"].isin(appeared)]
            for r in c.itertuples():
                rows.append({"player_id": r.player_id, "player_display_name": r.player_display_name,
                             "position": r.position, "position_group": getattr(r, "position_group", None),
                             "season": season, "week": week, "season_type": "REG", "game_id": g.game_id,
                             "team": team, "opponent": opp})
    x = pd.DataFrame(rows)
    for c in STATS + ["target_share", "air_yards_share", "offense_pct"]:
        x[c] = np.nan
    return x


def snapshot_rows(d: dict, season: int, week: int, lines: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """One pre-game row per (player, game) with a line in the decision snapshot; unscorable lines -> voids."""
    sch = d["schedules"]
    games = sch[(sch["season"] == season) & (sch["week"] == week) & (sch["game_type"] == "REG")].copy()
    games["espn"] = games["espn"].astype(str)
    pg = assemble_player_games(d)
    last = pg.sort_values(["gameday", "game_id"]).groupby("player_id").tail(1).set_index("player_id")
    L = lines.copy()
    L["event_id"] = L["event_id"].astype(str)
    L = L.merge(games[["espn", "game_id", "home_team", "away_team"]], left_on="event_id", right_on="espn", how="left")
    rows, voids = [], []
    if "void_reason" not in L:
        L["void_reason"] = np.nan
    for r in L.itertuples():
        reason = None
        if pd.notna(r.void_reason):           # snapshot-level void from snaplines (kickoff_moved / duplicate_line)
            reason = r.void_reason
        elif pd.isna(r.player_id):
            reason = "no player row: ESPN athlete id has no GSIS match in the nflverse players table"
        elif pd.isna(r.game_id):
            reason = "no player row: ESPN event not in the nflverse schedule for this week"
        elif r.player_id not in last.index:
            reason = "no player row: no prior NFL game data for this player"
        elif last.loc[r.player_id, "team"] not in (r.home_team, r.away_team):
            reason = f"no player row: player's last team ({last.loc[r.player_id, 'team']}) is not in this game"
        if reason:
            voids.append({"season": season, "week": week, "event_id": r.event_id, "game_id": r.game_id,
                          "player_id": r.player_id, "player_name": r.player_name, "market": r.market,
                          "line_D": r.line, "void_reason": reason,
                          "stage": "snapshot" if pd.notna(r.void_reason) else "pregame"})
            continue
        lr = last.loc[r.player_id]
        team = lr["team"]
        rows.append({"player_id": r.player_id, "player_display_name": lr["player_display_name"],
                     "position": lr["position"], "position_group": lr.get("position_group"), "season": season,
                     "week": week, "season_type": "REG", "game_id": r.game_id, "team": team,
                     "opponent": r.away_team if team == r.home_team else r.home_team})
    x = pd.DataFrame(rows).drop_duplicates(["player_id", "game_id"]) if rows else pd.DataFrame(
        columns=["player_id", "game_id"])
    for c in STATS + ["target_share", "air_yards_share", "offense_pct"]:
        x[c] = np.nan
    return x, pd.DataFrame(voids)


def pregame_features(d: dict, season: int, week: int, lookback: int = 2, lines: pd.DataFrame | None = None):
    """Truncate the data before the week's first game day, add pre-game rows (from the D snapshot if given, else
    recent-appearance candidates = dry run), build features. Returns (features, truncated data, rows, cutoff, voids)."""
    sch = d["schedules"]
    wk = sch[(sch["season"] == season) & (sch["week"] == week) & (sch["game_type"] == "REG")]
    cutoff = pd.to_datetime(wk["gameday"]).min()
    dt_ = truncate(d, cutoff)
    if lines is not None:
        extra, voids = snapshot_rows(dt_, season, week, lines)
    else:
        extra, voids = candidate_rows(dt_, season, week, lookback), pd.DataFrame()
    return build_features(dt_, extra), dt_, extra, cutoff, voids


def score(season: int, week: int, cfg: dict | None = None, lookback: int = 2, refresh_age_h: float = 12.0):
    cfg, champ_hash = (cfg, chash(model_key(cfg))) if cfg else champion_cfg()
    cfg = deep_update(cfg, {"data": {"last_season": max(season, cfg["data"]["last_season"])}})
    first = cfg["data"]["first_season"]
    d = load(first, season, max_age_h=refresh_age_h)
    sch = d["schedules"]
    wk = sch[(sch["season"] == season) & (sch["week"] == week) & (sch["game_type"] == "REG")]
    if wk.empty:
        raise SystemExit(f"no REG games for {season} week {week} in the schedule")
    from .snaplines import derive
    derive(season, week)                       # refresh D/C files from the raw snapshots (no-op without captures)
    dfile = DATA / "lines" / f"snap_{season}_wk{week}_D.csv"
    lines = pd.read_csv(dfile, dtype={"player_id": str, "event_id": str}) if dfile.exists() else None
    if lines is not None and "void_reason" not in lines:
        lines["void_reason"] = np.nan
    ok_lines = lines[lines["void_reason"].isna()] if lines is not None else None   # voided lines are never scored
    mode = "snapshot (D lines)" if lines is not None else "DRY RUN (no D snapshot: recent-appearance candidates)"
    f, dt_, extra, cutoff, voids = pregame_features(d, season, week, lookback, lines)
    dv = data_version(dt_, first, season)
    mc = cfg["model"]
    cols = feature_columns(mc["feature_set"], mc.get("use_snaps", True), mc.get("use_market_proj", True))
    k = int(mc.get("retrain_every_weeks", 4))
    blk_first = 1 + ((week - 1) // k) * k
    season_start = pd.to_datetime(sch[(sch["season"] == season) & (sch["game_type"] == "REG")]["gameday"]).min()
    blk = sch[(sch["season"] == season) & (sch["week"] == blk_first) & (sch["game_type"] == "REG")]
    blk_start = pd.to_datetime(blk["gameday"]).min()
    out = []
    for mk in cfg["markets"]:
        stat = MARKETS[mk]["stat"]
        u = f[universe_mask(f, mk, cfg.get("universe", {}).get("min_proj", 20.0))]
        real = u[u["is_pregame_row"] == 0]
        if lines is not None:     # every player with a D line in this market, in the model universe or not
            wkrows = f[(f["is_pregame_row"] == 1) & (f["season"] == season) & (f["week"] == week)]
            te = wkrows[wkrows["player_id"].isin(ok_lines.loc[ok_lines["market"] == mk, "player_id"])]
        else:
            te = u[(u["is_pregame_row"] == 1) & (u["season"] == season) & (u["week"] == week)]
        m = DistModel(mc.get("lgbm", {}), mc.get("dist", "empirical"), mc.get("n_folds", 3))
        trd = real[real["gameday"] < season_start]
        m.fit_dist(trd[cols], trd[stat].values, trd["season"].values)
        trm = real[real["gameday"] < blk_start]
        m.fit_mean(trm[cols], trm[stat].values)
        mu, s = m.predict(te[cols])
        q = m.quantiles(mu, s)
        r = te[["season", "week", "game_id", "gameday", "player_id", "player_display_name", "team", "opponent",
                "position", f"mkt_proj_{mk}", "is_proj_starter"]].rename(columns={f"mkt_proj_{mk}": "public_proj"})
        r = r.assign(in_model_universe=te.index.isin(u.index), market=mk, mu=mu, s=s, median=q[:, 49], p10=q[:, 9], p90=q[:, 89],
                     n_train_mean=len(trm), n_train_dist=len(trd))
        qdf = pd.DataFrame(q, columns=[f"q{int(round(x * 100)):02d}" for x in QLEVELS], index=r.index)
        out.append((pd.concat([r, qdf], axis=1), m))
    preds = pd.concat([o[0] for o in out], ignore_index=True)
    models = {mk: o[1] for mk, o in zip(cfg["markets"], out)}
    # attach P(over D-line) if snapshot-derived decision lines exist for that week
    preds["line_D"] = np.nan
    preds["p_over_D"] = np.nan
    if ok_lines is not None:
        L = ok_lines[["player_id", "market", "line"]].rename(columns={"line": "line_D"})
        dup = L.duplicated(["player_id", "market"], keep=False)
        if dup.any():                       # snaplines voids every duplicate; never keep an arbitrary first row
            raise ValueError(f"{int(dup.sum())} non-void duplicate (player, market) lines in {dfile}")
        preds = preds.drop(columns=["line_D"]).merge(L, on=["player_id", "market"], how="left")
        for mk, m in models.items():
            ix = (preds["market"] == mk) & preds["line_D"].notna()
            preds.loc[ix, "p_over_D"] = m.prob_over(preds.loc[ix, "mu"].values, preds.loc[ix, "s"].values,
                                                    preds.loc[ix, "line_D"].values)
    now = dt.datetime.now(dt.timezone.utc)
    meta = {"created_at_utc": now.isoformat(timespec="seconds"),
            "created_at_pt": now.astimezone().isoformat(timespec="seconds"), "season": season, "week": week,
            "champion_hash": champ_hash, "config_hash": chash(model_key(cfg)), "code_version": code_version(CODE_FILES),
            "pregame_code_sha1": hashlib.sha1(open(__file__, "rb").read()).hexdigest()[:10],
            "data_version": dv, "data_cutoff": str(cutoff.date()), "dist_fit_before": str(season_start.date()),
            "mean_fit_before": str(blk_start.date()), "lookback_games": lookback,
            "mode": mode, "n_rows_built": int(len(extra)), "n_void_lines": int(len(voids)),
            "void_reasons": voids["void_reason"].value_counts().to_dict() if len(voids) else {}, "n_predictions": {mk: int((preds["market"] == mk).sum()) for mk in cfg["markets"]},
            "d_lines_file": str(dfile.relative_to(DATA.parent)) if dfile.exists() else None,
            "d_lines_sha256": hashlib.sha256(dfile.read_bytes()).hexdigest() if dfile.exists() else None,
            "d_captured_at_utc": (lines.groupby("event_id")["captured_at_utc"].first().to_dict()
                                  if lines is not None else None),
            "n_with_line_D": int(preds["line_D"].notna().sum())}
    odir = PRED / f"{season}_wk{week:02d}"
    odir.mkdir(parents=True, exist_ok=True)
    stem = f"pregame_{now.strftime('%Y%m%dT%H%M%SZ')}"
    pq, csv = odir / f"{stem}.parquet", odir / f"{stem}.csv"
    preds.to_parquet(pq, index=False)
    preds.drop(columns=[c for c in preds.columns if c.startswith("q") and c[1:].isdigit()]).to_csv(csv, index=False)
    for p in (pq, csv):
        h = hashlib.sha256(p.read_bytes()).hexdigest()
        p.with_suffix(p.suffix + ".sha256").write_text(f"{h}  {p.name}\n")
        meta[f"sha256_{p.suffix[1:]}"] = h
    meta["files"] = [str(pq.relative_to(DATA.parent)), str(csv.relative_to(DATA.parent))]
    if lines is not None:
        vf = odir / f"{stem}_voids.csv"
        (voids if len(voids) else pd.DataFrame(columns=["season", "week", "event_id", "game_id", "player_id",
                                                         "player_name", "market", "line_D", "void_reason", "stage"])
         ).to_csv(vf, index=False)
        meta["void_report"] = str(vf.relative_to(DATA.parent))
        meta["sha256_voids"] = hashlib.sha256(vf.read_bytes()).hexdigest()
    (odir / f"{stem}.meta.json").write_text(json.dumps(meta, indent=1))
    with open(PRED / "pred_log.jsonl", "a") as fh:
        fh.write(json.dumps(meta) + "\n")
    return preds, meta, f


def asof_check(season: int, week: int, f_pre: pd.DataFrame, cfg: dict) -> dict:
    """As-of equivalence: features of the pre-game rows must equal the features the full (post-game) build gives
    the same player-games, for every model feature."""
    from .features import load_features
    full = load_features(cfg["data"]["first_season"], season)
    mc = cfg["model"]
    cols = feature_columns(mc["feature_set"], mc.get("use_snaps", True), mc.get("use_market_proj", True))
    a = f_pre[(f_pre["is_pregame_row"] == 1) & (f_pre["week"] == week) & (f_pre["season"] == season)]
    b = full[(full["season"] == season) & (full["week"] == week)]
    m = a.merge(b, on=["player_id", "game_id"], suffixes=("_pre", "_full"))
    bad = {}
    for c in cols:
        x, y = m[f"{c}_pre"].astype(float), m[f"{c}_full"].astype(float)
        diff = ~(np.isclose(x, y, equal_nan=True))
        if diff.any():
            bad[c] = int(diff.sum())
    return {"n_pregame_rows": int(len(a)), "n_played_rows": int(len(b)), "n_matched": int(len(m)),
            "played_rows_not_candidates": int(len(b) - len(m)), "candidates_who_did_not_play": int(len(a) - len(m)),
            "n_features": len(cols), "features_with_differences": bad}


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(message)s")
    ap = argparse.ArgumentParser()
    ap.add_argument("--season", type=int, required=True)
    ap.add_argument("--week", type=int, required=True)
    ap.add_argument("--lookback", type=int, default=2)
    ap.add_argument("--max-age-hours", type=float, default=12.0, help="refresh in-season data older than this")
    ap.add_argument("--check", action="store_true", help="as-of equivalence check (played weeks only)")
    a = ap.parse_args()
    preds, meta, f = score(a.season, a.week, lookback=a.lookback, refresh_age_h=a.max_age_hours)
    if meta["mode"].startswith("DRY"):
        print("NOTE: no decision snapshot for this week -> DRY RUN (candidates from recent appearances).")
    print(json.dumps(meta, indent=1))
    print(preds.groupby("market").agg(n=("mu", "size"), mean_mu=("mu", "mean")).round(1).to_string())
    if a.check:
        chk = asof_check(a.season, a.week, f, champion_cfg()[0])
        chk.update({"season": a.season, "week": a.week, "pred_file": meta["files"][0], "mode": meta["mode"],
                    "checked_at": dt.datetime.now().astimezone().isoformat(timespec="seconds")})
        chk["pred_sha256"] = meta["sha256_parquet"]
        chk["d_lines_sha256"] = meta.get("d_lines_sha256")
        out = ROOT / "reports" / f"pregame_asof_check_{a.season}_wk{a.week:02d}.json"
        out.write_text(json.dumps(chk, indent=1))
        h = hashlib.sha256(out.read_bytes()).hexdigest()
        out.with_suffix(".json.sha256").write_text(f"{h}  {out.name}\n")
        print(json.dumps(chk, indent=1))
        print(f"wrote {out.relative_to(ROOT)} sha256 {h}")

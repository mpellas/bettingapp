"""Walk-forward 2025 backtest harness (NFL + FBS) that drives the live model code paths.

For each week W the model sees only: current-season logs from weeks < W, the full prior season, team scoring from
weeks < W, the official injury report for week W (NFL), and pregame implied totals (closing spread/total).
Lines: real historical ESPN BET opening main lines where ESPN still serves them; otherwise a clearly labelled
SYNTHETIC proxy line (floor(trailing-5 average) + 0.5 at -110/-110) used only for the proxy evaluation.
"""
from __future__ import annotations

import math
import time
from collections import defaultdict

import numpy as np
import pandas as pd

from . import analysis, cfb_context, cfbd, hist_lines, nfl_stats
from .stats_common import pos_group

SEASON = 2025
NFL_WEEKS = list(range(2, 19))
CFB_WEEKS = list(range(2, 17))
STATS = ["pass_yds", "completions", "attempts", "pass_tds", "interceptions", "rush_yds", "carries", "rec_yds",
         "receptions", "rush_rec_yds", "pass_rush_yds", "rush_tds", "rec_tds", "rush_rec_tds"]


# ------------------------------------------------------------------ NFL inputs
def prepare_nfl():
    logs = nfl_stats.game_logs([SEASON - 1, SEASON])
    games = nfl_stats.load_games()
    g = games[(games.season == SEASON) & (games.game_type == "REG")].copy()
    g["espn"] = g["espn"].astype("Int64").astype(str)
    gid2ev = dict(zip(g.game_id, g.espn))
    inj_all = nfl_stats.load_injuries(SEASON)
    cur = logs[logs.season == SEASON].copy()
    cur["event_id"] = cur["game_id"].map(gid2ev)
    weeks = {}
    for W in NFL_WEEKS:
        lw = logs[(logs.season < SEASON) | (logs.week < W)]
        gw = g[g.week == W]
        slate = []
        for r in gw.itertuples():
            tot, spr = r.total_line, r.spread_line
            hi = ai = None
            if pd.notna(tot) and pd.notna(spr):
                hi, ai = (tot + spr) / 2, (tot - spr) / 2
            slate.append({"event_id": r.espn, "name": f"{r.away_team} @ {r.home_team}", "date_utc": str(r.gameday),
                          "state": "pre", "completed": False, "home": r.home_team, "away": r.away_team,
                          "neutral": r.location == "Neutral", "home_implied": hi, "away_implied": ai,
                          "indoor": r.roof in ("dome", "closed")})
        prev = g[(g.week < W) & g.home_score.notna()]
        tp = pd.concat([pd.DataFrame({"season": SEASON, "team": prev.home_team, "pts": prev.home_score}),
                        pd.DataFrame({"season": SEASON, "team": prev.away_team, "pts": prev.away_score})])
        inj = {}
        if not inj_all.empty:
            for r in inj_all[(inj_all.week == W)].itertuples():
                if isinstance(r.report_status, str) and r.report_status:
                    inj[str(r.gsis_id)] = {"status": r.report_status,
                                           "detail": r.report_primary_injury if isinstance(r.report_primary_injury, str) else ""}
        act = cur[cur.week == W]
        weeks[W] = {"logs": lw, "slate": slate, "team_pts": tp, "injuries": inj, "weather": {}, "ctx": None,
                    "actuals": {(str(r.player_id), str(r.event_id)): {s: getattr(r, s) for s in STATS}
                                for r in act.itertuples()}}
    return weeks


# ------------------------------------------------------------------ college inputs
def _cfb_positions(logs):
    roster = cfbd.get("/roster", {"year": SEASON}, ttl=None)
    pos = {str(r["id"]): r.get("position") for r in roster}
    logs = logs.copy()
    logs["position"] = logs["player_id"].map(pos)
    # players missing from CFBD's roster: infer the group from usage (flagged)
    agg = logs.groupby("player_id")[["attempts", "carries", "receptions"]].mean()
    inferred = agg.apply(lambda r: "QB" if r.attempts >= 5 else ("RB" if r.carries > r.receptions else "WR"), axis=1)
    miss = logs["position"].isna()
    logs.loc[miss, "position"] = logs.loc[miss, "player_id"].map(inferred)
    logs["position_inferred"] = miss
    logs["pos_group"] = logs["position"].map(pos_group)
    return logs


def prepare_cfb(c: cfb_context.Context | None = None):
    c = c or cfb_context.Context(SEASON, asof_ratings=True)
    allg = cfbd.get("/games", {"year": SEASON, "seasonType": "regular"}, ttl=None)
    lines = cfbd.get("/lines", {"year": SEASON, "seasonType": "regular"}, ttl=None)
    implied = {}
    for ln in lines:
        sp = [x["spread"] for x in ln.get("lines", []) if x.get("spread") is not None]
        ou = [x["overUnder"] for x in ln.get("lines", []) if x.get("overUnder") is not None]
        if sp and ou:
            s, o = float(np.median(sp)), float(np.median(ou))   # CFBD spread is the home line
            implied[str(ln["id"])] = ((o - s) / 2, (o + s) / 2)
    logs25 = c._prev_logs(SEASON)            # CFBD /games/players 2025 (cached), same parser as the prior season
    logs25 = _cfb_positions(logs25)
    logs25 = logs25[logs25.week <= 16]
    weeks = {}
    for W in CFB_WEEKS:
        cur = logs25[logs25.week < W].copy()
        t0 = time.time()
        ctx, logs = cfb_context.make_ctx(c, cur.drop(columns=["position_inferred"]))
        # prior-season rows need a pos_group column for concat consistency (unused for projection role)
        gw = [x for x in allg if x["week"] == W and "fbs" in (x.get("homeClassification"), x.get("awayClassification"))]
        slate = []
        for x in gw:
            hi, ai = implied.get(str(x["id"]), (None, None))
            slate.append({"event_id": str(x["id"]), "name": f"{x['awayTeam']} @ {x['homeTeam']}",
                          "date_utc": x["startDate"], "state": "pre", "completed": False, "home": x["homeTeam"],
                          "away": x["awayTeam"], "neutral": bool(x.get("neutralSite")), "home_implied": hi,
                          "away_implied": ai, "indoor": None})
        prev = [x for x in allg if x["week"] < W and x.get("homePoints") is not None]
        tp = pd.DataFrame([{"season": SEASON, "team": x["homeTeam"], "pts": x["homePoints"]} for x in prev] +
                          [{"season": SEASON, "team": x["awayTeam"], "pts": x["awayPoints"]} for x in prev])
        act = logs25[logs25.week == W]
        weeks[W] = {"logs": logs, "slate": slate, "team_pts": tp, "injuries": {}, "weather": {}, "ctx": ctx,
                    "ctx_secs": round(time.time() - t0, 1),
                    "actuals": {(str(r.player_id), str(r.game_id)): {s: getattr(r, s) for s in STATS}
                                for r in act.itertuples()}}
    return weeks, logs25


# ------------------------------------------------------------------ projection + lines
def project(weeks: dict, league: str, wk_list=None) -> pd.DataFrame:
    out = []
    for W in (wk_list or sorted(weeks)):
        d = weeks[W]
        proj, _ = analysis.build_projections(d["logs"], SEASON, d["slate"], d["team_pts"], d["injuries"],
                                             d["weather"], league, d["ctx"])
        if proj.empty:
            continue
        proj["week"] = W
        out.append(proj)
    return pd.concat(out, ignore_index=True) if out else pd.DataFrame()


def real_lines(league: str, event_ids) -> pd.DataFrame:
    rows = []
    for ev in sorted(set(event_ids)):
        p = hist_lines.DIR / league / f"{ev}.json"
        if not p.exists():
            continue
        import json
        rows.extend(hist_lines.parse_event(league, json.loads(p.read_text())))
    df = pd.DataFrame(rows)
    if df.empty:
        return df
    df = df[df["line_open"].notna()].copy()
    # grade against the OPENING main line (posted pregame). The feed's 'current' line is the last listed line and
    # is updated after kickoff (in-game), so it is NOT used for grading.
    both = df["over_open"].notna() & df["under_open"].notna()
    df["line"] = df["line_open"].astype(float)
    df["over_price"] = df["over_open"].where(both)
    df["under_price"] = df["under_open"].where(both)
    df["line_note"] = "opening main line (pregame)"
    return df


def synthetic_lines(proj: pd.DataFrame) -> pd.DataFrame:
    """PROXY ONLY: floor(trailing-5 average incl. prior season) + 0.5, -110 both sides. Not a market line."""
    p = proj.drop_duplicates(["player_id", "event_id", "stat"])
    return pd.DataFrame({"espn_id": p["player_id"].astype(str), "event_id": p["event_id"].astype(str),
                         "stat": p["stat"], "line": np.floor(p["l5_avg"].astype(float)) + 0.5,
                         "line_open": np.nan, "over_price": -110, "under_price": -110, "book": "SYNTHETIC",
                         "source": "SYNTHETIC proxy: floor(trailing-5 avg)+0.5", "line_note": "synthetic proxy line"})


def rank_week(proj_w: pd.DataFrame, lines: pd.DataFrame, synthetic: bool) -> pd.DataFrame:
    p = proj_w.copy()
    if synthetic:
        p["espn_id"] = p["player_id"].astype(str)
    p["event_id"] = p["event_id"].astype(str)
    r = analysis.rank_props(p, lines)
    if r.empty:
        return r
    r["week"] = int(proj_w["week"].iloc[0])
    return r


def rank_all(proj: pd.DataFrame, lines: pd.DataFrame | None, synthetic=False) -> pd.DataFrame:
    out = []
    for W, pw in proj.groupby("week"):
        ln = synthetic_lines(pw) if synthetic else lines[lines.event_id.isin(set(pw.event_id.astype(str)))]
        if ln is None or ln.empty:
            continue
        r = rank_week(pw, ln, synthetic)
        if not r.empty:
            out.append(r)
    return pd.concat(out, ignore_index=True) if out else pd.DataFrame()


# ------------------------------------------------------------------ grading
def _profit(win: bool, price) -> float:
    price = -110 if price is None or (isinstance(price, float) and math.isnan(price)) else float(price)
    return (100 / -price if price < 0 else price / 100) if win else -1.0


def attach_actuals(df: pd.DataFrame, weeks: dict, key_col="player_id") -> pd.DataFrame:
    if df.empty:
        return df
    acts = {}
    for W, d in weeks.items():
        acts.update(d["actuals"])
    vals = []
    for r in df.itertuples():
        a = acts.get((str(getattr(r, key_col)), str(r.event_id)))
        vals.append(np.nan if a is None else float(a.get(r.stat, np.nan)))
    df = df.copy()
    df["actual"] = vals
    return df


def grade(r: pd.DataFrame, weeks: dict) -> pd.DataFrame:
    r = attach_actuals(r, weeks)
    res = np.where(r.actual.isna(), "void", np.where(r.actual == r.line, "push",
                   np.where((r.actual > r.line) == (r.pick == "OVER"), "win", "loss")))
    r["result"] = res
    price = np.where(r.pick == "OVER", r.over_price, r.under_price)
    r["profit_110"] = [(_profit(x == "win", -110) if x in ("win", "loss") else 0.0) for x in res]
    r["profit_price"] = [(_profit(x == "win", pr) if x in ("win", "loss") else 0.0) for x, pr in zip(res, price)]
    r["over_hit"] = np.where(r.actual.isna() | (r.actual == r.line), np.nan, (r.actual > r.line).astype(float))
    return r


def summarize(g: pd.DataFrame, label="") -> dict:
    d = g[g.result.isin(["win", "loss"])]
    n = len(d)
    w = int((d.result == "win").sum())
    return {"group": label, "bets": n, "wins": w, "losses": n - w,
            "pushes": int((g.result == "push").sum()), "voids": int((g.result == "void").sum()),
            "hit_rate": round(float(w / n), 4) if n else None,
            "roi_110": round(float(d.profit_110.sum() / n), 4) if n else None,
            "roi_price": round(float(d.profit_price.sum() / n), 4) if n else None,
            "units_110": round(float(d.profit_110.sum()), 2)}


def top_n(g: pd.DataFrame, n: int, score="rank_score") -> pd.DataFrame:
    """Top-n picks per league-week chosen pregame (voids stay in the selection and are refunded)."""
    return g.sort_values(score, ascending=False).groupby(["league", "week"], group_keys=False).head(n)


def calibration(g: pd.DataFrame, col="model_p_side") -> pd.DataFrame:
    d = g[g.result.isin(["win", "loss"])].copy()
    bins = [0.5, 0.525, 0.55, 0.575, 0.6, 0.65, 0.7, 0.8, 1.0001]
    d["bucket"] = pd.cut(d[col], bins, right=False)
    t = d.groupby("bucket", observed=True).agg(bets=("result", "size"), mean_pred=(col, "mean"),
                                               hit_rate=("result", lambda s: (s == "win").mean()))
    t = t.reset_index()
    t["bucket"] = t["bucket"].astype(str)
    return t.round(4)


def brier(g: pd.DataFrame, col="p_over") -> float | None:
    d = g[g.over_hit.notna()]
    return round(float(((d[col] - d.over_hit) ** 2).mean()), 5) if len(d) else None


def logloss(g: pd.DataFrame, col="p_over") -> float | None:
    d = g[g.over_hit.notna()]
    p = d[col].clip(1e-4, 1 - 1e-4)
    return round(float(-(d.over_hit * np.log(p) + (1 - d.over_hit) * np.log(1 - p)).mean()), 5) if len(d) else None


def proj_accuracy(proj: pd.DataFrame, weeks: dict) -> pd.DataFrame:
    p = attach_actuals(proj, weeks)
    p = p[p.actual.notna()]
    rows = []
    for (lg, st), d in p.groupby(["league", "stat"]):
        rows.append({"league": lg, "stat": st, "n": len(d), "mean_actual": round(d.actual.mean(), 2),
                     "model_mae": round((d.projection - d.actual).abs().mean(), 3),
                     "model_bias": round((d.projection - d.actual).mean(), 3),
                     "season_avg_mae": round((d.season_avg - d.actual).abs().mean(), 3),
                     "l5_avg_mae": round((d.l5_avg - d.actual).abs().mean(), 3)})
    t = pd.DataFrame(rows)
    if not t.empty:
        t["mae_vs_season_avg_pct"] = ((t.model_mae / t.season_avg_mae - 1) * 100).round(1)
    return t


def norm_mae(proj: pd.DataFrame, weeks: dict, wk=None) -> float:
    """Scale-free projection error: mean over stats of model MAE / trailing-season-average MAE (lower is better)."""
    p = proj if wk is None else proj[proj.week.isin(wk)]
    t = proj_accuracy(p, weeks)
    t = t[t.n >= 30]
    return round(float((t.model_mae / t.season_avg_mae).mean()), 5) if len(t) else float("nan")

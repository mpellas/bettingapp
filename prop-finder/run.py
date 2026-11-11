#!/usr/bin/env python3
"""Football player-prop finder.  Usage:  python run.py --league nfl|ncaaf|all [--top 25]"""
from __future__ import annotations

import argparse
import sys
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

from prop_finder import analysis, cfb_context, cfb_stats, cfbd, espn, nfl_stats, odds, report

ROOT = Path(__file__).resolve().parent
MAIN_STAT = {"QB": "pass_yds", "RB": "rush_yds", "WR": "rec_yds", "TE": "rec_yds"}


def log(msg):
    print(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}", file=sys.stderr, flush=True)


def dvp_slate_view(dvp: pd.DataFrame, slate: list[dict]) -> pd.DataFrame:
    rows = []
    for g in slate:
        if g.get("completed"):
            continue
        for off, de in ((g["home"], g["away"]), (g["away"], g["home"])):
            for pg, st in MAIN_STAT.items():
                d = dvp[(dvp.def_team == de) & (dvp.pos_group == pg) & (dvp.stat == st)]
                if d.empty:
                    continue
                d = d.iloc[0]
                rows.append({"Offense": off, "vs Defense": de, "Pos": pg, "Stat": analysis.LABEL[st],
                             "Allowed/g": round(d.allowed_pg, 1), "x Lg avg": round(d.ratio, 2),
                             "Rank (1=most allowed)": f"{int(d.rank_most_allowed)}/{int(d.n_teams)}",
                             "Def G": int(d.def_games)})
    df = pd.DataFrame(rows)
    if df.empty:
        return df
    df = df.sort_values("x Lg avg", ascending=False)
    parts = []
    for pg in MAIN_STAT:  # 3 easiest + 3 toughest per position group
        d = df[df["Pos"] == pg]
        parts.append(d.head(3).assign(Matchup="easiest"))
        parts.append(d.tail(3).assign(Matchup="toughest"))
    return pd.concat(parts).drop_duplicates(subset=["Offense", "vs Defense", "Pos"])


def fetch_context(league: str, games: list[dict]):
    pending = [g for g in games if not g["completed"]]
    weather, inj = {}, {}

    def one(g):
        return g["event_id"], espn.game_weather(league, g["event_id"], g.get("indoor")), espn.game_injuries(league, g["event_id"])
    with ThreadPoolExecutor(8) as ex:
        for eid, w, i in ex.map(one, pending):
            weather[eid] = w
            inj.update(i)
    return weather, inj


def fetch_lines(league: str, games: list[dict], args, status: dict) -> pd.DataFrame:
    pending = [g for g in games if not g["completed"]]
    rows, notes = [], {}
    if not args.no_espn_props:
        now = datetime.now(timezone.utc)
        with ThreadPoolExecutor(6) as ex:
            for g, (r, note) in zip(pending, ex.map(lambda g: odds.espn_props(league, g, now), pending)):
                rows.extend(r)
                notes[g["name"]] = f"{note} ({len(r)} lines)"
        n_with = sum(1 for v in notes.values() if not v.endswith("(0 lines)"))
        status["Prop lines: ESPN/DraftKings (no key)"] = f"{n_with}/{len(pending)} games had O/U player lines; " + \
            "; ".join(f"{k}: {v}" for k, v in notes.items())
    oa, note = odds.odds_api_props(league, games, max_events=args.odds_max_events)
    status["Prop lines: The Odds API (ODDS_API_KEY)"] = note
    rows.extend(oa)
    return pd.DataFrame(rows)


def run_league(league: str, args) -> dict:
    status = {}
    ctx = None
    season, week, games = espn.current_slate(league)
    pending = [g for g in games if not g["completed"]]
    status["Slate (ESPN scoreboard)"] = (f"{len(games)} games in week {week}; {len(pending)} not final "
                                         f"({sum(g['state'] == 'pre' for g in games)} not started)")
    log(f"{league}: season {season} week {week}, {len(games)} games")

    if league == "nfl":
        try:
            logs = nfl_stats.game_logs([season - 1, season])
            tp = nfl_stats.team_points([season])
            cur = logs[logs.season == season]
            status["Player stats (nflverse stats_player_week)"] = (
                f"OK: {len(cur)} player-games in {season} (weeks {int(cur.week.min())}-{int(cur.week.max())}), "
                f"{len(logs) - len(cur)} from {season - 1}")
        except Exception as e:  # noqa: BLE001
            status["Player stats (nflverse)"] = f"FAILED: {e}"
            raise
        for g in games:  # ESPN -> nflverse team codes
            g["home"] = nfl_stats.ESPN_TO_NFLVERSE.get(g["home"], g["home"])
            g["away"] = nfl_stats.ESPN_TO_NFLVERSE.get(g["away"], g["away"])
        weather, inj = fetch_context(league, games)
        rep = nfl_stats.injury_report(season, week)
        n_rep = 0
        for r in rep.itertuples():
            if isinstance(r.report_status, str) and r.gsis_id not in inj:
                inj[r.gsis_id] = {"status": r.report_status, "detail": r.report_primary_injury if isinstance(r.report_primary_injury, str) else ""}
                n_rep += 1
        status["Injuries"] = f"ESPN game-day list + nflverse week-{week} report ({len(rep)} rows)"
    else:
        logs, tp, meta = cfb_stats.game_logs(season, through_week=week)
        status["Player stats (ESPN box scores, FBS)"] = (
            f"OK: {meta['final_games']} final FBS games parsed, weeks 1-{int(logs.week.max())} ({meta['summary_failures']} failures), "
            f"{len(logs)} player-games; previous season not loaded")
        weather, inj = fetch_context(league, games)
        ids = sorted({g["home_id"] for g in pending} | {g["away_id"] for g in pending})
        inj.update(cfb_stats.roster_out_list(ids))
        status["Injuries"] = (f"no official college injury feed used; ESPN roster IR/out entries: {len(inj)}; "
                              "players with no stats in team's last game are flagged")
        if args.no_cfbd:
            status["CFBD (CFBD_API_KEY)"] = "disabled by --no-cfbd (v1 college model)"
        elif not cfbd.available():
            status["CFBD (CFBD_API_KEY)"] = "skipped: CFBD_API_KEY not set -> v1 college model (no transfer priors / opponent adjustment)"
        else:
            try:
                c = cfb_context.Context(season)
                ctx, logs = cfb_context.make_ctx(c, logs)
                priors = ctx["priors"]
                k = [k for k in status if k.startswith("Player stats")][0]
                status[k] = status[k].replace("previous season not loaded",
                                              f"{season - 1} season from CFBD (followed across schools)")
                ss = cfbd.session_stats()
                status["CFBD (CFBD_API_KEY)"] = (
                    f"OK: {len(c.logs_prev)} {season - 1} player-games, SP+ {season - 1}/{season} "
                    f"({len(c.ratings[season]['by_id'])} FBS teams rated), {len(c.portal)} portal entries, "
                    f"returning production for {len(c.ret_by_id)} teams; {len(priors)} players with a prior "
                    f"({sum(p['moved'] for p in priors.values())} changed schools). "
                    f"CFBD network calls this run: {ss['network']} (cache hits {ss['cached']})")
            except Exception as e:  # noqa: BLE001
                ctx = None
                status["CFBD (CFBD_API_KEY)"] = f"FAILED, fell back to v1 college model: {e}"
    n_wx = sum(1 for w in weather.values() if w.get("temp_f") is not None)
    status["Weather (ESPN summary / AccuWeather)"] = f"{n_wx} outdoor forecasts, {sum(1 for w in weather.values() if w['weather'] == 'Indoor')} indoor"

    log(f"{league}: building projections")
    proj, dvp = analysis.build_projections(logs, season, games, tp, inj, weather, league, ctx)
    log(f"{league}: {len(proj)} player-stat projections; fetching lines")
    lines = fetch_lines(league, games, args, status)
    ranked = analysis.rank_props(proj, lines)
    status["Lines matched to projections"] = f"{len(ranked)} of {len(lines)} lines"
    return {"league": league, "season": season, "week": week, "games": games, "proj": proj, "dvp": dvp, "ctx": ctx,
            "dvp_view": dvp_slate_view(dvp, games), "lines": lines, "ranked": ranked, "status": status}


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--league", choices=["nfl", "ncaaf", "all"], default="all")
    ap.add_argument("--top", type=int, default=25)
    ap.add_argument("--out", default=str(ROOT / "output"))
    ap.add_argument("--odds-max-events", type=int, default=8,
                    help="max events to query on The Odds API per league (each costs ~#markets credits)")
    ap.add_argument("--no-espn-props", action="store_true", help="skip ESPN/DraftKings prop lines")
    ap.add_argument("--no-cfbd", action="store_true", help="college: ignore CFBD (v1 model, for comparison)")
    ap.add_argument("--tag", default="", help="suffix for the output folder name")
    args = ap.parse_args()

    leagues = ["nfl", "ncaaf"] if args.league == "all" else [args.league]
    gen = datetime.now(timezone.utc)
    stamp = gen.astimezone(report.PT).strftime("%Y-%m-%d_%H%M")
    outdir = Path(args.out) / (stamp + (f"_{args.tag}" if args.tag else ""))
    outdir.mkdir(parents=True, exist_ok=True)
    results = []
    for lg in leagues:
        try:
            res = run_league(lg, args)
        except Exception as e:  # noqa: BLE001
            log(f"{lg} FAILED: {e}")
            import traceback; traceback.print_exc()
            continue
        results.append(res)
        pre = f"{lg}_{res['season']}_wk{res['week']}"
        proj = res["proj"].drop(columns=[c for c in res["proj"].columns if c in ("vals_cur", "vals_all")])
        if "kickoff_utc" in proj:
            proj.insert(proj.columns.get_loc("kickoff_utc") + 1, "kickoff_pt", proj["kickoff_utc"].map(report.to_pt))
        proj.to_csv(outdir / f"{pre}_projections.csv", index=False)
        res["dvp"].to_csv(outdir / f"{pre}_defense_vs_position.csv", index=False)
        res["lines"].to_csv(outdir / f"{pre}_prop_lines_raw.csv", index=False)
        rk = res["ranked"]
        if not rk.empty:
            rk.insert(rk.columns.get_loc("kickoff_utc") + 1, "kickoff_pt", rk["kickoff_utc"].map(report.to_pt))
        rk.to_csv(outdir / f"{pre}_ranked_props.csv", index=False)
        if res.get("ctx"):
            res["ctx"]["transfers"].to_csv(outdir / f"{pre}_transfers.csv", index=False)
            res["ctx"]["vacated_df"].to_csv(outdir / f"{pre}_vacated_roles_by_team.csv", index=False)
        log(f"{lg}: wrote CSVs ({len(proj)} projections, {len(rk)} ranked props)")
    if not results:
        sys.exit("no league produced results")
    md = report.build_markdown(results, gen, args.top)
    (outdir / "report.md").write_text(md)
    (outdir / "report.html").write_text(report.md_to_html(md))
    latest = Path(args.out) / "latest"
    if latest.is_symlink() or latest.exists():
        latest.unlink()
    latest.symlink_to(outdir.name)
    print(f"Output written to {outdir}")
    for res in results:
        print(f"\n== {res['league'].upper()} {res['season']} wk {res['week']} ==")
        for k, v in res["status"].items():
            print(f"  {k}: {v[:300]}")


if __name__ == "__main__":
    main()

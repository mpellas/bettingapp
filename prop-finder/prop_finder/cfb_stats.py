"""College (FBS) game logs built from ESPN box scores (no key)."""
from __future__ import annotations

import sys
from concurrent.futures import ThreadPoolExecutor

import pandas as pd

from . import espn
from .stats_common import add_derived, pos_group


def _num(x):
    try:
        return float(x)
    except (TypeError, ValueError):
        return 0.0


def parse_boxscore(summ: dict, season: int, week: int) -> list[dict]:
    comp = summ["header"]["competitions"][0]
    neutral = bool(comp.get("neutralSite"))
    teams = {c["team"]["id"]: c for c in comp["competitors"]}
    date = comp.get("date", "")[:10]
    gid = summ["header"]["id"]
    rows: dict[tuple, dict] = {}
    for tblock in (summ.get("boxscore") or {}).get("players", []):
        tid = tblock["team"]["id"]
        me = teams.get(tid, {})
        opp = next((c for k, c in teams.items() if k != tid), {})
        ha = "N" if neutral else ("H" if me.get("homeAway") == "home" else "A")
        for cat in tblock.get("statistics", []):
            keys = cat.get("keys", [])
            for a in cat.get("athletes", []):
                ath = a.get("athlete") or {}
                aid = str(ath.get("id"))
                if not aid or aid.startswith("-"):
                    continue
                st = dict(zip(keys, a.get("stats", [])))
                r = rows.setdefault((aid, tid), {
                    "league": "ncaaf", "season": season, "week": week, "game_id": gid,
                    "game_date": date, "player_id": aid, "espn_id": aid,
                    "player": ath.get("displayName"), "team": tblock["team"].get("abbreviation"),
                    "team_id": tid, "opp": opp.get("team", {}).get("abbreviation"),
                    "opp_id": opp.get("team", {}).get("id"), "home_away": ha,
                })
                n = cat.get("name")
                if n == "passing":
                    ca = str(st.get("completions/passingAttempts", "0/0")).split("/")
                    r["completions"] = _num(ca[0]); r["attempts"] = _num(ca[1] if len(ca) > 1 else 0)
                    r["pass_yds"] = _num(st.get("passingYards")); r["pass_tds"] = _num(st.get("passingTouchdowns"))
                    r["interceptions"] = _num(st.get("interceptions"))
                elif n == "rushing":
                    r["carries"] = _num(st.get("rushingAttempts")); r["rush_yds"] = _num(st.get("rushingYards"))
                    r["rush_tds"] = _num(st.get("rushingTouchdowns"))
                elif n == "receiving":
                    r["receptions"] = _num(st.get("receptions")); r["rec_yds"] = _num(st.get("receivingYards"))
                    r["rec_tds"] = _num(st.get("receivingTouchdowns"))
    return list(rows.values())


def season_events(season: int, through_week: int) -> list[tuple[int, dict]]:
    evs = []
    for wk in range(1, through_week + 1):
        try:
            sb = espn.scoreboard("ncaaf", week=wk, season=season, ttl=3600 if wk >= through_week - 1 else 24 * 3600)
        except Exception as e:  # noqa: BLE001
            print(f"[ncaaf] scoreboard week {wk} failed: {e}", file=sys.stderr)
            continue
        for ev in sb.get("events", []):
            evs.append((wk, espn.parse_event(ev)))
    return evs


def game_logs(season: int, through_week: int, workers: int = 8) -> tuple[pd.DataFrame, pd.DataFrame, dict]:
    """Returns (player game logs, team points table, meta)."""
    evs = season_events(season, through_week)
    finals = [(wk, g) for wk, g in evs if g["completed"]]
    meta = {"events_seen": len(evs), "final_games": len(finals), "summary_failures": 0}

    def work(item):
        wk, g = item
        try:
            s = espn.summary("ncaaf", g["event_id"], final=True)
            return parse_boxscore(s, season, wk)
        except Exception as e:  # noqa: BLE001
            print(f"[ncaaf] summary {g['event_id']} failed: {e}", file=sys.stderr)
            return None

    rows = []
    with ThreadPoolExecutor(workers) as ex:
        for res in ex.map(work, finals):
            if res is None:
                meta["summary_failures"] += 1
            else:
                rows.extend(res)
    df = pd.DataFrame(rows)
    # dedupe (same game can appear on two scoreboard weeks at calendar edges)
    df = df.drop_duplicates(subset=["game_id", "player_id", "team_id"])
    df = add_derived(df)
    df["position"] = assign_positions(df, workers)
    df["pos_group"] = df["position"].map(pos_group)
    # team points
    tp = []
    seen = set()
    for wk, g in finals:
        if g["event_id"] in seen or g["home_score"] is None:
            continue
        seen.add(g["event_id"])
        tp.append({"season": season, "team": g["home"], "team_id": g["home_id"], "pts": g["home_score"], "opp_pts": g["away_score"]})
        tp.append({"season": season, "team": g["away"], "team_id": g["away_id"], "pts": g["away_score"], "opp_pts": g["home_score"]})
    return df, pd.DataFrame(tp), meta


def assign_positions(df: pd.DataFrame, workers: int = 8) -> pd.Series:
    """Roster positions from ESPN team rosters; fall back to role inference."""
    pos_map: dict[str, str] = {}
    team_ids = sorted(df["team_id"].dropna().unique())

    def fetch(tid):
        try:
            return espn.team_roster("ncaaf", tid)
        except Exception:  # noqa: BLE001
            return None

    with ThreadPoolExecutor(workers) as ex:
        for r in ex.map(fetch, team_ids):
            if not r:
                continue
            for grp in r.get("athletes", []):
                for a in grp.get("items", []):
                    p = (a.get("position") or {}).get("abbreviation")
                    if p:
                        pos_map[str(a["id"])] = p
    agg = df.groupby("player_id")[["attempts", "carries", "receptions"]].sum()

    def infer(pid):
        if pid in pos_map:
            return pos_map[pid]
        if pid in agg.index:
            a = agg.loc[pid]
            if a["attempts"] >= 8:
                return "QB"
            if a["carries"] > a["receptions"]:
                return "RB"
            return "WR"
        return None

    return df["player_id"].map(infer)


def roster_out_list(team_ids: list[str]) -> dict[str, str]:
    """Players ESPN lists in a roster's injuredReserveOrOut / suspended groups."""
    out = {}
    for tid in team_ids:
        try:
            r = espn.team_roster("ncaaf", tid)
        except Exception:  # noqa: BLE001
            continue
        for grp in (r or {}).get("athletes", []):
            if grp.get("position") in ("injuredReserveOrOut", "suspended"):
                for a in grp.get("items", []):
                    out[str(a["id"])] = "Out (roster: IR/out)" if grp["position"] != "suspended" else "Suspended"
    return out

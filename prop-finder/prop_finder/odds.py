"""Player prop lines.

Sources:
  1. ESPN core API 'propBets' (DraftKings lines, no key, no prices) -- default.
     Each fetch is snapshotted to data/snapshots/<league>/ so that once a game kicks off
     we can still use the last *pregame* line instead of an in-game line.
  2. The Odds API (needs ODDS_API_KEY env var) -- multi-book lines with prices.
"""
from __future__ import annotations

import glob
import json
import os
import re
import statistics
import sys
from datetime import datetime, timezone
from pathlib import Path

import requests

from .net import ROOT

CORE = "https://sports.core.api.espn.com/v2/sports/football/leagues/{lg}"
LG = {"nfl": "nfl", "ncaaf": "college-football"}
SNAP = ROOT / "data" / "snapshots"

ESPN_MARKETS = {
    "Total Passing Yards": "pass_yds",
    "Total Pass Completions": "completions",
    "Total Passing Attempts": "attempts",
    "Total Passing Touchdowns": "pass_tds",
    "Total Passing Interceptions": "interceptions",
    "Total Rushing Yards": "rush_yds",
    "Total Carries": "carries",
    "Total Receiving Yards": "rec_yds",
    "Total Receptions": "receptions",
    "Total Rushing Plus Receiving Yards": "rush_rec_yds",
    "Total Passing Plus Rushing Yards": "pass_rush_yds",
}

ODDS_API_MARKETS = {
    "player_pass_yds": "pass_yds",
    "player_pass_completions": "completions",
    "player_pass_attempts": "attempts",
    "player_pass_tds": "pass_tds",
    "player_pass_interceptions": "interceptions",
    "player_rush_yds": "rush_yds",
    "player_rush_attempts": "carries",
    "player_reception_yds": "rec_yds",
    "player_receptions": "receptions",
    "player_rush_reception_yds": "rush_rec_yds",
    "player_pass_rush_yds": "pass_rush_yds",
}
ODDS_SPORT = {"nfl": "americanfootball_nfl", "ncaaf": "americanfootball_ncaaf"}


def _ts(dt: datetime) -> str:
    return dt.strftime("%Y%m%dT%H%M%SZ")


def _parse_ts(s: str) -> datetime:
    return datetime.strptime(s, "%Y%m%dT%H%M%SZ").replace(tzinfo=timezone.utc)


def _fetch_espn_pages(league: str, event_id: str) -> list[dict] | None:
    url = f"{CORE.format(lg=LG[league])}/events/{event_id}/competitions/{event_id}/odds/100/propBets"
    pages, page = [], 1
    while True:
        r = requests.get(url, params={"lang": "en", "region": "us", "limit": 1000, "page": page}, timeout=25,
                         headers={"User-Agent": "prop-finder/0.1"})
        if r.status_code == 404:
            return pages or None  # no props posted for this event
        r.raise_for_status()
        d = r.json()
        pages.append(d)
        if page >= int(d.get("pageCount") or 1) or page >= 5:
            return pages
        page += 1


def _parse_espn_items(items: list[dict], league: str, event_id: str, fetched: str, note: str) -> list[dict]:
    best: dict[tuple, dict] = {}
    for it in items:
        name = re.sub(r"\s*\(incl\. overtime\)", "", (it.get("type") or {}).get("name", "")).strip()
        stat = ESPN_MARKETS.get(name)
        if not stat or "athlete" not in it:
            continue
        tgt = ((it.get("current") or {}).get("target") or {}).get("value")
        if tgt is None:
            continue
        m = re.search(r"/athletes/(\d+)", it["athlete"]["$ref"])
        if not m:
            continue
        aid = m.group(1)
        key = (aid, stat)
        upd = it.get("lastUpdated", "")
        if key not in best or upd > best[key]["line_updated"]:
            best[key] = {
                "league": league, "event_id": event_id, "source": "ESPN/DraftKings", "book": "DraftKings",
                "espn_id": aid, "player_name": None, "stat": stat, "line": float(tgt),
                "line_open": ((it.get("open") or {}).get("target") or {}).get("value"),
                "over_price": None, "under_price": None, "n_books": 1,
                "line_updated": upd, "fetched_at": fetched, "line_note": note,
            }
    return list(best.values())


def espn_props(league: str, game: dict, now: datetime) -> tuple[list[dict], str]:
    """Live fetch for pregame games (and snapshot). For started games, use latest pregame snapshot."""
    ev = game["event_id"]
    snapdir = SNAP / league
    snapdir.mkdir(parents=True, exist_ok=True)
    kickoff = datetime.fromisoformat(game["date_utc"].replace("Z", "+00:00"))
    if game["state"] == "pre" and now < kickoff:
        try:
            pages = _fetch_espn_pages(league, ev)
        except Exception as e:  # noqa: BLE001
            pages = None
            print(f"[odds] ESPN propBets {ev} failed: {e}", file=sys.stderr)
        if pages:
            ts = _ts(now)
            for i, p in enumerate(pages, 1):
                (snapdir / f"{ev}_{ts}_p{i}.json").write_text(json.dumps(p))
            items = [it for p in pages for it in p.get("items", [])]
            return _parse_espn_items(items, league, ev, ts, "live pregame"), "live"
        # fall through to snapshot if live fetch empty
    files = glob.glob(str(snapdir / f"{ev}_*_p*.json"))
    stamps = sorted({Path(f).name.split("_")[1] for f in files})
    pre = [s for s in stamps if _parse_ts(s) < kickoff]
    if not pre:
        return [], ("none posted" if game["state"] == "pre" else "game started; no pregame snapshot")
    s = pre[-1]
    items = []
    for f in sorted(glob.glob(str(snapdir / f"{ev}_{s}_p*.json"))):
        items.extend(json.loads(Path(f).read_text()).get("items", []))
    return _parse_espn_items(items, league, ev, s, f"pregame snapshot {s}"), f"snapshot {s}"


# ---------------------------------------------------------------- The Odds API
def _norm(s: str) -> str:
    s = (s or "").lower()
    s = re.sub(r"[^a-z0-9 ]", "", s)
    return re.sub(r"\b(jr|sr|ii|iii|iv|v)\b", "", s).strip()


def _redact(e) -> str:
    return re.sub(r"apiKey=[^&\s]+", "apiKey=***", str(e))


def odds_api_props(league: str, games: list[dict], max_events: int = 20, regions: str = "us") -> tuple[list[dict], str]:
    key = os.environ.get("ODDS_API_KEY")
    if not key:
        return [], "skipped: ODDS_API_KEY not set"
    sport = ODDS_SPORT[league]
    base = "https://api.the-odds-api.com/v4"
    try:
        r = requests.get(f"{base}/sports/{sport}/events", params={"apiKey": key}, timeout=20)
        r.raise_for_status()
        events = r.json()  # free call (does not count against quota)
    except Exception as e:  # noqa: BLE001
        return [], f"error listing events: {_redact(e)}"
    pending = [g for g in games if g["state"] == "pre"]
    out, used, remaining = [], 0, None
    for g in pending:
        if used >= max_events:
            break
        ko = datetime.fromisoformat(g["date_utc"].replace("Z", "+00:00"))
        match = None
        for e in events:
            ct = datetime.fromisoformat(e["commence_time"].replace("Z", "+00:00"))
            if abs((ct - ko).total_seconds()) > 6 * 3600:
                continue
            if _norm(e["home_team"]) in _norm(g["home_name"]) or _norm(g["home_name"]) in _norm(e["home_team"]):
                match = e
                break
        if not match:
            continue
        try:
            r = requests.get(f"{base}/sports/{sport}/events/{match['id']}/odds", timeout=25, params={
                "apiKey": key, "regions": regions, "markets": ",".join(ODDS_API_MARKETS), "oddsFormat": "american"})
            remaining = r.headers.get("x-requests-remaining", remaining)
            r.raise_for_status()
            data = r.json()
        except Exception as e:  # noqa: BLE001
            print(f"[odds-api] event {match['id']} failed: {_redact(e)}", file=sys.stderr)
            continue
        used += 1
        agg: dict[tuple, dict] = {}
        for bk in data.get("bookmakers", []):
            for mk in bk.get("markets", []):
                stat = ODDS_API_MARKETS.get(mk["key"])
                if not stat:
                    continue
                for oc in mk.get("outcomes", []):
                    k = (oc.get("description"), stat)
                    a = agg.setdefault(k, {"lines": [], "over": [], "under": [], "books": set()})
                    if oc.get("point") is not None:
                        a["lines"].append(oc["point"])
                    a["books"].add(bk["key"])
                    (a["over"] if oc["name"] == "Over" else a["under"]).append((oc.get("price"), oc.get("point")))
        now = _ts(datetime.now(timezone.utc))
        for (pname, stat), a in agg.items():
            if not a["lines"]:
                continue
            line = statistics.median(a["lines"])
            ov = [p for p, pt in a["over"] if pt == line and p is not None]
            un = [p for p, pt in a["under"] if pt == line and p is not None]
            out.append({
                "league": league, "event_id": g["event_id"], "source": "TheOddsAPI", "book": "consensus",
                "espn_id": None, "player_name": pname, "player_norm": _norm(pname), "stat": stat, "line": line,
                "line_open": None, "over_price": max(ov) if ov else None, "under_price": max(un) if un else None,
                "n_books": len(a["books"]), "line_updated": now, "fetched_at": now, "line_note": "odds api",
            })
    return out, f"ok: {used} events queried, credits remaining={remaining}"

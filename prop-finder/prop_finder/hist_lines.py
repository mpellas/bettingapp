"""Historical player-prop lines from ESPN's core API (backtests only).

For completed events ESPN still serves propBets for the ESPN BET provider (id 58) on many games. The feed mixes the
main over/under line with an alternate-line ladder under the same market name; the main line is the item whose
`current` carries both over and under prices. Raw responses are cached under data/hist_props/{league}/{event}.json
(one file per event, including 'no lines' results) so a rerun makes no network calls.
"""
from __future__ import annotations

import json
import re
import time
from pathlib import Path

import requests

from .odds import ESPN_MARKETS

ROOT = Path(__file__).resolve().parents[1]
DIR = ROOT / "data" / "hist_props"
CORE = "https://sports.core.api.espn.com/v2/sports/football/leagues/{lg}/events/{ev}/competitions/{ev}/odds"
LG = {"nfl": "nfl", "ncaaf": "college-football"}
PROP_PROVIDERS = {"58": "ESPN BET", "100": "DraftKings"}   # 59 = live odds (excluded)
_S = requests.Session()
_S.headers["User-Agent"] = "Mozilla/5.0 prop-finder-backtest"


def _get(url, params=None, tries=3):
    for i in range(tries):
        try:
            r = _S.get(url, params=params, timeout=25)
            if r.status_code == 404:
                return None
            if r.status_code == 200:
                return r.json()
        except requests.RequestException:
            pass
        time.sleep(1.5 * (i + 1))
    raise RuntimeError(f"ESPN request failed: {url}")


def fetch_event(league: str, event_id: str) -> dict:
    """Return cached {'event_id', 'providers': [...], 'props': {pid: [items]}}; fetch once if missing."""
    p = DIR / league / f"{event_id}.json"
    if p.exists():
        return json.loads(p.read_text())
    base = CORE.format(lg=LG[league], ev=event_id)
    lst = _get(base, {"limit": 100}) or {}
    pids = []
    for it in lst.get("items", []):
        m = re.search(r"/odds/(\d+)", it.get("$ref", "")) if "$ref" in it else None
        pid = str((it.get("provider") or {}).get("id") or (m.group(1) if m else ""))
        if pid:
            pids.append(pid)
    out = {"event_id": str(event_id), "providers": pids, "props": {}, "fetched": time.strftime("%Y-%m-%dT%H:%M:%S%z")}
    for pid in pids:
        if pid not in PROP_PROVIDERS:
            continue
        items, page = [], 1
        while True:
            d = _get(f"{base}/{pid}/propBets", {"limit": 1000, "page": page})
            if not d:
                break
            items.extend(d.get("items", []))
            if page >= int(d.get("pageCount", 1) or 1):
                break
            page += 1
        if items:
            out["props"][pid] = items
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(out))
    return out


def _price(x):
    try:
        v = (x or {}).get("american")
        return int(str(v).replace("+", "")) if v not in (None, "", "EVEN") else (100 if v == "EVEN" else None)
    except ValueError:
        return None


def parse_event(league: str, raw: dict) -> list[dict]:
    """Main O/U lines only. ESPN BET publishes the main line as two items (one carrying an `over` price, one an
    `under` price) at the same target; alternate-ladder rungs carry only a target. Both the OPENING main line
    (open.target + open prices; posted pregame) and the LAST listed main line (current.*) are returned."""
    cand = {}
    for pid, items in raw.get("props", {}).items():
        book = PROP_PROVIDERS.get(pid, pid)
        for it in items:
            name = (it.get("type") or {}).get("name", "")
            name = re.sub(r"\s*\(incl\.? overtime\)\s*$", "", name, flags=re.I).strip()
            stat = ESPN_MARKETS.get(name)
            if not stat or "athlete" not in it:
                continue
            m = re.search(r"/athletes/(\d+)", it["athlete"].get("$ref", ""))
            if not m:
                continue
            cur, opn = it.get("current") or {}, it.get("open") or {}
            for side in ("over", "under"):
                if side in cur or side in opn:
                    d = cand.setdefault((pid, book, m.group(1), stat), {})
                    d[side] = {"cur_t": (cur.get("target") or {}).get("value"), "cur_p": _price(cur.get(side)),
                               "open_t": (opn.get("target") or {}).get("value"), "open_p": _price(opn.get(side)),
                               "upd": it.get("lastUpdated", "")}
    rows = {}
    for (pid, book, aid, stat), d in cand.items():
        o, u = d.get("over"), d.get("under")
        if not o or not u:
            continue
        row = {"league": league, "event_id": raw["event_id"], "espn_id": aid, "player_name": None, "stat": stat,
               "line_last": o["cur_t"] if o["cur_t"] == u["cur_t"] else None,
               "over_price_last": o["cur_p"], "under_price_last": u["cur_p"],
               "line_open": o["open_t"] if o["open_t"] == u["open_t"] else None,
               "over_open": o["open_p"], "under_open": u["open_p"], "book": book, "n_books": 1,
               "source": f"ESPN core API propBets, provider {pid} ({book}), historical",
               "line_updated": max(o["upd"], u["upd"])}
        key = (aid, stat)
        if key not in rows or pid == "58":
            rows[key] = row
    return list(rows.values())

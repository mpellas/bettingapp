"""The Odds API (the-odds-api.com) player-prop prices for NFL yards markets.

Free-tier keyed capture: DraftKings + FanDuel for player_pass_yds / player_rush_yds / player_reception_yds.
Quota: ~1 credit per market per event-odds call. Caps spend at MAX_CREDITS_PER_PASS (~40) and logs
x-requests-used / x-requests-remaining from response headers. Key from ODDS_API_KEY or data/secrets/odds_api_key
(never logged). Events list endpoint is free; only /events/{id}/odds burns credits.
"""
from __future__ import annotations

import datetime as dt
import json
import os
import re
import time
from pathlib import Path

import requests

from . import DATA
from .snapshot import SNAP, PT, UA, _write, sha256

SECRET = DATA / "secrets" / "odds_api_key"
BASE = "https://api.the-odds-api.com/v4"
SPORT = "americanfootball_nfl"
MARKETS = ("player_pass_yds", "player_rush_yds", "player_reception_yds")
MARKET_MAP = {"player_pass_yds": "pass_yds", "player_rush_yds": "rush_yds", "player_reception_yds": "rec_yds"}
BOOKS = ("draftkings", "fanduel")
MAX_CREDITS_PER_PASS = 40
_S = requests.Session()
_S.headers.update(UA)


def load_key() -> str | None:
    k = (os.environ.get("ODDS_API_KEY") or "").strip()
    if k:
        return k
    if SECRET.exists():
        return SECRET.read_text().strip() or None
    env = DATA.parent / ".env"
    if env.exists():
        for line in env.read_text().splitlines():
            if line.startswith("ODDS_API_KEY="):
                return line.split("=", 1)[1].strip().strip('"').strip("'") or None
    return None


def _hdr_int(r, *names) -> int | None:
    for n in names:
        v = r.headers.get(n)
        if v is not None:
            try:
                return int(v)
            except ValueError:
                pass
    return None


def norm_name(s: str) -> str:
    s = (s or "").lower().replace(".", "").replace("'", "").replace("-", " ")
    s = re.sub(r"\b(jr|sr|ii|iii|iv)\b", "", s)
    return re.sub(r"\s+", " ", s).strip()


def fetch_events(key: str) -> tuple[list[dict], dict]:
    """Upcoming NFL events (quota-free)."""
    r = _S.get(f"{BASE}/sports/{SPORT}/events", params={"apiKey": key}, timeout=30)
    r.raise_for_status()
    meta = {"remaining": _hdr_int(r, "x-requests-remaining"), "used": _hdr_int(r, "x-requests-used")}
    return r.json(), meta


def match_event(espn_home: str, espn_away: str, kick: dt.datetime, events: list[dict]) -> dict | None:
    """Match ESPN home/away display names + kickoff to an Odds API event."""
    nh, na = norm_name(espn_home), norm_name(espn_away)
    best, best_dt = None, None
    for ev in events:
        ht, at = norm_name(ev.get("home_team", "")), norm_name(ev.get("away_team", ""))
        if not ((ht == nh or nh in ht or ht in nh) and (at == na or na in at or at in na)):
            continue
        ct = dt.datetime.fromisoformat(ev["commence_time"].replace("Z", "+00:00"))
        dsec = abs((ct - kick).total_seconds())
        if dsec > 6 * 3600:
            continue
        if best is None or dsec < best_dt:
            best, best_dt = ev, dsec
    return best


def fetch_event_odds(key: str, event_id: str, markets: tuple[str, ...] = MARKETS,
                     bookmakers: tuple[str, ...] = BOOKS) -> tuple[dict, dict]:
    """One event-odds call (~1 credit per market). Returns (json, credit_meta)."""
    r = _S.get(f"{BASE}/sports/{SPORT}/events/{event_id}/odds",
               params={"apiKey": key, "regions": "us", "markets": ",".join(markets),
                       "bookmakers": ",".join(bookmakers), "oddsFormat": "american"},
               timeout=45)
    meta = {"remaining": _hdr_int(r, "x-requests-remaining"), "used": _hdr_int(r, "x-requests-used"),
            "http": r.status_code, "markets_requested": len(markets)}
    if r.status_code != 200:
        return {"error": r.text[:500], "status": r.status_code}, meta
    return r.json(), meta


def parse_prices(payload: dict) -> list[dict]:
    """Flatten bookmaker outcomes -> rows with market, player_name, line, over/under prices, book."""
    out = []
    if not isinstance(payload, dict) or "bookmakers" not in payload:
        return out
    for bm in payload.get("bookmakers") or []:
        book = bm.get("key")
        for mkt in bm.get("markets") or []:
            mk = MARKET_MAP.get(mkt.get("key"))
            if not mk:
                continue
            # group Over/Under by (player, point)
            pair = {}
            for o in mkt.get("outcomes") or []:
                name, side = o.get("description") or "", (o.get("name") or "").lower()
                if side not in ("over", "under") or not name or o.get("point") is None:
                    continue
                k = (norm_name(name), float(o["point"]))
                pair.setdefault(k, {"player_name": name, "market": mk, "line": float(o["point"]),
                                    "book": book, "over_price": None, "under_price": None})
                pair[k][f"{side}_price"] = o.get("price")
            out.extend(pair.values())
    return out


def index_prices(rows: list[dict]) -> dict:
    """(norm_name, market) -> preferred row (draftkings over fanduel; exact line kept)."""
    pref = {"draftkings": 0, "fanduel": 1}
    by: dict[tuple, list] = {}
    for r in rows:
        if r.get("over_price") is None or r.get("under_price") is None:
            continue
        by.setdefault((norm_name(r["player_name"]), r["market"]), []).append(r)
    out = {}
    for k, rs in by.items():
        rs = sorted(rs, key=lambda x: (pref.get(x["book"], 9), abs(x["line"])))
        out[k] = rs  # all lines for that player+market, DK first
    return out


def merge_prices_onto_espn(espn_rows: list[dict], price_index: dict, name_by_espn: dict) -> tuple[list[dict], int]:
    """Attach Odds API prices to ESPN rows matched by player+market (prefer exact line, else closest ≤1.0).
    Returns (rows, n_priced)."""
    n = 0
    for r in espn_rows:
        nm = name_by_espn.get(str(r.get("espn_id")))
        if not nm:
            continue
        cands = price_index.get((nm, r["market"])) or []
        if not cands:
            continue
        exact = [c for c in cands if abs(c["line"] - float(r["line"])) < 1e-6]
        pool = exact or [c for c in cands if abs(c["line"] - float(r["line"])) <= 1.0]
        if not pool:
            continue
        best = min(pool, key=lambda c: (0 if c["book"] == "draftkings" else 1, abs(c["line"] - float(r["line"]))))
        r["over_price"] = best["over_price"]
        r["under_price"] = best["under_price"]
        r["price_book"] = best["book"]
        r["price_line"] = best["line"]
        n += 1
    return espn_rows, n


def capture_for_events(espn_events: list[dict], day: Path, ts: str, max_credits: int = MAX_CREDITS_PER_PASS) -> dict:
    """Pull Odds API props for ESPN events being captured. espn_events items need:
    event_id, home, away, kick (datetime UTC). Saves raw JSON, returns summary (no key material)."""
    key = load_key()
    summary = {"enabled": bool(key), "credits_spent_this_pass": 0, "remaining": None, "used_total": None,
               "events": [], "skipped": [], "max_credits": max_credits}
    if not key:
        summary["skipped"].append({"reason": "no ODDS_API_KEY"})
        return summary
    try:
        events, meta = fetch_events(key)
    except Exception as e:
        summary["skipped"].append({"reason": f"events list failed: {type(e).__name__}"})
        return summary
    summary["remaining"] = meta.get("remaining")
    summary["used_total"] = meta.get("used")
    summary["n_oddsapi_events"] = len(events)
    spent = 0
    for ee in espn_events:
        cost = len(MARKETS)
        if spent + cost > max_credits:
            summary["skipped"].append({"event_id": ee["event_id"], "reason": f"credit cap {max_credits}"})
            continue
        m = match_event(ee["home"], ee["away"], ee["kick"], events)
        if not m:
            summary["skipped"].append({"event_id": ee["event_id"], "reason": "no Odds API event match"})
            continue
        try:
            payload, cmeta = fetch_event_odds(key, m["id"])
        except Exception as e:
            summary["skipped"].append({"event_id": ee["event_id"], "reason": f"odds fetch: {type(e).__name__}"})
            continue
        spent += cmeta.get("markets_requested") or cost
        if cmeta.get("remaining") is not None:
            summary["remaining"] = cmeta["remaining"]
        if cmeta.get("used") is not None:
            summary["used_total"] = cmeta["used"]
        raw = json.dumps(payload, separators=(",", ":")).encode()
        fname = f"{ee['event_id']}_oddsapi_{ts}.json"
        info = _write(day, fname, raw)
        prices = parse_prices(payload) if cmeta.get("http") == 200 else []
        by_mk = {}
        for p in prices:
            by_mk[p["market"]] = by_mk.get(p["market"], 0) + 1
        n_priced = sum(1 for p in prices if p.get("over_price") is not None and p.get("under_price") is not None)
        summary["events"].append({
            "event_id": ee["event_id"], "oddsapi_id": m["id"], "file": info["file"],
            "http": cmeta.get("http"), "n_price_rows": len(prices), "n_with_both_prices": n_priced,
            "lines_by_market": by_mk, "books": sorted({p["book"] for p in prices}),
            "remaining": cmeta.get("remaining"),
        })
        time.sleep(0.35)
    summary["credits_spent_this_pass"] = spent
    return summary

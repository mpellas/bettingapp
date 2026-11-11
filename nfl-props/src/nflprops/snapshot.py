"""FREE prop-line snapshot capture (no API key, nothing paid).

Source: ESPN's public core API, the same read-only approach /workspace/prop-finder uses:
    scoreboard   https://site.api.espn.com/apis/site/v2/sports/football/nfl/scoreboard
    odds list    https://sports.core.api.espn.com/v2/sports/football/leagues/nfl/events/{ev}/competitions/{ev}/odds
    propBets     .../odds/{provider}/propBets?limit=1000&page=k
In 2026 the only provider ESPN lists is 100 = DraftKings; its propBets carry open/current TARGETS but NO PRICES.
Prices are stored whenever a provider includes them (e.g. ESPN BET, provider 58, did in 2025); the parser records
whether they were present. The game-level odds list (spread / total / moneyline WITH prices) is saved too.

Every run:
  * writes the raw HTTP response bytes, unmodified, to data/snapshots/<YYYY-MM-DD PT>/ as
        scoreboard_<season>_<type>_wk<w>_<UTC>.json, <event>_odds_<UTC>.json, <event>_<provider>_<UTC>_p<k>.json
  * appends one record per event to data/snapshots/capture_log.jsonl (capture time UTC + PT, kickoff, files, sha256,
    HTTP status, item counts);
  * rewrites the day's MANIFEST.sha256 (sha256sum format, all files of that day, sorted) and appends the manifest's
    own sha256 + time to data/snapshots/manifest_log.txt (so a snapshot's hash is logged before kickoff).
Only games that have not kicked off are captured. Idempotent: an event captured less than --min-interval minutes
ago is skipped, files are never overwritten, and the manifest is recomputed from the directory contents.

    python -m nflprops.snapshot                 # current + next ESPN week
    python -m nflprops.snapshot --weeks 1 --min-interval 0
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import re
import sys
import time
from pathlib import Path
from zoneinfo import ZoneInfo

import requests

from . import DATA

SNAP = DATA / "snapshots"
LOG = SNAP / "capture_log.jsonl"
PT = ZoneInfo("America/Los_Angeles")
SITE = "https://site.api.espn.com/apis/site/v2/sports/football/nfl/scoreboard"
CORE = "https://sports.core.api.espn.com/v2/sports/football/leagues/nfl/events/{ev}/competitions/{ev}/odds"
UA = {"User-Agent": "nflprops-snapshot/0.1 (personal research; read-only)"}
MARKETS = {"Total Passing Yards": "pass_yds", "Total Rushing Yards": "rush_yds", "Total Receiving Yards": "rec_yds"}
_S = requests.Session()
_S.headers.update(UA)


def _get(url, params=None, tries=3):
    last = None
    for i in range(tries):
        try:
            r = _S.get(url, params=params, timeout=25)
            if r.status_code in (200, 404):
                return r
            last = f"HTTP {r.status_code}"
        except requests.RequestException as e:
            last = str(e)
        time.sleep(1.5 * (i + 1))
    raise RuntimeError(f"GET failed {url}: {last}")


def sha256(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def _write(day: Path, name: str, content: bytes) -> dict:
    p = day / name
    if p.exists():                      # never overwrite (append-only)
        return {"file": name, "sha256": sha256(p.read_bytes()), "existed": True}
    p.write_bytes(content)
    return {"file": name, "sha256": sha256(content)}


def last_captures() -> dict:
    out = {}
    if LOG.exists():
        for line in LOG.read_text().splitlines():
            r = json.loads(line)
            out[r["event_id"]] = max(out.get(r["event_id"], ""), r["captured_at_utc"])
    return out


def write_manifest(day: Path) -> str:
    files = sorted(p for p in day.iterdir() if p.is_file() and p.name != "MANIFEST.sha256")
    txt = "".join(f"{sha256(p.read_bytes())}  {p.name}\n" for p in files)
    (day / "MANIFEST.sha256").write_text(txt)
    h = sha256(txt.encode())
    now = dt.datetime.now(dt.timezone.utc)
    ml = SNAP / "manifest_log.txt"
    if ml.exists() and any(line.split("\t")[2:4] == [f"{day.name}/MANIFEST.sha256", h]
                           for line in ml.read_text().splitlines()):
        return h                         # unchanged since it was last logged
    with open(ml, "a") as f:
        f.write(f"{now.isoformat(timespec='seconds')}\t{now.astimezone(PT).isoformat(timespec='seconds')}\t"
                f"{day.name}/MANIFEST.sha256\t{h}\t{len(files)} files\n")
    return h


def parse_items(items: list[dict]) -> list[dict]:
    """Full-game pass/rush/rec yards O/U items -> rows (one per athlete-market-target; prices if present)."""
    rows = {}
    for it in items:
        name = re.sub(r"\s*\(incl\.? overtime\)\s*$", "", (it.get("type") or {}).get("name", ""), flags=re.I).strip()
        mk = MARKETS.get(name)
        if not mk or "athlete" not in it:
            continue
        m = re.search(r"/athletes/(\d+)", it["athlete"].get("$ref", ""))
        cur, opn = it.get("current") or {}, it.get("open") or {}
        tgt = (cur.get("target") or {}).get("value")
        if not m or tgt is None:
            continue
        pid = re.search(r"/casinos/(\d+)", (it.get("provider") or {}).get("$ref", ""))
        k = (m.group(1), mk, float(tgt))
        r = rows.setdefault(k, {"espn_id": m.group(1), "market": mk, "line": float(tgt),
                                "line_open": (opn.get("target") or {}).get("value"),
                                "provider": pid.group(1) if pid else None, "over_price": None, "under_price": None,
                                "espn_last_updated": it.get("lastUpdated")})
        r["espn_last_updated"] = max(r["espn_last_updated"] or "", it.get("lastUpdated") or "")
        for side in ("over", "under"):
            if side in cur and isinstance(cur[side], dict):
                r[f"{side}_price"] = cur[side].get("american")
    return list(rows.values())


def capture(weeks: int = 2, min_interval: float = 5.0, now: dt.datetime | None = None,
            far_interval: float | None = None, near_minutes: float = 60.0) -> dict:
    """min_interval applies to events kicking off within `near_minutes`; events further out use far_interval
    (default = min_interval). The summary's next_kickoff_min lets a loop capture faster before kickoffs."""
    now = now or dt.datetime.now(dt.timezone.utc)
    far_interval = min_interval if far_interval is None else far_interval
    ts = now.strftime("%Y%m%dT%H%M%SZ")
    day = SNAP / now.astimezone(PT).strftime("%Y-%m-%d")
    day.mkdir(parents=True, exist_ok=True)
    r = _get(SITE, {"limit": 400})
    sb = r.json()
    season, stype, week = sb["season"]["year"], sb["season"]["type"], sb["week"]["number"]
    boards = [(week, r.content, sb)]
    for w in range(week + 1, week + weeks):
        rr = _get(SITE, {"limit": 400, "week": w, "seasontype": stype, "year": season})
        boards.append((w, rr.content, rr.json()))
    prev = last_captures()
    summary = {"captured_at_utc": now.isoformat(timespec="seconds"),
               "captured_at_pt": now.astimezone(PT).isoformat(timespec="seconds"), "dir": str(day.relative_to(DATA.parent)),
               "events": [], "skipped": []}
    log_rows = []
    next_kick = None
    for w, raw, js in boards:
        sbname = f"scoreboard_{season}_{stype}_wk{w}_{ts}.json"
        sbf = None
        for e in js.get("events", []):
            ev, kick = e["id"], dt.datetime.fromisoformat(e["date"].replace("Z", "+00:00"))
            state = e["status"]["type"]["state"]
            if state != "pre" or kick <= now:
                summary["skipped"].append({"event_id": ev, "reason": f"state={state}, kickoff passed"})
                continue
            mins = (kick - now).total_seconds() / 60
            next_kick = mins if next_kick is None else min(next_kick, mins)
            iv = min_interval if mins <= near_minutes else far_interval
            if ev in prev and (now - dt.datetime.fromisoformat(prev[ev])).total_seconds() < iv * 60:
                summary["skipped"].append({"event_id": ev, "reason": f"captured < {iv:g} min ago"})
                continue
            sbf = sbf or _write(day, sbname, raw)      # scoreboard saved only if something is captured from it
            rec = {"captured_at_utc": now.isoformat(timespec="seconds"),
                   "captured_at_pt": now.astimezone(PT).isoformat(timespec="seconds"), "event_id": ev,
                   "season": season, "season_type": stype, "week": w, "name": e.get("shortName"),
                   "kickoff_utc": kick.isoformat(), "minutes_to_kickoff": round((kick - now).total_seconds() / 60, 1),
                   "scoreboard_file": sbf["file"], "files": [], "providers": {}}
            ro = _get(CORE.format(ev=ev), {"limit": 100})
            rec["files"].append({**_write(day, f"{ev}_odds_{ts}.json", ro.content), "http": ro.status_code})
            pids = []
            if ro.status_code == 200:
                for it in ro.json().get("items", []):
                    p = str((it.get("provider") or {}).get("id") or "")
                    if p and p not in pids:
                        pids.append(p)
            rec["odds_providers"] = pids        # [] = ESPN lists no odds provider for this event yet
            n_lines = {}
            for p in pids:
                page, items, st = 1, [], None
                while True:
                    rp = _get(CORE.format(ev=ev) + f"/{p}/propBets",
                              {"lang": "en", "region": "us", "limit": 1000, "page": page})
                    st = rp.status_code
                    if st != 200:
                        break
                    d = rp.json()
                    rec["files"].append({**_write(day, f"{ev}_{p}_{ts}_p{page}.json", rp.content), "http": st,
                                         "n_items": len(d.get("items", []))})
                    items += d.get("items", [])
                    if page >= int(d.get("pageCount") or 1) or page >= 10:
                        break
                    page += 1
                rows = parse_items(items)
                by = {}
                for x in rows:
                    by[x["market"]] = by.get(x["market"], 0) + 1
                rec["providers"][p] = {"status": "ok" if items else f"no propBets (HTTP {st})", "n_items": len(items),
                                       "lines_by_market": by,
                                       "n_with_prices": sum(x["over_price"] is not None for x in rows)}
                n_lines[p] = by
            log_rows.append(rec)
            summary["events"].append({"event_id": ev, "name": rec["name"], "week": w,
                                      "kickoff_pt": kick.astimezone(PT).isoformat(timespec="minutes"),
                                      "providers": rec["providers"]})
    with open(LOG, "a") as f:
        for rec in log_rows:
            f.write(json.dumps(rec) + "\n")
    summary["manifest_sha256"] = write_manifest(day)
    tot, priced = {}, 0
    for e in summary["events"]:
        for p in e["providers"].values():
            for mk, n in p["lines_by_market"].items():
                tot[mk] = tot.get(mk, 0) + n
            priced += p["n_with_prices"]
    summary["total_lines_by_market"], summary["total_lines_with_prices"] = tot, priced
    summary["next_kickoff_min"] = None if next_kick is None else round(next_kick, 1)
    return summary


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--weeks", type=int, default=2, help="ESPN weeks to scan starting at the current one")
    ap.add_argument("--min-interval", type=float, default=5.0, help="skip events captured less than N min ago")
    ap.add_argument("--far-interval", type=float, default=None,
                    help="interval for events more than --near-minutes from kickoff (default: --min-interval)")
    ap.add_argument("--near-minutes", type=float, default=60.0)
    a = ap.parse_args()
    s = capture(a.weeks, a.min_interval, far_interval=a.far_interval, near_minutes=a.near_minutes)
    json.dump(s, sys.stdout, indent=1)
    print()

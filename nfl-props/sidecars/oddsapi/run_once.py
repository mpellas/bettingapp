"""Sidecar: Odds API prices once. Writes ONLY data/snapshots/.../oddsapi_*.json.
Hashed nflprops modules untouched. Call only at D/C check-ins.
Budget: DraftKings + 3 yards markets; only the next 1–2 events by kickoff
(~3 credits/game). Prefer --event-id or upcoming window to avoid burning free plan.
"""
from __future__ import annotations
import argparse, hashlib, json, os, sys, urllib.request
from datetime import datetime, timezone, timedelta
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]
KEY = os.environ.get("ODDS_API_KEY")
if not KEY:
    p = ROOT / "data" / "secrets" / "odds_api_key"
    if p.exists():
        KEY = p.read_text().strip()
if not KEY:
    print("NO_KEY"); sys.exit(1)
MARKETS = "player_pass_yds,player_rush_yds,player_reception_yds"
BOOK = "draftkings"
BASE = "https://api.the-odds-api.com/v4"

def get(url):
    with urllib.request.urlopen(url, timeout=60) as r:
        return json.loads(r.read().decode()), {
            k: r.headers.get(k)
            for k in ("x-requests-remaining", "x-requests-used", "x-requests-last")
        }

ap = argparse.ArgumentParser()
ap.add_argument("--event-id", action="append", default=[])
ap.add_argument("--max-events", type=int, default=1, help="soonest N events if no --event-id (default 1)")
ap.add_argument("--within-hours", type=float, default=6.0)
args = ap.parse_args()

now = datetime.now(timezone.utc)
day = now.astimezone().strftime("%Y-%m-%d")
out_dir = ROOT / "data" / "snapshots" / day
out_dir.mkdir(parents=True, exist_ok=True)
events, h1 = get(f"{BASE}/sports/americanfootball_nfl/events?apiKey={KEY}")
ts = now.strftime("%Y%m%dT%H%M%SZ")

def commence(ev):
    t = ev.get("commence_time")
    return datetime.fromisoformat(t.replace("Z", "+00:00")) if t else now + timedelta(days=99)

if args.event_id:
    want = set(args.event_id)
    chosen = [e for e in events if e.get("id") in want]
else:
    upcoming = [e for e in events if commence(e) >= now - timedelta(minutes=30)]
    upcoming = [e for e in upcoming if commence(e) <= now + timedelta(hours=args.within_hours)]
    upcoming.sort(key=commence)
    chosen = upcoming[: max(1, args.max_events)]

saved = []
for ev in chosen:
    eid = ev["id"]
    url = (
        f"{BASE}/sports/americanfootball_nfl/events/{eid}/odds"
        f"?apiKey={KEY}&regions=us&markets={MARKETS}&oddsFormat=american&bookmakers={BOOK}"
    )
    try:
        data, h = get(url)
    except Exception as e:
        print("ERR", eid[:8], type(e).__name__, str(e)[:120])
        continue
    fn = out_dir / f"oddsapi_{eid}_{ts}.json"
    payload = {
        "captured_at_utc": now.isoformat(),
        "event": {k: ev.get(k) for k in ("id", "commence_time", "home_team", "away_team")},
        "odds": data,
        "headers": h,
        "budget": {"bookmakers": BOOK, "markets": MARKETS, "max_events": args.max_events},
    }
    raw = json.dumps(payload, indent=2).encode()
    fn.write_bytes(raw)
    saved.append({
        "file": fn.name,
        "sha256": hashlib.sha256(raw).hexdigest(),
        "event": f"{ev.get('away_team')} @ {ev.get('home_team')}",
        "books": len((data or {}).get("bookmakers") or []),
        "remaining": h.get("x-requests-remaining"),
        "last_cost": h.get("x-requests-last"),
    })
print(json.dumps({
    "chosen": len(chosen),
    "saved": saved,
    "list_remaining": h1.get("x-requests-remaining"),
}, indent=2))
